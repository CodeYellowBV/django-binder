import logging
import time
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
from django.http.request import RawPostDataException
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.db import transaction

from .exceptions import BinderException, BinderFieldTypeError, BinderFileSizeExceeded, BinderForbidden, BinderImageError, BinderImageSizeExceeded, BinderInvalidField, BinderIsDeleted, BinderIsNotDeleted, BinderMethodNotAllowed, BinderNotAuthenticated, BinderNotFound, BinderReadOnlyFieldError, BinderRequestError, BinderValidationError, BinderFileTypeIncorrect, BinderInvalidURI
from . import history
from .json import JsonResponse, jsonloads



# Haha kill me now
def multiput_get_id(bla):
	return bla['id'] if isinstance(bla, dict) else bla

# Primary keys are a bit special, they're NOT NULL, but .save() populates them.
# So when checking for not null constraint fails, we ignore primary keys.
# The same holds for auto_now and auto_now_add fields. (like created_at and updated_at)
def is_filled_upon_save(field):
	return field.primary_key or getattr(field, 'auto_now_add', False) or getattr(field, 'auto_now', False)

logger = logging.getLogger(__name__)



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
	# Model this is a view for. Use None for views not tied to a particular model.
	model = None

	# If True, Router().model_view(model) will return this view.
	# Set to False for additional views for the same model.
	# FIXME: this is actually quite kludgy.
	register_for_model = True

	# The route name to use in the URL. String, True, or None.
	# If string, specifies the route name.
	# If True, uses model._model_name() (model=None -> no route)
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
	#
	# NOTE: Unwritability also disables the in-Binder not-NULL check.
	# See the nullability check in self._store() (search for T9646)
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

	# The router object through which this view was invoked.  Will
	# be set by dispatch().
	router = None

	# Images over this width/height get scaled down.
	# None disables resizing.
	# 123 limits size to 123x123 for all ImageFields on this model.
	# (123,456) limits size to 123x456 on all ImageFields.
	# {'foo': 123, 'bar': 456} limits size to 123x123 on field foo and 456x456 on bar.
	# A dict will KeyError if you don't specify all ImageFields. Or use:
	# collections.defaultdict(lambda: 512, foo=1024)
	image_resize_threshold = 512



	#### XXX WARNING XXX
	# dispatch() ensures transactions. If overriding or circumventing dispatch(), you're on your own!
	# Also, a transaction is aborted if and only if post() or whatever raises an exception.
	# If you detect an error and return a HttpResponse(status=400), the transaction is not aborted!
	#### XXX WARNING XXX
	def dispatch(self, request, *args, **kwargs):
		self.router = kwargs.pop('router')
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

		if not self.log_request_body:
			body = ' censored.'
		else:
			# FIXME: ugly workaround, remove when Django bug fixed
			# Try/except because https://code.djangoproject.com/ticket/27005
			try:
				if request.META.get('CONTENT_TYPE', '').lower() == 'application/json':
					body = ': ' + ellipsize(request.body, length=65536)
				else:
					body = ': ' + ellipsize(request.body, length=64)
			except RawPostDataException:
				body = ' unavailable.'

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
			history.abort()
		except:
			history.abort()
			raise

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
	def _get_objs(self, queryset, request):
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
			for this, other in self.model.objects.filter(pk__in=list(queryset.values_list('pk', flat=True))).values_list('pk', rfield):
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
					file = getattr(obj, f.attname)
					if file:
						# {router-view-instance}
						data[f.name] = self.router.model_route(self.model, obj.id, f)
					else:
						data[f.name] = None
				else:
					data[f.name] = getattr(obj, f.attname)
			for field, idmap in m2m_ids.items():
				# TODO: Don't require OneToOneFields in the m2m_fields list
				if isinstance(self.model._meta.get_field(field), models.OneToOneRel):
					assert(len(idmap[obj.id]) <= 1)
					data[field] = idmap[obj.id][0] if len(idmap[obj.id]) == 1 else None
				else:
					data[field] = idmap[obj.id]
			data['id'] = data.pop(self.model._meta.pk.name)
			datas.append(data)

		return datas



	# Kinda like model_to_dict()
	# Fetches the object specified by <id>, and returns a dictionary.
	# Includes a list of ids for all m2m fields (including reverse relations).
	def _get_obj(self, id, request):
		return self._get_objs(self.model.objects.filter(pk=id), request=request)[0]



	# Find which objects of which models to include according to <withs> for the objects in <queryset>.
	# returns two dictionaries:
	# - withs: { related_modal_name: [ids]}
	# - mappings: { with_name: related_model_name}
	def _get_withs(self, pks, withs, request):
		if withs is None and request is not None:
			withs = list(filter(None, request.GET.get('with', '').split(',')))

		if isinstance(pks, django.db.models.query.QuerySet):
			pks = pks.values_list('pk', flat=True)
		# Force evaluation of querysets, as nesting too deeply causes problems. See T1850.
		pks = list(pks)

		# Make sure to include A if A.B is specified.
		for w in withs:
			if '.' in w:
				withs.append('.'.join(w.split('.')[:-1]))

		withs = set(withs)
		extras = defaultdict(set)
		extras_mapping = {}

		for w in withs:
			(view, new_ids) = self._get_with(w, pks, request=request)
			if view:
				extras_mapping[w] = view
				extras[view].update(set(new_ids))

		extras_dict = {}
		# FIXME: delegate this to a router or something
		for view, with_pks in extras.items():
			view = view()
			# {router-view-instance}
			view.router = self.router
			os = view._get_objs(view.get_queryset(request).filter(pk__in=with_pks), request=request)
			extras_dict[view._model_name()] = os
		extras_mapping_dict = {fk: view()._model_name() for fk, view in extras_mapping.items()}

		return (extras_dict, extras_mapping_dict)



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

		# {router-view-instance}
		# TODO: This should be refactored so that router
		# returns an instance which has the router set on it.
		view = self.router.model_view(related_model)()
		view.router = self.router
		return (RelatedModel(fieldname, related_model),) + view._follow_related(fieldspec)



	def _get_with(self, wth, pks, request):
		head, *tail = wth.split('.')

		next = self._follow_related(head)[0].model

		pks = list(self.model.objects.filter(pk__in=pks).values_list(head + '__pk', flat=True))
		view_class = self.router.model_view(next)

		if not tail:
			return (view_class, pks)
		else:
			view = view_class()
			# {router-view-instance}
			view.router = self.router
			return view._get_with('.'.join(tail), pks, request=request)



	def _parse_filter(self, queryset, field, value, partial=''):
		head, *tail = field.split('.')

		if tail:
			next = self._follow_related(head)[0].model
			view = self.router.model_view(next)()
			# {router-view-instance}
			view.router = self.router
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

		if qualifier in ('in', 'range', 'isnull'):
			values = value.split(',')
			if qualifier == 'range':
				if len(values) != 2:
					raise BinderRequestError('Range requires exactly 2 values for {{{}}}.{{{}}}.'
							.format(self.model.__name__, head))
		else:
			values = [value]

		if isinstance(field, (models.IntegerField, models.AutoField, models.ForeignKey)) \
				or isinstance(field, (models.ManyToOneRel, models.ManyToManyField, models.ManyToManyRel)):
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by :in or :isnull
				if v == '':
					continue
				try:
					clean_value.append(int(v))
				except ValueError:
					raise BinderRequestError('Invalid value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
		elif isinstance(field, models.FloatField):
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by :in or :isnull
				if v == '':
					continue
				try:
					clean_value.append(float(v))
				except ValueError:
					raise BinderRequestError('Invalid value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
		elif isinstance(field, models.DateTimeField):
			# Maybe allow __startswith? And __year etc?
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by :in or :isnull
				if v == '':
					continue
				if not re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}([T ][0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?([A-Za-z]+|[+-][0-9]{1,4})?)?$', v):
					raise BinderRequestError('Invalid YYYY-MM-DDTHH:MM:SS(.mmm)ZONE value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
			clean_value = values
		elif isinstance(field, models.DateField):
			# Maybe allow __startswith? And __year etc?
			allowed_qualifiers = (None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by :in or :isnull
				if v == '':
					continue
				if not re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', v):
					raise BinderRequestError('Invalid YYYY-MM-DD value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
			clean_value = values
		elif isinstance(field, models.BooleanField):
			allowed_qualifiers = (None, 'isnull')
			for v in values:
				# Filter out empty strings, they make no sense in this context, and are likely caused by :in or :isnull
				if v == '':
					continue
				if v == 'true':
					clean_value.append(True)
				elif v == 'false':
					clean_value.append(False)
				else:
					raise BinderRequestError('Invalid value {{{}}} for {} {{{}}}.{{{}}}.'
							.format(v, field.__class__.__name__, self.model.__name__, head))
		elif isinstance(field, (models.CharField, models.TextField)):
			allowed_qualifiers = (None, 'in', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'exact', 'search', 'isnull')
			clean_value = values
		else:
			raise BinderRequestError('Filtering not supported for type {} ({{{}}}.{{{}}}).'
					.format(field.__class__.__name__, self.model.__name__, head))

		if qualifier == 'isnull':
			clean_value = True
		elif qualifier in ('in', 'range'):
			pass
		else:
			try:
				clean_value = clean_value[0]
			except IndexError:
				raise BinderRequestError('Value for filter {{{}}}.{{{}}} may not be empty.'.format(self.model.__name__, head))

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
			view = self.router.model_view(next)()
			# {router-view-instance}
			view.router = self.router
			return view._parse_order_by(queryset, '.'.join(tail), partial + head + '__')

		try:
			self.model._meta.get_field(head)
		except models.fields.FieldDoesNotExist:
			if head == 'id':
				pk = self.model._meta.pk
				head = pk.get_attname() if pk.one_to_one or pk.many_to_one else pk.name
			else:
				raise BinderRequestError('Unknown field in order_by: {{{}}}.{{{}}}.'.format(self.model.__name__, head))

		return (queryset, partial + head)



	def search(self, queryset, search, request):
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



	def filter_deleted(self, queryset, pk, deleted, request):
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



	def get_queryset(self, request):
		return self.model.objects.all()



	def order_by(self, queryset, request):
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
			# Append model default orders to the API orders.
			# This guarantees stable result sets when paging.
			orders += queryset.model._meta.ordering
			queryset = queryset.order_by(*orders)
		return queryset



	def get(self, request, pk=None, withs=None):
		meta = {}
		queryset = self.get_queryset(request)
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

		queryset = self.order_by(queryset, request)

		if not pk:
			meta['total_records'] = queryset.count()

		queryset = self._paginate(queryset, request)

		#### with
		extras, extras_mapping = self._get_withs(queryset, withs, request=request)

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

		return JsonResponse(response_data)



	# Deserialize JSON to Django Model objects.
	# obj: Model object to update (for PUT), newly created object (for POST)
	# values: Python dict of {field name: value} (parsed JSON)
	# Output: Python dict representation of the updated object
	def _store(self, obj, values, request, ignore_unknown_fields=False, pk=None):
		deferred_m2ms = {}
		ignored_fields = []
		validation_errors = []

		def store_field(obj, field, value, request, pk=pk):
			try:
				func = getattr(self, '_store__' + field)
			except AttributeError:
				func = self._store_field
			return func(obj, field, value, request, pk=pk)

		for field, value in values.items():
			try:
				res = store_field(obj, field, value, request, pk=pk)
				if isinstance(res, list):
					deferred_m2ms[field] = res
			except BinderInvalidField:
				if not ignore_unknown_fields:
					raise
			except BinderReadOnlyFieldError:
				ignored_fields.append(field)
			except BinderValidationError as e:
				validation_errors.append(e)

		try:
			obj.full_clean()
		except ValidationError as ve:
			model_name = self.router.model_view(obj.__class__)()._model_name()

			e = BinderValidationError({
				model_name: {
					obj.pk if pk is None else pk: {
						f: [
							{'code': e.code, 'message': e.messages[0]}
							for e in el
						]
						for f, el in ve.error_dict.items()
					}
				}
			})
			validation_errors.append(e)

		# full_clean() doesn't complain when CharField(blank=True, null=False) = None
		# This causes save() to explode with a django.db.IntegrityError because the
		# column is NOT NULL. Tyvm, Django.
		# So we check this case here.
		for f in obj._meta.fields:
			if (f.blank and not f.null) and not is_filled_upon_save(f):
				# gettattr on a foreignkey foo gets the related model, while foo_id just gets the id.
				# We don't need or want the model (nor the DB query), we'll take the id thankyouverymuch.
				name = f.name + ('_id' if isinstance(f, models.ForeignKey) else '')

				if getattr(obj, name) is None:
					e = BinderValidationError({
						self._model_name(): {
							obj.pk if pk is None else pk: {
								f.name: [{
									'code': 'null',
									'message': 'This field cannot be null.'
								}]
							}
						}
					})
					validation_errors.append(e)

		if validation_errors:
			raise sum(validation_errors, None)

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
						rmobj.save()
					elif hasattr(rmobj, 'deleted'):
						if not rmobj.deleted:
							rmobj.deleted = True
							rmobj.save()
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
	def _store_field(self, obj, field, value, request, pk=None):
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
							model_name = self.router.model_view(obj.__class__)()._model_name()
							raise BinderValidationError({
								model_name: {
									obj.pk if pk is None else pk: {
										f.name: [{
											'code': 'not_int',
											'message': 'This value must be an integral number.',
											'value': value
										}]
									}
								}
							})
					setattr(obj, f.attname, value)
				elif isinstance(f, models.TextField):
					# Django doesn't enforce max_length on TextFields, so we do.
					if f.max_length is not None:
						if isinstance(value, str) and len(value) > f.max_length:
							setattr(obj, f.attname, value[:f.max_length])
							model_name = self.router.model_view(obj.__class__)()._model_name()
							raise BinderValidationError({
								model_name: {
									obj.pk if pk is None else pk: {
										f.name: [{
											'code': 'max_length',
											'message': 'Ensure this value has at most {} characters (it has {}).'.format(f.max_length, len(value)),
											'limit_value': f.max_length,
											'show_value': len(value),
											'value': value
										}]
									}
								}
							})
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
					field_name = obj._meta.get_field(field).remote_field.model.__name__
					model_name = self.router.model_view(obj.__class__)()._model_name()
					raise BinderValidationError({
						model_name: {
							obj.pk: {
								field: [{
									'code': 'does_not_exist',
									'message': '{} instances {} do not exist'.format(field_name, list(ids)),
									'model': field_name,
									'values': list(ids)
								}]
							}
						}
					})
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
		if isinstance(old, dict) and isinstance(new, dict):
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

		if isinstance(old, list) and isinstance(new, list):
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



	# Put data and with on one big pile, that's easier for us
	def _multi_put_parse_request(self, request):
		body = jsonloads(request.body)

		if not 'data' in body:
			raise BinderRequestError('missing data')

		if not isinstance(body['data'], list):
			raise BinderRequestError('data should be a list')

		if 'with' in body and not isinstance(body['with'], dict):
			raise BinderRequestError('with should be a dict')

		data = body.get('with', {})
		data[self._model_name()] = body['data']

		return data



	# Sort object values by model/id
	def _multi_put_collect_objects(self, data):
		objects = {}
		for modelname, objs in data.items():
			if not isinstance(objs, list):
				raise BinderRequestError('with.{} value should be a list')

			try:
				model = self.router.name_models[modelname]
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

		return objects



	def _multi_put_convert_backref_to_forwardref(self, objects):
		for (model, mid), values in objects.items():
			for field in filter(lambda f: f.one_to_many, model._meta.get_fields()):
				if field.name in values:
					if not isinstance(values[field.name], list) or not all(isinstance(v, int) for v in values[field.name]):
						raise BinderFieldTypeError(self.model.__name__, field.name)
					for rid in values[field.name]:
						if (field.related_model, rid) in objects:
							objects[(field.related_model, rid)][field.remote_field.name] = mid
		return objects



	def _multi_put_calculate_dependencies(self, objects):
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
						# Ignore dependencies from an object to itself
						if (model, mid) != (r_model, r_id):
							dependencies[(model, mid)].add((r_model, r_id))

		return dependencies



	# Actually sort the objects by dependency (and within dependency layer by model/id)
	def _multi_put_order_dependencies(self, dependencies):
		ordered_objects = []
		while dependencies:
			this_batch = []
			# NOTE: careful. This code makes a deep copy of the dependency list, so the dependency
			# data the for iterates over is stable. The body of the loop modifies <dependencies>,
			# so without the deep copy this leads to nasty surprises.
			for obj, deps in [(k, set(v)) for k, v in dependencies.items()]:
				if not deps:
					this_batch.append(obj)
					del dependencies[obj]
					for d in dependencies.values():
						if obj in d:
							d.remove(obj)
			if len(this_batch) == 0:
				raise BinderRequestError('No progress in dependency resolution! Cyclic dependencies?')
			ordered_objects += sorted(this_batch, key=lambda obj: (obj[0].__name__, obj[1]))

		return ordered_objects



	def _multi_put_save_objects(self, ordered_objects, objects, request):
		new_id_map = {}
		validation_errors = []
		for model, oid in ordered_objects:
			values = objects[(model, oid)]
			logger.info('Saving {} {}'.format(model.__name__, oid))

			if oid >= 0:
				try:
					obj = model.objects.select_for_update().get(pk=oid)
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

			view = self.router.model_view(model)()
			# {router-view-instance}
			view.router = self.router
			try:
				view._store(obj, values, request, pk=oid)
			except BinderValidationError as e:
				validation_errors.append(e)
			if oid < 0:
				new_id_map[(model, oid)] = obj.id
				logger.info('Saved as id {}'.format(obj.id))

		if validation_errors:
			raise sum(validation_errors, None)

		return new_id_map



	def multi_put(self, request):
		logger.info('ACTIVATING THE MULTI-PUT!!!1!')

		data = self._multi_put_parse_request(request)
		objects = self._multi_put_collect_objects(data)
		objects = self._multi_put_convert_backref_to_forwardref(objects)
		dependencies = self._multi_put_calculate_dependencies(objects)
		ordered_objects = self._multi_put_order_dependencies(dependencies)
		new_id_map = self._multi_put_save_objects(ordered_objects, objects, request)

		output = defaultdict(list)
		for (model, oid), nid in new_id_map.items():
			output[self.router.model_view(model)()._model_name()].append((oid, nid))

		return JsonResponse({'idmap': output})



	def put(self, request, pk=None):
		self._require_model_perm('change', request, pk)

		if pk is None:
			return self.multi_put(request)

		values = jsonloads(request.body)

		try:
			obj = self.model.objects.select_for_update().get(pk=int(pk))
			old = self._get_obj(int(pk), request)
		except ObjectDoesNotExist:
			raise BinderNotFound()

		if hasattr(obj, 'deleted') and obj.deleted:
			raise BinderIsDeleted()

		data = self._store(obj, values, request)

		new = dict(data)
		new.pop('_meta', None)

		meta = data.setdefault('_meta', {})
		meta['with'], meta['with_mapping'] = self._get_withs([new['id']], request=request, withs=None)

		logger.info('PUT updated {} #{}'.format(self._model_name(), pk))
		for c in self._obj_diff(old, new, '{}[{}]'.format(self._model_name(), pk)):
			logger.debug('PUT ' + c)

		return JsonResponse(data)



	def patch(self, request, pk=None):
		return self.put(request, pk)



	def post(self, request, pk=None):
		self._require_model_perm('add', request)

		if pk is not None:
			return self.delete(request, pk, undelete=True)

		values = jsonloads(request.body)

		data = self._store(self.model(), values, request)

		new = dict(data)
		new.pop('_meta', None)

		meta = data.setdefault('_meta', {})
		meta['with'], meta['with_mapping'] = self._get_withs([new['id']], request=request, withs=None)

		logger.info('POST created {} #{}'.format(self._model_name(), data['id']))
		for c in self._obj_diff({}, new, '{}[{}]'.format(self._model_name(), data['id'])):
			logger.debug('POST ' + c)

		return JsonResponse(data)



	def delete(self, request, pk=None, undelete=False):
		if not undelete:
			self._require_model_perm('delete', request)

		if pk is None:
			raise BinderMethodNotAllowed()

		# FIXME: ugly workaround, remove when Django bug fixed
		# Try/except because https://code.djangoproject.com/ticket/27005
		try:
			if request.body not in (b'', b'{}'):
				raise BinderRequestError('{}DELETE body must be empty or empty json object.'.format('UN' if undelete else ''))
		except ValueError:
			pass

		try:
			obj = self.model.objects.select_for_update().get(pk=int(pk))
		except ObjectDoesNotExist:
			raise BinderNotFound()

		self.soft_delete(obj, undelete, request)
		logger.info('{}DELETEd {} #{}'.format('UN' if undelete else '', self._model_name(), pk))

		return HttpResponse(status=204)  # No content



	def soft_delete(self, obj, undelete, request):
		try:
			if obj.deleted and not undelete:
				raise BinderIsDeleted()
			if not obj.deleted and undelete:
				raise BinderIsNotDeleted()
		except AttributeError:
			if undelete:  # Should never happen
				raise BinderMethodNotAllowed()
			else:
				obj.delete()
				return

		obj.deleted = not undelete
		obj.save()



	def dispatch_file_field(self, request, pk=None, file_field=None):
		if not request.method in ('GET', 'POST', 'DELETE'):
			raise BinderMethodNotAllowed()

		if isinstance(pk, self.model):
			obj = pk
		else:
			try:
				obj = self.get_queryset(request).get(pk=int(pk))
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

				# Determine resize threshold
				try:
					max_size = self.image_resize_threshold[file_field_name]
				except TypeError:
					max_size = self.image_resize_threshold
				if max_size is None:
					max_size = 65335
				try:
					max_width, max_height = max_size
				except (TypeError, ValueError):
					max_width, max_height = max_size, max_size

				if width > max_width or height > max_height:
					img.thumbnail((max_width, max_height), Image.ANTIALIAS)
					logger.info('image dimensions ({}x{}) exceeded ({}, {}), resizing.'.format(width, height, max_width, max_height))
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
			path = self.router.model_route(self.model, obj.id, field)
			return JsonResponse( {"data": {file_field_name: path}} )

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
			return JsonResponse( {"data": {file_field_name: None}} )



	def filefield_get_name(self, instance=None, request=None, file_field=None):
		try:
			method = getattr(self, 'filefield_get_name_' + file_field.field.name)
		except AttributeError:
			return os.path.basename(file_field.path)
		return method(instance=instance, request=request, file_field=file_field)



	def view_history(self, request, pk=None, **kwargs):
		if request.method != 'GET':
			raise BinderMethodNotAllowed()

		debug = kwargs['history'] == 'debug'

		if debug and not django.conf.settings.ENABLE_DEBUG_ENDPOINTS:
			logger.warning('Debug endpoints disabled.')
			return HttpResponseForbidden('Debug endpoints disabled.')

		changesets = history.Changeset.objects.filter(id__in=set(history.Change.objects.filter(model=self.model.__name__, oid=pk).values_list('changeset_id', flat=True)))
		if debug:
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



def handler500(request):
	try:
		request_id = request.request_id
	except Exception as e:
		request_id = str(e)

	return HttpResponse('{"code": "InternalServerError", "debug": {"request_id": "' + request_id + '"}}', status=500)
