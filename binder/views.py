import logging
import time
import json
import io
import re
import os
import hashlib
import datetime
import mimetypes
from collections import defaultdict, namedtuple
from PIL import Image

import django
from django.views.generic import View
from django.core.exceptions import ObjectDoesNotExist, FieldError, ValidationError, FieldDoesNotExist
from django.http import HttpResponse, StreamingHttpResponse, HttpResponseForbidden
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

from .exceptions import BinderException, BinderFieldTypeError, BinderFileSizeExceeded, BinderForbidden, BinderImageError, BinderImageSizeExceeded, BinderInvalidField, BinderIsDeleted, BinderIsNotDeleted, BinderMethodNotAllowed, BinderNotAuthenticated, BinderNotFound, BinderReadOnlyFieldError, BinderRequestError, BinderValidationError, BinderFileTypeIncorrect, BinderInvalidURI
from .router import Router
from . import history



# Haha kill me now
def multiput_get_id(bla):
	return bla['id'] if isinstance(bla, dict) else bla



logger = logging.getLogger(__name__)



class BinderJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, (datetime.datetime, datetime.date)):
			return obj.isoformat()
		if isinstance(obj, set):
			return list(obj)
		return json.JSONEncoder.default(self, obj)

def jsondumps(o, indent=None):
	return json.dumps(o, cls=BinderJSONEncoder, indent=indent)



# Used to truncate request bodies.
def ellipsize(msg, length=2048):
	msglen = len(msg)
	msg = repr(msg)
	if msglen > length:
		msg = msg[:length] + '...'
	msg += ' [{}]'.format(msglen)
	return msg



RelatedModel = namedtuple('RelatedModel', 'fieldname model')



