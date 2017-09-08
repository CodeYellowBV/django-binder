import logging
import threading

from django.db import models
from django.utils import timezone
from django.http import HttpResponse
from django.contrib.auth.models import User
from django.conf import settings

from .json import jsondumps, JsonResponse



class Changeset(models.Model):
	source = models.CharField(max_length=32)
	user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='changesets')
	date = models.DateTimeField(default=timezone.now)
	uuid = models.CharField(max_length=36, blank=True, null=True)

	def __str__(self):
		uuid = self.uuid[:8] if self.uuid else None
		username = self.user.username if self.user else None
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



class _Transaction(threading.local):
	def __init__(self):
		logger.info('Creating new Transaction for thread {}'.format(threading.current_thread().name))

	user = None
	uuid = None
	date = None
	source = None
	started = False
	changes = {}

Transaction = _Transaction()



class NewInstanceField:
	pass

class DeferredM2M:
	pass



def start(source=None, user=None, uuid=None, date=None):
	if source is None:
		raise ValueError('source may not be None')

	if date is None:
		date = timezone.now()

	if Transaction.started:
		raise RuntimeError('called Transaction.start() while there is an open transaction')

	Transaction.source = source
	Transaction.user = user
	Transaction.uuid = uuid
	Transaction.date = date
	Transaction.started = True
	Transaction.changes.clear()



# old can be NewInstanceField, which will translate to None on commit.
# old and new can be DeferredM2M. But only for actual m2m fields or SHIT WILL BREAK.
def change(model, oid, field, old, new):
	# FK fields on newly created objects cause annoyances. Ignore them.
	if oid is NewInstanceField:
		return
	hid = model, oid, field

	# Re-use old old value (so we accumulate all changes in one)
	if hid in Transaction.changes:
		old = Transaction.changes[hid][0]
	elif old is DeferredM2M:
		# If we haven't seen this field before, and it's a m2m of
		# unknown value, we need to get the value now.
		#
		# The target model may be a non-Binder model (e.g. User), so lbyl.
		if hasattr(model, 'binder_serialize_m2m_field'):
			old = model(id=oid).binder_serialize_m2m_field(field)

	Transaction.changes[hid] = old, new, False



def m2m_diff(old, new):
	return sorted(old - new), sorted(new - old), True



# FIXME: use bulk inserts for efficiency.
def commit():
	if not Transaction.started:
		raise RuntimeError('called Transaction.commit() while there is no open transaction')
	Transaction.started = False

	# Fill in the deferred m2ms
	for (model, oid, field), (old, new, diff) in Transaction.changes.items():
		if new is DeferredM2M:
			# The target model may be a non-Binder model (e.g. User), so lbyl.
			if hasattr(model, 'binder_serialize_m2m_field'):
				new = model(id=oid).binder_serialize_m2m_field(field)
				Transaction.changes[model, oid, field] = m2m_diff(old, new)

	# Filter non-changes
	Transaction.changes = {idx: (old, new, diff) for idx, (old, new, diff) in Transaction.changes.items() if old != new}

	if not Transaction.changes:
		return

	user = Transaction.user if Transaction.user and not Transaction.user.is_anonymous else None

	changeset = Changeset(
		source=Transaction.source,
		user=user,
		date=Transaction.date,
		uuid=Transaction.uuid,
	)
	changeset.save()

	for (model, oid, field), (old, new, diff) in Transaction.changes.items():
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

	Transaction.changes.clear()



def abort():
	if not Transaction.started:
		raise RuntimeError('called Transaction.abort() while there is no open transaction')
	Transaction.started = False
	Transaction.changes.clear()



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
	for u in User.objects.filter(id__in=userids):
		users.append({'id': u.id, 'username': u.username, 'email': u.email, 'first_name': u.first_name, 'last_name': u.last_name})

	return JsonResponse({'data': data, 'with': {'user': users}})



def view_changesets_debug(request, changesets):
	body = ['<html>', '<head>', '<style type="text/css">td {padding: 0px 20px;} th {padding: 0px 20px;}</style>', '</head>', '<body>']
	for cs in changesets:
		username = cs.user.username if cs.user else None
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
