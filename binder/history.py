import logging
import threading
import warnings

from django.db import models
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.conf import settings
from django.dispatch import Signal

from .json import jsondumps, JsonResponse


transaction_commit = Signal(providing_args=['changeset'])


class Changeset(models.Model):
	source = models.CharField(max_length=32)
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='changesets')
	date = models.DateTimeField(auto_now=True)  # When this changeset is "final". Ideally equal to the moment the DB commits the transaction.
	uuid = models.CharField(max_length=36, blank=True, null=True)

	def __str__(self):
		uuid = self.uuid[:8] if self.uuid else None
		username = self.user.get_username() if self.user else None
		return '{}/{} by {} on {}'.format(self.id, uuid, username, self.date.strftime('%Y%m%d-%H%M%S'))

	class Meta:
		ordering = ['id']



class Change(models.Model):
	changeset = models.ForeignKey(Changeset, on_delete=models.CASCADE, db_index=True, related_name='changes')
	model = models.CharField(max_length=64, db_index=True)
	oid = models.IntegerField(db_index=True)
	field = models.CharField(max_length=64, db_index=True)
	diff = models.BooleanField(default=False)
	before = models.TextField(blank=True, null=True)
	after = models.TextField(blank=True, null=True)

	def __str__(self):
		return '{}: {}({}).{}  {}  ->  {}'.format(self.id, self.model, self.oid, self.field, self.before[:20], self.after[:20])

	class Meta:
		ordering = ['id']



logger = logging.getLogger(__name__)



class __Transaction(threading.local):
	def __init__(self):
		logger.info('Creating new _Transaction for thread {}'.format(threading.current_thread().name))

		self.user = None
		self.uuid = None
		self.source = None
		self.started = False
		self.changes = {}

	def start(self, *, user=None, uuid=None, source=None):
		if self.started:
			raise RuntimeError('Called _Transaction.start() while there is an open transaction')

		self.started = True
		self.changes.clear()
		self.user = user
		self.uuid = uuid
		self.source = source

	def stop(self):
		if not self.started:
			raise RuntimeError('Called _Transaction.stop() while there is no open transaction')

		self.started = False
		self.changes.clear()

_Transaction = __Transaction()



class NewInstanceField:
	pass

class DeferredM2M:
	pass



# History context manager. Use this.
class atomic:
	def __init__(self, source=None, user=None, uuid=None):
		self.source = source
		self.user = user
		self.uuid = uuid

	def __enter__(self):
		_start(self.source, self.user, self.uuid)

	def __exit__(self, etype, value, traceback):
		if etype is None:
			_commit()
			return True
		else:
			_abort()
			return False # reraise



def _start(source=None, user=None, uuid=None):
	if source is None:
		raise ValueError('source may not be None')

	_Transaction.start(source=source, user=user, uuid=uuid)



# old can be NewInstanceField, which will translate to None on commit.
# old and new can be DeferredM2M. But only for actual m2m fields or SHIT WILL BREAK.
def change(model, oid, field, old, new):
	# FK fields on newly created objects cause annoyances. Ignore them.
	if oid is NewInstanceField:
		return
	hid = model, oid, field

	# Re-use old old value (so we accumulate all changes in one)
	if hid in _Transaction.changes:
		old = _Transaction.changes[hid][0]
	elif old is DeferredM2M:
		# If we haven't seen this field before, and it's a m2m of
		# unknown value, we need to get the value now.
		#
		# The target model may be a non-Binder model (e.g. User), so lbyl.
		if hasattr(model, 'binder_serialize_m2m_field'):
			old = model(id=oid).binder_serialize_m2m_field(field)

	_Transaction.changes[hid] = old, new, False



def m2m_diff(old, new):
	return sorted(old - new), sorted(new - old), True



# FIXME: use bulk inserts for efficiency.
def _commit():
	# Fill in the deferred m2ms
	for (model, oid, field), (old, new, diff) in _Transaction.changes.items():
		if new is DeferredM2M:
			# The target model may be a non-Binder model (e.g. User), so lbyl.
			if hasattr(model, 'binder_serialize_m2m_field'):
				new = model(id=oid).binder_serialize_m2m_field(field)
				_Transaction.changes[model, oid, field] = m2m_diff(old, new)

	# Filter non-changes
	_Transaction.changes = {idx: (old, new, diff) for idx, (old, new, diff) in _Transaction.changes.items() if old != new}

	if not _Transaction.changes:
		_Transaction.stop()
		return

	user = _Transaction.user if _Transaction.user and not _Transaction.user.is_anonymous else None

	changeset = Changeset(
		source=_Transaction.source,
		user=user,
		uuid=_Transaction.uuid,
	)
	changeset.save()

	for (model, oid, field), (old, new, diff) in _Transaction.changes.items():
		# New instances get None for all the before values
		if old is NewInstanceField:
			old = None

		# Actually record the change
		change = Change(
			changeset=changeset,
			model=model.__name__,
			oid=oid,
			field=field,
			diff=diff,
			before=jsondumps(old),
			after=jsondumps(new),
		)
		change.save()

	transaction_commit.send(sender=None, changeset=changeset)

	# Save the changeset again, to update the date to be as close to DB transaction commit start as possible.
	changeset.save()
	_Transaction.stop()



def _abort():
	_Transaction.stop()



def view_changesets(request, changesets):
	data = []
	userids = set()
	for cs in changesets:
		changes = []
		for c in cs.changes.order_by('model', 'oid', 'field'):
			changes.append({'model': c.model, 'oid': c.oid, 'field': c.field, 'diff': c.diff, 'before': c.before, 'after': c.after})
		data.append({'date': cs.date, 'uuid': cs.uuid, 'id': cs.id, 'source': cs.source, 'user': cs.user_id, 'changes': changes})
		if cs.user_id:
			userids.add(cs.user_id)

	users = []
	for u in get_user_model().objects.filter(id__in=userids):
		users.append({'id': u.id, 'username': u.get_username(), 'email': u.email, 'first_name': u.first_name, 'last_name': u.last_name})

	return JsonResponse({'data': data, 'with': {'user': users}})



def view_changesets_debug(request, changesets):
	body = ['<html>', '<head>', '<style type="text/css">td {padding: 0px 20px;} th {padding: 0px 20px;}</style>', '</head>', '<body>']
	for cs in changesets:
		username = cs.user.get_username() if cs.user else None
		body.append('<h3>Changeset {} by {}: {} on {} {{{}}}'.format(cs.id, cs.source, username, cs.date.strftime('%Y-%m-%d %H:%M:%S'), cs.uuid))
		body.append('<br><br>')
		body.append('<table>')
		body.append('<tr><th>model</th><th>object id</th><th>field</th><th><diff</th><th>before</th><th>after</th></tr>')
		for c in cs.changes.order_by('model', 'oid', 'field'):
			body.append('<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(
				c.model, c.oid, c.field, c.diff, c.before, c.after))
		body.append('</table>')
		body.append('<br><br>')
	body.append('</body>')
	body.append('</html>')
	return HttpResponse('\n'.join(body))



# Deprecation wrappers, remove at some point
def start(*args, **kwargs):
	warnings.warn("Don't call history.start() directly, use the history.atomic() context manager", DeprecationWarning)
	_start(*args, **kwargs)

def abort(*args, **kwargs):
	warnings.warn("Don't call history.abort() directly, use the history.atomic() context manager", DeprecationWarning)
	_abort(*args, **kwargs)

def commit(*args, **kwargs):
	warnings.warn("Don't call history.commit() directly, use the history.atomic() context manager", DeprecationWarning)
	_commit(*args, **kwargs)