class ModelView(View):
	# Model this is a view for. Mandatory.
	model = None

	# If True, Router().model_view(model) will return this view.
	# Set to False for additional views for the same model.
	# FIXME: this is actually quite kludgy.
	register_for_model = True

	# The route name to use in the URL. String, True, or None.
	# If string, specifies the route name.
	# If True, uses model._model_name()
	# If None, doesn't add a route.
	route = True

	# What regular fields and FKs show up in a GET is controlled by
	# shown_fields and hidden_fields. If shown_fields is a list of fields,
	# only those fields are included in a GET. If shown_fields is None, all
	# fields except those in hidden_fields are included.
	# m2m fields always need to be listed explicitly in m2m_fields.
	# These settings only control GETs. Writability is controlled separately.
	shown_fields = None
	hidden_fields = []
	m2m_fields = []

	# Fields that cannot be written (PUT/POST). Writing them is not an error;
	# their values are silently ignored.
	# The following fields are always excluded for writes:
	#  - id, pk, deleted, _meta
	#  - reverse relations
	#  - file fields (as specified in file_fields)
	unwritable_fields = []

	# Fields to use for ?search=foo. Empty tuple for disabled search.
	# NOTE: only string fields and 'id' are supported.
	# id is hardcoded to be treated as an integer.
	# For anything fancier, override self.search()
	searches = []

	# Fields to allow POST/GET/DELETE files on.
	file_fields = []

	# Pagination limit default and max. Use None for no limit.
	limit_default = 20
	limit_max = None

	# Size limit (in MB, floats ok) of uploaded files.
	# NOTE: files are fully uploaded before this size check is performed, so
	# this is not an adequate protection against DoS attacks. Also, rejecting
	# a file after a potentially lengthy upload is poor UX.
	max_upload_size = 10

	# If set, this will be passed in the meta.comment field in GET replies,
	# for the information of the front-end developer.
	comment = None

	# If True, the (first part of the) request body will be logged at level=debug.
	# Set this to False for endpoints that receive passwords etc.
	log_request_body = True



	#### XXX WARNING XXX
	# dispatch() ensures transactions. If overriding or circumventing dispatch(), you're on your own!
	# Also, a transaction is aborted if and only if post() or whatever raises an exception.
	# If you detect an error and return a HttpResponse(status=400), the transaction is not aborted!
	#### XXX WARNING XXX
	def dispatch(self, request, *args, **kwargs):
		history.start(source='http', user=request.user, uuid=request.request_id, date=None)
		time_start = time.time()
		logger.info('request dispatch; verb={}, user={}/{}, path={}'.
				format(
					request.method,
					request.user.id,
					request.user,
					request.path,
				))
		logger.info('remote_addr={}, X-Real-IP={}, X-Forwarded-For={}'.
				format(
					request.META.get('REMOTE_ADDR', None),
					request.META.get('HTTP_X_REAL_IP', None),
					request.META.get('HTTP_X_FORWARDED_FOR', None),
				))
		logger.info('request parameters: {}'.format(dict(request.GET)))
		logger.debug('cookies: {}'.format(request.COOKIES))

		# Ugh. T1850.
		# In Django, you can't access the raw body after you've accessed POST/FILES. (http/request.py:201, in def body)
		# And Django's csrf middleware fondles request.POST so ouch. (middleware/csrf.py:170, in def process_view)
		# Luckily, this doesn't succeed for application/json POSTs (http/request.py:226, in def _load_post_and_files)
		# So we're good for most requests. For file uploads, we proceed without body logging.
		if not self.log_request_body:
			body = ' censored.'
		elif request.method in ('HEAD', 'GET'):
			body = ' unavailable.'
		else:
			if request.META.get('CONTENT_TYPE', '').lower() == 'application/json':
				body = ': ' + ellipsize(request.body, length=65536)
			else:
				body = ': ' + ellipsize(request.body, length=64)

		logger.debug('body (content-type={}){}'.format(request.META.get('CONTENT_TYPE'), body))

		response = None
		try:
			#### START TRANSACTION
			with transaction.atomic():
				if not kwargs.pop('unauthenticated', False) and not request.user.is_authenticated:
					raise BinderNotAuthenticated()

				if 'method' in kwargs:
					method = kwargs.pop('method')
					response = getattr(self, method)(request, *args, **kwargs)
				elif 'file_field' in kwargs:
					response = self.dispatch_file_field(request, *args, **kwargs)
				elif 'history' in kwargs:
					response = self.view_history(request, *args, **kwargs)
				else:
					response = super().dispatch(request, *args, **kwargs)

				history.commit()
			#### END TRANSACTION
		except BinderException as e:
			e.log()
			response = e.response(request=request)

		logger.info('request response; status={} time={}ms bytes={} queries={}'.
				format(
					response.status_code,
					int((time.time() - time_start) * 1000),
					'?' if response.streaming else len(response.content),
					len(django.db.connection.queries),
				))

		return response



	# Like model._meta.model_name, except it converts camelcase to underscores
	@classmethod
	def _model_name(cls):
		mn = cls.model.__name__
		return ''.join((x + '_' if x.islower() and y.isupper() else x.lower() for x, y in zip(mn, mn[1:] + 'x')))



	# Return a list of RelatedObjects for all _visible_ reverse relations (from both FKs and m2ms).
	def _get_reverse_relations(self):
		return [
			f for f in self.model._meta.get_fields()
			if (f.one_to_one or f.one_to_many or f.many_to_many) and f.auto_created
		]



	# Kinda like model_to_dict() for multiple objects.
	# Return a list of dictionaries, one per object in the queryset.
	# Includes a list of ids for all m2m fields (including reverse relations).
	def _get_objs(self, queryset, request=None):
		# Create a dictionary of {field name: {this object id: [related object ids]}}
		# (one query per field for performance)
		m2m_ids = {}
		for field in self.m2m_fields:
			idmap = defaultdict(list)
			# Wuh, the autogenerated reverse relation is called foo_set, but in values() you need foo? Weird.
			# FIXME: We use explicit related_name everywhere, do we still need this? Maybe for User/Group
			rfield = field[:-4] if field.endswith('_set') else field
			# We could use an additional filter(**{field + '__isnull': False}), but that only seems slower?
			# Hurgh. The queryset is annotated, and the annotation columns show up in the subquery -> Boom. Use list of IDs instead.
			# for this, other in self.model.objects.filter(id__in=queryset).values_list('id', rfield):
			for this, other in self.model.objects.filter(id__in=list(queryset.values_list('id', flat=True))).values_list('id', rfield):
				if other is not None:
					idmap[this].append(other)
			m2m_ids[field] = idmap

		# Serialize the objects, and add in id arrays for m2m fields
		datas = []
		if self.shown_fields is None:
			fields = [f for f in self.model._meta.fields if f.name not in self.hidden_fields]
		else:
			fields = [f for f in self.model._meta.fields if f.name in self.shown_fields]
		for obj in queryset:
			data = {}
			for f in fields:
				if isinstance(f, models.fields.files.FileField):
					file = f.value_from_object(obj)
					if file:
						data[f.name] = Router().model_route(self.model, obj.id, f)
					else:
						data[f.name] = None
				else:
					data[f.name] = f.value_from_object(obj)
			for field, idmap in m2m_ids.items():
				data[field] = idmap[obj.id]
			datas.append(data)

		return datas



	# Kinda like model_to_dict()
	# Fetches the object specified by <id>, and returns a dictionary.
	# Includes a list of ids for all m2m fields (including reverse relations).
	def _get_obj(self, id, request=None):
		return self._get_objs(self.model.objects.filter(pk=id), request=request)[0]



	# Find which objects of which models to include according to <withs> for the objects in <queryset>.
	# returns a dictionary of {related view class: {ids}}.
	def _get_withs(self, withs, ids, request=None):
		if isinstance(ids, django.db.models.query.QuerySet):
			ids = ids.values_list('id', flat=True)
		# Force evaluation of querysets, as nesting too deeply causes problems. See T1850.
		ids = list(ids)

		# Make sure to include A if A.B is specified.
		for w in withs:
			if '.' in w:
				withs.append('.'.join(w.split('.')[:-1]))

		withs = set(withs)
		extras = defaultdict(set)
		extras_mapping = {}

		for w in withs:
			(view, new_ids) = self._get_with(w, ids, request=request)
			if view:
				extras_mapping[w] = view
				extras[view].update(set(new_ids))

		return (extras, extras_mapping)



	def _follow_related(self, fieldspec):
		if not fieldspec:
			return ()

		if isinstance(fieldspec, str):
			fieldspec = fieldspec.split('.')

		fieldname, *fieldspec = fieldspec

		try:
			field = self.model._meta.get_field(fieldname)
		except FieldDoesNotExist:
			raise BinderRequestError('Unknown field {{{}}}.{{{}}}.'.format(self.model.__name__, fieldname))

		if not field.is_relation:
			raise BinderRequestError('Field is not a related object {{{}}}.{{{}}}.'.format(self.model.__name__, fieldname))

		if isinstance(field, django.db.models.fields.reverse_related.ForeignObjectRel):
			# Reverse relations
			related_model = field.related_model
		else:
			# Forward relations
			related_model = field.remote_field.model

		return (RelatedModel(fieldname, related_model),) + Router().model_view(related_model)()._follow_related(fieldspec)



	def _get_with(self, wth, ids, request=None):
		head, *tail = wth.split('.')

		next = self._follow_related(head)[0].model
		ids = list(self.model.objects.filter(id__in=ids).values_list(head + '__id', flat=True))
		view = Router().model_view(next)

		if not tail:
			return (view, ids)
		else:
			return view()._get_with('.'.join(tail), ids, request=request)



	def _parse_filter(self, queryset, field, value, partial=''):
		head, *tail = field.split('.')

		if tail:
			next = self._follow_related(head)[0].model
			view = Router().model_view(next)()
			return view._parse_filter(queryset, '.'.join(tail), value, partial + head + '__')

		invert = False
		try:
			head, qualifier = head.split(':', 1)
			if qualifier == 'not':
				qualifier = None
				invert = True
			elif qualifier.startswith('not:'):
				qualifier = qualifier[4:]
				invert = True
		except ValueError:
			qualifier = None

		try:
			field = self.model._meta.get_field(head)
		except models.fields.FieldDoesNotExist:
			raise BinderRequestError('Unknown field in filter: {{{}}}.{{{}}}.'.format(self.model.__name__, head))

		clean_value = []

		# FIXME: Support __isnull?
		if qualifier in ('in', 'range'):
			values = value.split(',')
			if qualifier == 'range':
				if len(values) != 2:
					raise BinderRequestError('Range requires exactly 2 values for {{{}}}.{{{}}}.'
							.format(self.model.__name__, head))
		else:
			values = [value]

		if isinstance(field, models.IntegerField) or isinstance(field, models.ForeignKey) or isinstance(field, models.AutoField):
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by ?.some_int:in=
				if v == '':
					continue
				try:
					clean_value.append(int(v))
				except ValueError:
					raise BinderRequestError('Invalid value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
		elif isinstance(field, models.DateField) or isinstance(field, models.DateTimeField):
			# FIXME: fix date/datetime issues. Maybe allow __startswith? And __year etc?
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range')
			for v in values:
				if not re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', v):
					raise BinderRequestError('Invalid YYYY-MM-DD value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
			clean_value = values
		elif isinstance(field, models.BooleanField):
			allowed_qualifiers = (None,)
			for v in values:
				if v == 'true':
					clean_value.append(True)
				elif v == 'false':
					clean_value.append(False)
				else:
					raise BinderRequestError('Invalid value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
		elif isinstance(field, models.CharField) or isinstance(field, models.TextField):
			allowed_qualifiers = (None, 'in', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'exact', 'search')
			clean_value = values
		else:
			raise BinderRequestError('Filtering not supported for type {} ({{{}}}.{{{}}}).'
					.format(field.__class__.__name__, self.model.__name__, head))

		if qualifier not in ('in', 'range'):
			clean_value = clean_value[0]

		if qualifier not in allowed_qualifiers:
			raise BinderRequestError('Qualifier {} not supported for type {} ({{{}}}.{{{}}}).'
					.format(qualifier, field.__class__.__name__, self.model.__name__, head))

		suffix = '__' + qualifier if qualifier else ''
		if invert:
			return queryset.exclude(**{partial + head + suffix: clean_value})
		else:
			return queryset.filter(**{partial + head + suffix: clean_value})



	def _parse_order_by(self, queryset, field, partial=''):
		head, *tail = field.split('.')

		if tail:
			next = self._follow_related(head)[0].model
			view = Router().model_view(next)()
			return view._parse_order_by(queryset, '.'.join(tail), partial + head + '__')

		try:
			self.model._meta.get_field(head)
		except models.fields.FieldDoesNotExist:
			raise BinderRequestError('Unknown field in order_by: {{{}}}.{{{}}}.'.format(self.model.__name__, head))

		return (queryset, partial + head)



	def search(self, queryset, search, request=None):
		if not search:
			return queryset

		if not self.searches:
			raise BinderRequestError('No search fields defined for this view.')

		q = Q()
		for s in self.searches:
			if s == 'id':
				try:
					q |= Q(id=int(search))
				except ValueError:
					pass
			else:
				q |= Q(**{s: search})
		return queryset.filter(q)



	def filter_deleted(self, queryset, pk, deleted, request=None):
		if pk:
			return queryset

		if deleted is None:
			try:
				return queryset.filter(deleted=False)
			except FieldError:
				return queryset

		if deleted == 'true':
			return queryset

		if deleted == 'only':
			try:
				return queryset.filter(deleted=True)
			except FieldError:
				raise BinderRequestError('This entity has no soft-delete attribute.')

		raise BinderRequestError('Invalid value: deleted={{{}}}.'.format(request.GET.get('deleted')))



	def _paginate(self, queryset, request):
		limit = self.limit_default
		if request.GET.get('limit') == 'none':
			limit = None
		elif 'limit' in request.GET:
			try:
				limit = int(request.GET.get('limit'))
				if limit < 0:
					raise BinderRequestError('Limit must be nonnegative.')
			except ValueError:
				raise BinderRequestError('Invalid characters in limit.')

		if self.limit_max:
			if not limit or limit > self.limit_max:
				raise BinderRequestError('Limit exceeds maximum of {} for this view.'.format(self.limit_max))

		try:
			offset = int(request.GET.get('offset') or 0)
			if offset < 0:
				raise BinderRequestError('Offset must be nonnegative.')
		except ValueError:
			raise BinderRequestError('Invalid characters in offset.')

		if limit is not None:
			queryset = queryset[offset:offset+limit]

		return queryset



	def get(self, request, pk=None, withs=None):
		meta = {}
		queryset = self.model.objects.all()
		if pk:
			queryset = queryset.filter(pk=int(pk))

		# No parameter repetition. Should be extended to .params too after filters have been refactored.
		for k, v in request.GET.lists():
			if not k.startswith('.') and len(v) > 1:
				raise BinderRequestError('Query parameter `{}` may not be repeated.'.format(k))

		#### soft-deletes
		queryset = self.filter_deleted(queryset, pk, request.GET.get('deleted'), request)

		#### filters
		filters = {k.lstrip('.'): v for k, v in request.GET.lists() if k.startswith('.')}
		for field, values in filters.items():
			for v in values:
				queryset = self._parse_filter(queryset, field, v).distinct()

		#### search
		if 'search' in request.GET:
			queryset = self.search(queryset, request.GET['search'], request)

		#### order_by
		order_bys = list(filter(None, request.GET.get('order_by', '').split(',')))
		if order_bys:
			orders = []
			for o in order_bys:
				if o.startswith('-'):
					queryset, order = self._parse_order_by(queryset, o[1:], partial='-')
				else:
					queryset, order = self._parse_order_by(queryset, o)
				orders.append(order)
			queryset = queryset.order_by(*orders)

		if not pk:
			meta['total_records'] = queryset.count()

		queryset = self._paginate(queryset, request)

		#### with
		if withs is None:
			withs = list(filter(None, request.GET.get('with', '').split(',')))
		raw_extras, extras_mapping = self._get_withs(withs, queryset, request=request)
		extras = {}
		# FIXME: delegate this to a router or something
		for view, with_ids in raw_extras.items():
			view = view()
			os = view._get_objs(view.model.objects.filter(id__in=with_ids))
			extras[view._model_name()] = os
		extras_mapping = {fk: view()._model_name() for fk, view in extras_mapping.items()}

		data = self._get_objs(queryset, request=request)
		if pk:
			if data:
				data = data[0]
			else:
				raise BinderNotFound()

		if self.comment:
			meta['comment'] = self.comment

		debug = {'request_id': request.request_id}
		if django.conf.settings.DEBUG and 'debug' in request.GET:
			debug['queries'] = ['{}s: {}'.format(q['time'], q['sql'].replace('"', '')) for q in django.db.connection.queries]
			debug['query_count'] = len(django.db.connection.queries)

		response_data = {'data': data, 'with': extras, 'with_mapping': extras_mapping, 'meta': meta, 'debug': debug}

		response_data = jsondumps(response_data)
		return HttpResponse(response_data, content_type='application/json')



	# Deserialize JSON to Django Model objects.
	# obj: Model object to update (for PUT), newly created object (for POST)
	# values: Python dict of {field name: value} (parsed JSON)
	# Output: Python dict representation of the updated object
	def _store(self, obj, values, request, ignore_unknown_fields=False):
		deferred_m2ms = {}
		ignored_fields = []
		validation_errors = defaultdict(list)

		def store_field(obj, field, value, request):
			try:
				func = getattr(self, '_store__' + field)
			except AttributeError:
				func = self._store_field
			return func(obj, field, value, request)

		for field, value in values.items():
			try:
				res = store_field(obj, field, value, request)
				if isinstance(res, list):
					deferred_m2ms[field] = res
			except BinderInvalidField:
				if not ignore_unknown_fields:
					raise
			except BinderReadOnlyFieldError:
				ignored_fields.append(field)
			except BinderValidationError as ve:
				for f, e in ve.validation_errors.items():
					validation_errors[f] += e

		try:
			obj.full_clean()
		except ValidationError as ve:
			for f, el in ve.error_dict.items():
				validation_errors[f] += sum([e.messages for e in el], [])

		# full_clean() doesn't check nullability (WHY?), so do it here. See T2989.
		for f in obj._meta.fields:
			name = f.name + ('_id' if isinstance(f, models.ForeignKey) or isinstance(f, models.OneToOneField) else '')
			if not f.primary_key and not f.null and getattr(obj, name) is None:
				validation_errors[f.name] = ['This field cannot be null.']

		if validation_errors:
			raise BinderValidationError(validation_errors, object=obj)

		obj.save()

		for field, value in deferred_m2ms.items():
			# Can't use isinstance() because apparantly ManyToManyDescriptor is a subclass of
			# ReverseManyToOneDescriptor. Yes, really.
			if getattr(obj._meta.model, field).__class__ == models.fields.related.ReverseManyToOneDescriptor:
				#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
				if any(v for v in value if v < 0):
					continue
				# If the m2m to be set is actually a reverse FK relation, we need to do extra magic.
				# We figure out if the remote objects are added or removed. The added ones, we modify/save
				# explicitly rather than using the reverse relation manager, otherwise the history layer
				# doesn't see the changes. The same goes for the removed objects, except there we also
				# DELETE them if the FK is non-nullable. Interesting stuff.
				obj_field = getattr(obj, field)
				old_ids = set(obj_field.values_list('id', flat=True))
				new_ids = set(value)
				for rmobj in obj_field.model.objects.filter(id__in=old_ids - new_ids):
					if obj_field.field.null:
						setattr(rmobj, obj_field.field.name, None)
					else:
						rmobj.delete()
				for addobj in obj_field.model.objects.filter(id__in=new_ids - old_ids):
					setattr(addobj, obj_field.field.name, obj)
					addobj.save()
			elif field in [f.name for f in self._get_reverse_relations()]:
				#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
				if any(v for v in value if v < 0):
					continue
				setattr(obj, field, value)
			else:
				setattr(obj, field, value)

		data = self._get_obj(obj.pk, request=request)
		data['_meta'] = {'ignored_fields': ignored_fields}
		return data



	# Override _store_field example for a "FOO" field
	# Try to override setters using these methods, if at all possible.
	# def _store__FOO(self, obj, field, value, request):
	#	return self._store_field(obj, field, value, request)



	# Store <value> on <obj>.<field>
	# If the field is a m2m, it should do all validation and then return a list of ids
	# which will be actually set when the object is known to be saved.
	# Otherwise, return False.
	def _store_field(self, obj, field, value, request):
		# Unwritable fields
		if field in self.unwritable_fields + ['id', 'pk', 'deleted', '_meta'] + self.file_fields:
			raise BinderReadOnlyFieldError(self.model.__name__, field)

		# Regular fields and FKs
		for f in self.model._meta.fields:
			if f.name == field:
				if isinstance(f, models.ForeignKey):
					if not (value is None or isinstance(value, int)):
						raise BinderFieldTypeError(self.model.__name__, field)
					setattr(obj, f.attname, value)
				elif isinstance(f, models.IntegerField):
					if value is None or value == '':
						value = None
					else:
						try:
							value = int(value)
						except ValueError:
							raise BinderValidationError({f.name: ['This value must be an integral number.']}, object=obj)
					setattr(obj, f.attname, value)
				else:
					try:
						f.to_python(value)
					except (ValidationError, TypeError):
						raise BinderFieldTypeError(self.model.__name__, field)
					setattr(obj, f.attname, value)
				return False

		# m2ms
		for f in list(self.model._meta.many_to_many) + list(self._get_reverse_relations()):
			if f.name == field:
				if not (isinstance(value, list) and all(isinstance(v, int) for v in value)):
					raise BinderFieldTypeError(self.model.__name__, field)
				# FIXME
				# Check if the ids being saved as m2m actually exist. This kinda sucks, it would be much
				# better to have this handled by the DB transaction layer. Which DOES actually check and
				# enforce this, but on error this raises an exception at a point where we can't catch it.
				# So yeah, we kludge around here. :(
				#ids = set(value)
				#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
				ids = set(v for v in value if v > 0)
				ids -= set(obj._meta.get_field(field).remote_field.model.objects.filter(id__in=ids).values_list('id', flat=True))
				if ids:
					raise BinderValidationError({field: ['{} instances {} do not exist'.format(getattr(obj, field).model.__name__, list(ids))]})
				return value

		raise BinderInvalidField(self.model.__name__, field)



	def _require_model_perm(self, perm_type, request, pk=None):
		if hasattr(self, 'perms_via'):
			model = self.perms_via
		else:
			model = self.model

		if not model:
			raise BinderForbidden(None, request.user)

		perm = '{}.{}_{}'.format(model._meta.app_label, perm_type, model.__name__.lower())
		if not request.user.has_perm(perm):
			raise BinderForbidden(perm, request.user)

		logger.debug('passed permission check: {}'.format(perm))



	def _obj_diff(self, old, new, name):
		if isinstance(old, dict) or isinstance(new, dict):
			changes = []
			for k, v in old.items():
				if k in new:
					changes += self._obj_diff(old[k], new[k], '{}.{}'.format(name, k))
				else:
					changes.append('deleted {}.{}: {}'.format(name, k, repr(v)))
			for k, v in new.items():
				if not k in old:
					changes.append('  added {}.{}: {}'.format(name, k, repr(v)))
			return changes

		if isinstance(old, list) or isinstance(new, list):
			changes = []
			for i in range(0, min(len(old), len(new))):
				changes += self._obj_diff(old[i], new[i], '{}[{}]'.format(name, i))
			for i in range(len(old), len(new)):
				changes.append('  added {}[{}]: {}'.format(name, i, repr(new[i])))
			for i in range(len(new), len(old)):
				changes.append('deleted {}[{}]: {}'.format(name, i, repr(old[i])))
			return changes

		if old != new:
			return ['changed {}: {} -> {}'.format(name, repr(old), repr(new))]
		return []



	def multi_put(self, request):
		logger.info('ACTIVATING THE MULTI-PUT!!!1!')

		try:
			body = json.loads(request.body.decode())
		except ValueError as e:
			raise BinderRequestError('JSON parse error: {}.'.format(str(e)))

		if not 'data' in body:
			raise BinderRequestError('missing data')

		if not isinstance(body['data'], list):
			raise BinderRequestError('data should be a list')

		if 'with' in body and not isinstance(body['with'], dict):
			raise BinderRequestError('with should be a dict')

		# Put data and with on one big pile, that's easier for us
		data = body.get('with', {})
		data[self._model_name()] = body['data']

		# Sort object values by model/id
		objects = {}
		for modelname, objs in data.items():
			if not isinstance(objs, list):
				raise BinderRequestError('with.{} value should be a list')

			try:
				model = Router().name_models[modelname]
			except KeyError:
				raise BinderRequestError('with.{} is not a valid model name'.format(modelname))

			for idx, obj in enumerate(objs):
				if not isinstance(obj, dict):
					raise BinderRequestError('with.{}[{}] should be a dictionary'.format(modelname, idx))
				if not 'id' in obj:
					raise BinderRequestError('missing id in with.{}[{}]'.format(modelname, idx))
				if not isinstance(obj['id'], int):
					raise BinderRequestError('non-numeric id in with.{}[{}]'.format(modelname, idx))

				objects[(model, obj['id'])] = obj

		# Figure out dependencies
		logger.info('Resolving dependencies for {} objects'.format(len(objects)))
		dependencies = {}
		for (model, mid), values in objects.items():
			deps = defaultdict(list)
			for field in model._meta.fields:
				if isinstance(field, models.ForeignKey):
					if field.name in values:
						if values[field.name] is not None:
							if not isinstance(values[field.name], int):
								raise BinderRequestError('with.{}.{} should be an integer'.format(model.__name__, field.name))
							deps[field.related_model].append(values[field.name])

			for field in model._meta.many_to_many:
				if field.name in values:
					if not isinstance(values[field.name], list):
						raise BinderRequestError('with.{}.{} should be a list'.format(model.__name__, field.name))
					for i, v in enumerate(values[field.name]):
						if not isinstance(multiput_get_id(v), int):
							pass
					deps[field.related_model] += (values[field.name])

			dependencies[(model, mid)] = set()
			for r_model, r_ids in deps.items():
				for r_id in r_ids:
					r_id = multiput_get_id(r_id)
					if isinstance(r_id, int) and r_id < 0 and not (r_model, r_id) in objects:
						raise BinderRequestError('with.{} refers to unspecified {}[{}]'.format(
								model.__name__, r_model.__name__, r_id))
					if (r_model, r_id) in objects:
						dependencies[(model, mid)].add((r_model, r_id))

		ordered_objects = []
		while dependencies:
			before = len(dependencies)
			for obj, deps in list(dependencies.items()):
				if not deps:
					ordered_objects.append(obj)
					del dependencies[obj]
					for d in dependencies.values():
						if obj in d:
							d.remove(obj)
			if len(dependencies) == before:
				raise BinderRequestError('No progress in dependency resolution! Cyclic dependencies?')

		new_id_map = {}
		for model, oid in ordered_objects:
			values = objects[(model, oid)]
			logger.info('Saving {} {}'.format(model.__name__, oid))

			if oid >= 0:
				try:
					obj = model.objects.get(pk=oid)
				except ObjectDoesNotExist:
					raise BinderNotFound('{}[{}]'.format(model.__name__, oid))
				if hasattr(obj, 'deleted') and obj.deleted:
					raise BinderIsDeleted()
			else:
				obj = model()

			values = dict(values)
			del values['id']

			# FIXME
			for field in model._meta.fields:
				if isinstance(field, models.ForeignKey):
					if field.name in values:
						if values[field.name] is not None and values[field.name] < 0:
							values[field.name] = new_id_map[(field.related_model, values[field.name])]

			for field in model._meta.many_to_many:
				if field.name in values:
					values[field.name] = [(new_id_map[(field.related_model, multiput_get_id(i))] if multiput_get_id(i) < 0 else i) for i in values[field.name]]

			for field in [f for f in model._meta.get_fields() if f.one_to_many]:
				if field.name in values:
					values[field.name] = [multiput_get_id(i) for i in values[field.name] if multiput_get_id(i) >= 0]

			Router().model_view(model)()._store(obj, values, request)
			if oid < 0:
				new_id_map[(model, oid)] = obj.id
				logger.info('Saved as id {}'.format(obj.id))

		bla = defaultdict(list)
		for (model, oid), nid in new_id_map.items():
			bla[Router().model_view(model)()._model_name()].append((oid, nid))

		return HttpResponse(jsondumps({'idmap': bla}), content_type='application/json')



	def put(self, request, pk=None):
		self._require_model_perm('change', request, pk)

		if pk is None:
			return self.multi_put(request)

		try:
			values = json.loads(request.body.decode())
		except ValueError as e:
			raise BinderRequestError('JSON parse error: {}.'.format(str(e)))

		try:
			obj = self.model.objects.get(pk=int(pk))
			old = self._get_obj(int(pk), request)
		except ObjectDoesNotExist:
			raise BinderNotFound()

		if hasattr(obj, 'deleted') and obj.deleted:
			raise BinderIsDeleted()

		data = self._store(obj, values, request)

		new = dict(data)
		new.pop('_meta', None)
		logger.info('PUT updated {} #{}'.format(self._model_name(), pk))
		for c in self._obj_diff(old, new, '{}[{}]'.format(self._model_name(), pk)):
			logger.debug('PUT ' + c)

		return HttpResponse(jsondumps(data), content_type='application/json')



	def patch(self, request, pk=None):
		return self.put(request, pk)



	def post(self, request, pk=None):
		self._require_model_perm('add', request)

		if pk is not None:
			return self.delete(request, pk, undelete=True)

		try:
			values = json.loads(request.body.decode())
		except ValueError as e:
			raise BinderRequestError('JSON parse error: {}.'.format(str(e)))

		data = self._store(self.model(), values, request)

		new = dict(data)
		new.pop('_meta', None)
		logger.info('POST created {} #{}'.format(self._model_name(), data['id']))
		for c in self._obj_diff({}, new, '{}[{}]'.format(self._model_name(), data['id'])):
			logger.debug('POST ' + c)

		return HttpResponse(jsondumps(data), content_type='application/json')



	def delete(self, request, pk=None, undelete=False):
		if not undelete:
			self._require_model_perm('delete', request)

		if pk is None:
			raise BinderMethodNotAllowed()

		if request.body not in (b'', b'{}'):
			raise BinderRequestError('{}DELETE body must be empty or empty json object.'.format('UN' if undelete else ''))

		try:
			obj = self.model.objects.get(pk=int(pk))
		except ObjectDoesNotExist:
			raise BinderNotFound()

		self.soft_delete(obj, undelete, request)
		logger.info('{}DELETEd {} #{}'.format('UN' if undelete else '', self._model_name(), pk))

		return HttpResponse(status=204)  # No content



	def soft_delete(self, obj, undelete=False, request=None):
		try:
			if obj.deleted and not undelete:
				raise BinderIsDeleted()
			if not obj.deleted and undelete:
				raise BinderIsNotDeleted()
		except AttributeError:
			raise BinderMethodNotAllowed()

		obj.deleted = not undelete
		obj.save()



	def dispatch_file_field(self, request, pk=None, file_field=None):
		if not request.method in ('GET', 'POST', 'DELETE'):
			raise BinderMethodNotAllowed()

		try:
			obj = self.model.objects.get(pk=int(pk))
		except ObjectDoesNotExist:
			raise BinderNotFound()

		file_field_name = file_field
		file_field = getattr(obj, file_field_name)

		if request.method == 'GET':
			if not file_field:
				raise BinderNotFound(file_field_name)

			guess = mimetypes.guess_type(file_field.path)
			guess = guess[0] if guess and guess[0] else 'application/octet-stream'
			try:
				resp = StreamingHttpResponse(open(file_field.path, 'rb'), content_type=guess)
			except FileNotFoundError:
				logger.error('Expected file {} not found'.format(file_field.path))
				raise BinderNotFound(file_field_name)

			if 'download' in request.GET:
				filename = self.filefield_get_name(instance=obj, request=request, file_field=file_field)
				if 'prefix' in request.GET:
					filename = request.GET['prefix'] + ' - ' + filename
				resp['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
			return resp

		if request.method == 'POST':
			self._require_model_perm('change', request)

			try:
				# Take an arbitrary uploaded file
				file = next(request.FILES.values())
			except StopIteration:
				raise BinderRequestError('File POST should use multipart/form-data (with an arbitrary key for the file data).')

			if file.size > self.max_upload_size * 10**6:
				raise BinderFileSizeExceeded(self.max_upload_size)

			field = self.model._meta.get_field(file_field_name)
			if isinstance(field, models.fields.files.ImageField):
				try:
					img = Image.open(file)
				except Exception as e:
					raise BinderImageError(str(e))

				format = img.format.lower()
				if not format in ('png', 'gif', 'jpeg'):
					raise BinderFileTypeIncorrect([{'extension': t, 'mimetype': 'image/' + t} for t in ['jpeg', 'png', 'gif']])

				width, height = img.size
				# FIXME: hardcoded max
				if width > 4096 or height > 4096:
					raise BinderImageSizeExceeded(4096, 4096)

				# FIXME: hardcoded max
				if width > 512 or height > 512:
					img.thumbnail((512, 512), Image.ANTIALIAS)
					logger.info('image dimensions ({}x{}) exceeded (512, 512), resizing.'.format(width, height))
					file = io.BytesIO()
					if img.mode not in ["1", "L", "P", "RGB", "RGBA"]:
						img = img.convert("RGB")
					img.save(file, 'png')
					format = 'png'

				filename = '{}.{}'.format(obj.id, format)
			else:
				if file.name.find('.') != -1:
					filename = '{}.{}'.format(obj.id, file.name.split('.')[-1])
				else:
					filename = str(obj.id)

			# FIXME: duplicate code
			if file_field:
				try:
					old_hash = hashlib.sha256()
					for c in file_field.file.chunks():
						old_hash.update(c)
					old_hash = old_hash.hexdigest()
				except FileNotFoundError:
					logger.warning('Old file {} missing!'.format(file_field))
					old_hash = None
			else:
				old_hash = None

			file_field.delete()
			file_field.save(filename, django.core.files.File(file))
			obj.save()

			# FIXME: duplicate code
			new_hash = hashlib.sha256()
			for c in file_field.file.chunks():
				new_hash.update(c)
			new_hash = new_hash.hexdigest()

			logger.info('POST updated {}[{}].{}: {} -> {}'.format(self._model_name(), pk, file_field_name, old_hash, new_hash))
			path = Router().model_route(self.model, obj.id, field)
			return HttpResponse(jsondumps( {"data": {file_field_name: path}} ))

		if request.method == 'DELETE':
			self._require_model_perm('change', request)
			if not file_field:
				raise BinderIsDeleted()

			# FIXME: duplicate code
			old_hash = hashlib.sha256()
			for c in file_field.file.chunks():
				old_hash.update(c)
			old_hash = old_hash.hexdigest()

			file_field.delete()

			logger.info('DELETEd {}[{}].{}: {}'.format(self._model_name(), pk, file_field_name, old_hash))
			return HttpResponse(jsondumps( {"data": {file_field_name: None}} ))



	def filefield_get_name(self, instance=None, request=None, file_field=None):
		try:
			method = getattr(self, 'filefield_get_name_' + file_field.field.name)
		except AttributeError:
			return os.path.basename(file_field.path)
		return method(instance=instance, request=request, file_field=file_field)



	def view_history(self, request, pk=None, **kwargs):
		if request.method != 'GET':
			raise BinderMethodNotAllowed()

		if not django.conf.settings.ENABLE_DEBUG_ENDPOINTS:
			logger.warning('Debug endpoints disabled.')
			return HttpResponseForbidden('Debug endpoints disabled.')

		changesets = history.Changeset.objects.filter(id__in=set(history.Change.objects.filter(model=self.model.__name__, oid=pk).values_list('changeset_id', flat=True)))
		if kwargs['history'] == 'debug':
			return history.view_changesets_debug(request, changesets.order_by('-id'))
		else:
			return history.view_changesets(request, changesets.order_by('-id'))



def api_catchall(request):
	try:
		# Need to raise/catch the exception, so the traceback code works
		raise BinderInvalidURI(request.path)
	except BinderException as e:
		e.log()
		return e.response(request=request)



def debug_changesets_24h(request):
	if request.method != 'GET':
		raise BinderMethodNotAllowed()

	if not request.user.is_authenticated:
		logger.warning('Not authenticated.')
		return HttpResponseForbidden('Not authenticated.')

	if not django.conf.settings.ENABLE_DEBUG_ENDPOINTS:
		logger.warning('Debug endpoints disabled.')
		return HttpResponseForbidden('Debug endpoints disabled.')

	changesets = history.Changeset.objects.filter(date__gte=timezone.now() - datetime.timedelta(days=1))
	return history.view_changesets_debug(request, changesets.order_by('-id'))
