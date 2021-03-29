import logging
import time
import io
import inspect
import os
import hashlib
import datetime
import mimetypes
import functools
from collections import defaultdict, namedtuple
from PIL import Image
from inspect import getmro

import django
from django.views.generic import View
from django.core.exceptions import ObjectDoesNotExist, FieldError, ValidationError, FieldDoesNotExist
from django.http import HttpResponse, StreamingHttpResponse, HttpResponseForbidden
from django.http.request import RawPostDataException, QueryDict
from django.db import models, connections
from django.db.models import Q, F
from django.db.models.lookups import Transform
from django.utils import timezone
from django.db import transaction
from django.db.models.expressions import BaseExpression, Value, CombinedExpression, OrderBy, ExpressionWrapper
from django.db.models.fields.reverse_related import ForeignObjectRel


from .exceptions import (
	BinderException, BinderFieldTypeError, BinderFileSizeExceeded, BinderForbidden, BinderImageError, BinderImageSizeExceeded,
	BinderInvalidField, BinderIsDeleted, BinderIsNotDeleted, BinderMethodNotAllowed, BinderNotAuthenticated, BinderNotFound,
	BinderReadOnlyFieldError, BinderRequestError, BinderValidationError, BinderFileTypeIncorrect, BinderInvalidURI, BinderSkipSave
)
from . import history
from .orderable_agg import OrderableArrayAgg, GroupConcat
from .models import FieldFilter, BinderModel, ContextAnnotation, OptionalAnnotation, BinderFileField
from .json import JsonResponse, jsonloads


def split_par_aware(content):
	start = 0
	depth = 0

	for i, char in enumerate(content):
		if char == '(':
			depth += 1
		elif char == ')':
			depth -= 1
		elif char == ',' and depth == 0:
			yield content[start:i]
			start = i + 1

	yield content[start:]


def get_default_annotations(model):
	annotations = set()

	if issubclass(model, BinderModel) and hasattr(model, 'Annotations'):
		for attr in dir(model.Annotations):
			# Skip internal python keys
			if attr.startswith('__') and attr.endswith('__'):
				continue
			# Get expr
			expr = getattr(model.Annotations, attr)
			# Check if not optional
			if not isinstance(expr, OptionalAnnotation):
				annotations.add(attr)

	return annotations


# Haha kill me now
def multiput_get_id(bla):
	return bla['id'] if isinstance(bla, dict) else bla


def fix_output_field(expr, model):
	if isinstance(expr, F):
		path = expr.name.split('__')
		for key in path[:-1]:
			field = model._meta.get_field(key)
			model = (
				field.related_model
				if isinstance(field, ForeignObjectRel) else
				field.remote_field.model
			)
		expr._output_field_or_none = model._meta.get_field(path[-1])
	elif isinstance(expr, BaseExpression):
		try:
			expr.field
		except AttributeError:
			for subexpr in expr.get_source_expressions():
				fix_output_field(subexpr, model)


def get_annotations(model, request=None, annotations=None):
	if annotations is None:
		annotations = get_default_annotations(model)

	res = {}

	for attr in annotations:
		# Get expr
		expr = getattr(model.Annotations, attr)
		if isinstance(expr, (ContextAnnotation, OptionalAnnotation)):
			expr = expr.get(request)
		if callable(expr) and not isinstance(expr, F) and not isinstance(expr, BaseExpression):
			expr = expr()
		fix_output_field(expr, model)
		# Get field
		if isinstance(expr, F):
			field = expr._output_field_or_none
		elif isinstance(expr, BaseExpression):
			field = expr.field.clone()
			field.name = attr
			field.model = model
		else:
			raise ValueError(
				'{}.Annotations.{} is not a valid django query expression'
				.format(model.__name__, attr)
			)
		# Add annotation
		res[attr] = {'expr': expr, 'field': field}

	return res


def annotate(qs, request=None, annotations=None):
	for name, annotation in get_annotations(qs.model, request, annotations).items():
		qs = qs.annotate(**{name: annotation['expr']})
	return qs



logger = logging.getLogger(__name__)



# Used to truncate request bodies.
def ellipsize(msg, length=2048):
	msglen = len(msg)
	msg = repr(msg)
	if msglen > length:
		msg = msg[:length] + '...'
	msg += ' [{}]'.format(msglen)
	return msg


def sign(num):
	if num < 0:
		return -1
	elif num == 0:
		return 0
	elif num > 0:
		return 1


RelatedModel = namedtuple('RelatedModel', ['fieldname', 'model', 'reverse_fieldname'])
FilterDescription = namedtuple('FilterDescription', ['filter', 'need_distinct'])

# Stolen and improved from https://stackoverflow.com/a/30462851
def image_transpose_exif(im):
	exif_orientation_tag = 0x0112  # contains an integer, 1 through 8
	exif_transpose_sequences = [   # corresponding to the following
		[],
		[Image.FLIP_LEFT_RIGHT],
		[Image.ROTATE_180],
		[Image.FLIP_TOP_BOTTOM],
		[Image.FLIP_LEFT_RIGHT, Image.ROTATE_90],
		[Image.ROTATE_270],
		[Image.FLIP_TOP_BOTTOM, Image.ROTATE_90],
		[Image.ROTATE_90],
	]

	try:
		if im._getexif() is not None:
			seq = exif_transpose_sequences[im._getexif()[exif_orientation_tag] - 1]
			return functools.reduce(lambda im, op: im.transpose(op), seq, im)
		else:
			return im
	except KeyError:
		return im


def getsubclasses(cls):
	for subcls in cls.__subclasses__():
		yield subcls
		yield from getsubclasses(subcls)


# Prefix a deconstructible expression by adding a prefix to all
# fields.  If the expression is a string, just prefix it.  If the
# expression starts with -, the - is kept at the start for order by
# expressions.
def prefix_db_expression(value, prefix):
	if isinstance(value, str):
		if value.startswith('-'):
			return '-%s__%s' % (prefix, value[1:])
		else:
			return prefix + '__' + value

	elif not hasattr(value, 'resolve_expression') or isinstance(value, Value):
		return value

	# Generic case: use deconstruct() to parse and prefix all args
	elif isinstance(value, (F, Transform, OrderBy, ExpressionWrapper)):
		path, args, kwargs = value.deconstruct()
		args = [prefix_db_expression(arg, prefix) for arg in args]
		klass = value.__class__
		return klass(*args, **kwargs)

	elif isinstance(value, CombinedExpression):
		lhs = prefix_db_expression(value.lhs, prefix)
		rhs = prefix_db_expression(value.rhs, prefix)
		return CombinedExpression(lhs, value.connector, rhs, output_field=value._output_field_or_none)

	else:
		raise ValueError('Unknown expression type, cannot apply db prefix: %s', value)


class ModelView(View):
	# Model this is a view for. Use None for views not tied to a particular model.
	model = None

	# If True, Router().model_view(model) will return this view.  Set to False for additional views for the same model.
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
	shown_annotations = None
	hidden_annotations = []

	# Some models have derived properties that are not part of the fields of the model.
	# Properties added to this shown property list are automatically added to the fields
	# that are returned. Note that properties added here are read only. They can not be changed
	# directly. Rather the fields they are derived from need to be updated.
	shown_properties = []

	# Fields that won't be written by default (PUT/POST). Writing them is not an error;
	# their values are silently ignored.
	# The following fields are implicitly included in unwritable_fields:
	#  - id, pk, deleted, _meta
	#  - reverse relations  (FIXME ehh is this still true?)
	#  - file fields (as specified in file_fields)
	#
	# NOTE: custom _store__foo() methods will still be called for unwritable fields.
	unwritable_fields = []

	# Fields that can be written on creation of new records (POST) but won't be
	# written by default on updates of existing records (PUT/POST).
	# Writing them for updates is not an error; their values are silently ignored.
	#
	# NOTE: custom _store__foo() methods will still be called for unupdatable fields.
	unupdatable_fields = []

	# Allow validation without saving.
	allow_standalone_validation = False

	# Fields to use for ?search=foo. Empty tuple for disabled search.
	# NOTE: only string fields and 'id' are supported.
	# id is hardcoded to be treated as an integer.
	# For anything fancier, override self.search()
	searches = []
	transformed_searches = {}

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
	# 123 limits size to 123x123 for all ImageFields on this model.
	# (123,456) limits size to 123x456 on all ImageFields.
	# {'foo': 123, 'bar': 456} limits size to 123x123 on field foo and 456x456 on bar.
	# A dict will KeyError if you don't specify all ImageFields. Or use:
	# collections.defaultdict(lambda: 512, foo=1024)
	image_resize_threshold = 512
	image_format_override = None

	# A dict that looks like:
	#  name: {
	#'model': model class,
	#'annotation': Q obj or method name,
	#'related_field': fieldname (str) or None if there is no such field,
	#'singular': boolean, (assumed False if missing)
	#  }
	virtual_relations = {}

	@property
	def AggStrategy(self):
		return GroupConcat if connections[self.model.objects.db].vendor == 'mysql' else OrderableArrayAgg


	def annotations(self, request, include_annotations=None):
		if include_annotations is None:
			include_annotations = self._parse_include_annotations(request)
		return get_annotations(self.model, request, include_annotations.get(''))


	#### XXX WARNING XXX
	# dispatch() ensures transactions. If overriding or circumventing dispatch(), you're on your own!
	# Also, a transaction is aborted if and only if post() or whatever raises an exception.
	# If you detect an error and return a HttpResponse(status=400), the transaction is not aborted!
	#### XXX WARNING XXX
	def dispatch(self, request, *args, **kwargs):
		self.router = kwargs.pop('router')
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
			with transaction.atomic(), history.atomic(source='http', user=request.user, uuid=request.request_id):
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


	# This returns a (cached) filterclass for a field class.
	def get_field_filter(self, field_class, reset=False):
		f = not reset and getattr(self, '_field_filters', None)

		if not f:
			f = {}
			for field_filter_cls in FieldFilter.__subclasses__():
				for field_cls in field_filter_cls.fields:
					if f.get(field_cls):
						raise ValueError('Field-Filter mapping conflict: {} vs {}'.format(field_filter_cls.name, field_cls.name))
					else:
						f[field_cls] = field_filter_cls

			self._field_filters = f

		return f.get(field_class)


	# Like model._meta.model_name, except it converts camelcase to underscores
	@classmethod
	def _model_name(cls):
		mn = cls.model.__name__
		return ''.join((x + '_' if x.islower() and y.isupper() else x.lower() for x, y in zip(mn, mn[1:] + 'x')))



	# Use this to instantiate other views you need. It returns a properly initialized view instance.
	# Call like:   foo_view_instance = self.get_view(FooView)
	def get_view(self, cls):
		view = cls()
		view.router = self.router
		return view



	# Use this to instantiate the default view for a specific model class.
	# Call like:   foo_view_instance = self.get_model_view(FooModel)
	def get_model_view(self, model):
		return self.get_view(self.router.model_view(model))



	# Return a list of RelatedObjects for all _visible_ reverse relations (from both FKs and m2ms).
	def _get_reverse_relations(self):
		return [
			f for f in self.model._meta.get_fields()
			if (f.one_to_one or f.one_to_many or f.many_to_many) and f.auto_created
		]


	# Kinda like model_to_dict() for multiple objects.
	# Return a list of dictionaries, one per object in the queryset.
	# Includes a list of ids for all m2m fields (including reverse relations).
	def _get_objs(self, queryset, request, annotations=None):
		datas = []
		datas_by_id = {} # Save datas so we can annotate m2m fields later (avoiding a query)
		objs_by_id = {} # Same for original objects

		# Serialize the objects!
		if self.shown_fields is None:
			fields = [f for f in self.model._meta.fields if f.name not in self.hidden_fields]
		else:
			fields = [f for f in self.model._meta.fields if f.name in self.shown_fields]

		if annotations is None:
			annotations = set(self.annotations(request))
		if self.shown_annotations is None:
			annotations -= set(self.hidden_annotations)
		else:
			annotations &= set(self.shown_annotations)

		for obj in queryset:
			# So we tend to make binder call queryset.distinct when necessary
			# to prevent duplicate results, this is however not always possible
			# For example when ordering on a field from an m2m relation
			# this field is implicitly added to the row to be able to order
			# which makes distinct not work as expected.
			if obj.pk in objs_by_id:
				continue

			data = {}
			for f in fields:
				if isinstance(f, models.fields.files.FileField):
					file = getattr(obj, f.attname)
					if file:
						# {router-view-instance}
						data[f.name] = self.router.model_route(self.model, obj.id, f)

						# {duplicate-binder-file-field-hash-code}
						if isinstance(f, BinderFileField):
							data[f.name] += '?h={}&content_type={}&filename={}'.format(
								file.content_hash,
								file.content_type or '',
								os.path.basename(file.name),
							)
					else:
						data[f.name] = None
				else:
					data[f.name] = getattr(obj, f.attname)

			for a in annotations:
				data[a] = getattr(obj, a)

			for prop in self.shown_properties:
				data[prop] = getattr(obj, prop)

			if self.model._meta.pk.name in data:
				data['id'] = data.pop(self.model._meta.pk.name)

			datas.append(data) # order matters!
			datas_by_id[obj.pk] = data
			objs_by_id[obj.pk] = obj

		self._annotate_objs(datas_by_id, objs_by_id)

		return datas


	def _annotate_objs(self, datas_by_id, objs_by_id):
		pks = datas_by_id.keys()

		# Annotate data for obj id with m2m_fields (one query per field for performance)
		for field_name in self.m2m_fields:
			idmap = defaultdict(list)
			# Wuh, the autogenerated reverse relation is called foo_set, but in values() you need foo? Weird.
			# FIXME: We use explicit related_name everywhere, do we still need this? Maybe for User/Group
			field_name2 = field_name[:-4] if field_name.endswith('_set') else field_name
			remote_field = self.model._meta.get_field(field_name2).remote_field
			local_field = self.model._meta.get_field(field_name)

			for other, this in remote_field.model.objects.filter(**{remote_field.name + '__pk__in': pks}).values_list('pk', remote_field.name + '__pk'):
				idmap[this].append(other)

			for obj_id, data in datas_by_id.items():
				# TODO: Don't require OneToOneFields in the m2m_fields list
				if isinstance(local_field, models.OneToOneRel):
					assert(len(idmap[obj_id]) <= 1)
					data[field_name] = idmap[obj_id][0] if len(idmap[obj_id]) == 1 else None
				else:
					data[field_name] = idmap[obj_id]

		# For ease of use, return the datas dict
		return datas_by_id


	# Kinda like model_to_dict()
	# Fetches the object specified by <pk>, and serializes it to a Binder json dict.
	# It goes through get_queryset(), so permission scoping applies.
	# Raises model.DoesNotExist if the pk isn't found or not accessible to the user.
	def _get_obj(self, pk, request, include_annotations=None):
		if include_annotations is None:
			include_annotations = self._parse_include_annotations(request)
		results = self._get_objs(
			annotate(self.get_queryset(request).filter(pk=pk), request, include_annotations.get('')),
			request=request,
			annotations=include_annotations.get(''),
		)
		if results:
			return results[0]
		else:
			raise self.model.DoesNotExist()



	# Split ['animals(name:contains=lion)']
	# in ['animals': ['name:contains=lion']]
	# { 'animals': {'filters': ['name:contains=lion'], 'subrels': {}}}
	#
	# We include the withs because the where target
	# must be included in the withs. Filtering a relation you aren't querying is wrong.
	def _parse_wheres(self, wheres, withs):
		where_map = {}
		for wh in wheres:
			# Check if "(" and ")" exist in where
			if '(' not in wh or ')' not in wh:
				raise BinderRequestError('Syntax error in {{where={}}}.'.format(wh))

			target_rel, query = wh.split('(')

			if target_rel not in withs:
				raise BinderRequestError('Relation of {{where={}}} is missing from withs {{withs={}}}.'.format(wh, withs))

			# Also strip the trailing ) from the query
			query = query[:-1]

			rels = target_rel.split('.')
			pointer = where_map
			for i, rel in enumerate(rels):
				if rel not in pointer:
					pointer[rel] = {'filters': [], 'subrels': {}}

				# Don't change the pointer
				# if this is the last iteration
				if i != (len(rels) - 1):
					pointer = pointer[rel]['subrels']

			pointer[rel]['filters'].append(query)

		return where_map

	# Find which objects of which models to include according to <withs> for the objects in <queryset>.
	# returns three dictionaries:
	# - withs: { related_modal_name: [ids] }
	# - mappings: { with_name: related_model_name }
	# - related_name_mappings: { with_name: related_model_reverse_key }
	#
	# The related name mappings are useful when requesting a related
	# model in the with via its reverse relation and not putting it in
	# the m2m_fields, because for example there may be a huge number
	# of objects (and we're using a where filter to scope them).  Then
	# one might not be interested in the complete list of IDs, only in
	# the ones requested.  The reverse key allows the frontend to
	# reconstruct to which property in the main model the "with'ed"
	# model belongs.
	def _get_withs(self, pks, withs, request, wheres=None, include_annotations=None):
		if withs is None and request is not None:
			withs = list(filter(None, request.GET.get('with', '').split(',')))

		if include_annotations is None:
			if request is not None:
				include_annotations = self._parse_include_annotations(request)
			else:
				include_annotations = {}

		# Make sure to include A if A.B is specified.
		for w in withs:
			if '.' in w:
				withs.append('.'.join(w.split('.')[:-1]))

		if wheres is None and request is not None:
			where_str = request.GET.get('where', '')
			# Filter out empty params
			where_params = list(filter(bool, split_par_aware(where_str)))
			where_map = self._parse_wheres(where_params, withs)

		if isinstance(pks, django.db.models.query.QuerySet):
			if not withs:
				pks = []  # No sense in re-executing the query just for the ids if there are no withs
			else:
				pks = pks.values_list('pk', flat=True)
		# Force evaluation of querysets, as nesting too deeply causes problems. See T1850.
		pks = list(pks)

		extras_with_flat_ids = {}
		withs_per_model = defaultdict(dict)
		extras_mapping = {}
		extras_reverse_mapping_dict = {}

		# ['foo.bar', 'foo.qux', 'foo.bar.hoi'] => {'foo': {'bar': {'hoi': {}}, 'qux': {}}}
		def withs_to_nested_set(withs, result={}):
			for w in withs:
				head, *tail = w.split('.')
				if head not in result:
					result[head] = {}
				if tail:
					withs_to_nested_set(['.'.join(tail)], result[head])

			return result

		with_map = withs_to_nested_set(withs)

		# Make sure the _get_with only gets the wheres relevant to the relation
		# We scope on the head of the relation, as the caretakers in animals.caretaker
		# must also be filtered by the animal filter
		# head = w.split('.')[0]
		# scoped_wheres = where_map.get(head, [])

		field_results = self._get_with_ids(pks, request=request, include_annotations=include_annotations, with_map=with_map, where_map=where_map)
		for (w, (view, new_ids_dict, is_singular)) in field_results.items():
			model_name = view._model_name()
			extras_mapping[w] = model_name

			try:
				annotations = include_annotations[w]
			except KeyError:
				annotations = get_default_annotations(view.model)
			annotations = frozenset(annotations)  # So that it is hashable

			(view, annotation_ids) = extras_with_flat_ids.setdefault(model_name, (view, {}))
			flat_ids = annotation_ids.setdefault(annotations, set())
			for new_ids in new_ids_dict.values():
				flat_ids.update(set(new_ids))

			# Filter all annotations we need to add to this particular model
			for (w2, (view2, new_ids_dict2, is_singular2)) in field_results.items():
				if w2.startswith(w+'.'):
					rest = w2[len(w)+1:]
					try:
						(view2_old, old_ids_dict2, is_singular2_old) = withs_per_model[model_name][rest]
						new_ids_dict2.update(old_ids_dict2)
					except KeyError:
						pass
					withs_per_model[model_name][rest] = (view2, new_ids_dict2, is_singular2)

			related_model_info = self._follow_related(w)[-1]
			if related_model_info.reverse_fieldname is not None:
				extras_reverse_mapping_dict[w] = related_model_info.reverse_fieldname

		extras_dict = {}
		# FIXME: delegate this to a router or something
		for (model_name, (view, annotation_ids)) in extras_with_flat_ids.items():
			# It can happen that an id appears in multiple annotation sets, here
			# we move those ids to new annotation sets containing a union of the
			# two annotation sets
			to_add = list(annotation_ids.items())
			annotation_ids = {}
			while to_add:
				rannotations, rids = to_add.pop()
				for lannotations, lids in list(annotation_ids.items()):
					overlap = lids & rids
					if overlap:
						to_add.append((lannotations | rannotations, overlap))
						lids -= overlap
						rids -= overlap
						if not lids:
							del annotation_ids[lannotations]
						if not rids:
							break
				if rids:
					annotation_ids.setdefault(rannotations, set()).update(rids)

			extras_dict[model_name] = []
			view = view()
			# {router-view-instance}
			view.router = self.router
			for annotations, with_pks in annotation_ids.items():
				objs = view._get_objs(
					annotate(view.get_queryset(request).filter(pk__in=with_pks), request, annotations),
					request=request,
					annotations=annotations,
				)
				for obj in objs:
					view._annotate_obj_with_related_withs(obj, withs_per_model[model_name])
				extras_dict[model_name].extend(objs)

		return (extras_dict, extras_mapping, extras_reverse_mapping_dict, field_results)


	# Returns a dict mapping relations to a set of annotations that should be
	# included.
	# The top level model is indicated with the relation ''.
	# If a relation is not in the dict this means the annotations returned by
	# get_default_annotations should be used.
	def _parse_include_annotations(self, request):
		if 'include_annotations' in request.GET:
			includes = list(split_par_aware(request.GET['include_annotations']))
		else:
			includes = []

		relation_annotations = {}
		for include in includes:
			# Parse relation / annotations from include
			if not include:
				include = '()'
			if include.endswith(')'):
				relation, sep, annotations = include[:-1].partition('(')
				if not sep:
					raise BinderRequestError(
						'SyntaxError in {{include_annotations={}}}'
						.format(include)
					)
				annotations = annotations.split(',') if annotations else []
			else:
				relation, _, annotation = include.rpartition('.')
				annotations = [annotation]
			# Modify the relations annotations
			all_annotations = relation_annotations.setdefault(relation, set())
			for annotation in annotations:
				# Check if inverted
				inverted = False
				while annotation.startswith('-'):
					inverted = not inverted
					annotation = annotation[1:]
				# Expand * and convert to set
				related_models = self._follow_related(relation)
				model = (
					related_models[-1].model
					if related_models else
					self.model
				)
				if annotation == '*':
					annotation = get_default_annotations(model)
				elif (
					hasattr(model, 'Annotations') and
					hasattr(model.Annotations, annotation) and
					# Do not allow python internals
					not (
						annotation.startswith('__') and
						annotation.endswith('__')
					)
				):
					annotation = {annotation}
				else:
					raise BinderRequestError(
						'Annotation does not exist {{{}}}.{{{}}}.'
						.format(model.__name__, annotation)
					)
				# Add/remove annotations
				if inverted:
					all_annotations -= annotation
				else:
					all_annotations |= annotation

		return relation_annotations


	def _follow_related(self, fieldspec):
		if not fieldspec:
			return ()

		if isinstance(fieldspec, str):
			fieldspec = fieldspec.split('.')

		fieldname, *fieldspec = fieldspec

		try:
			field = self.model._meta.get_field(fieldname)

			if not field.is_relation:
				raise BinderRequestError('Field is not a related object {{{}}}.{{{}}}.'.format(self.model.__name__, fieldname))

			if isinstance(field, django.db.models.fields.reverse_related.ForeignObjectRel):
				# Reverse relations
				related_model = field.related_model
				related_field = field.remote_field.name
			else:
				# Forward relations
				related_model = field.remote_field.model
				related_field = field.remote_field.related_name # For completeness

			if field.remote_field.hidden: # Skip missing related fields
				related_field = None

		except FieldDoesNotExist:
			try:
				vr = self.virtual_relations[fieldname]
				try:
					related_model = vr['model']
					related_field = vr.get('related_field', None)
				except KeyError:
					raise BinderRequestError('No model defined for virtual relation field {{{}}}.{{{}}}.'.format(self.model.__name__, fieldname))
			except KeyError:
				raise BinderRequestError('Unknown field {{{}}}.{{{}}}.'.format(self.model.__name__, fieldname))


		view = self.get_model_view(related_model)
		return (RelatedModel(fieldname, related_model, related_field),) + view._follow_related(fieldspec)


	# This will return a dictionary of dotted "with string" keys and
	# tuple values of (view_class, id_dict).  These ids do not require
	# permission scoping.  This will be done when fetching the actual
	# objects.
	def _get_with_ids(self, pks, request, include_annotations, with_map, where_map):
		result = {}

		annotations = {}
		singular_fields = set()
		rel_ids_by_field_by_id = defaultdict(lambda: defaultdict(list))
		virtual_fields = set()

		Agg = self.AggStrategy

		for field in with_map:
			vr = self.virtual_relations.get(field, None)

			next_relation = self._follow_related(field)[0]
			view = self.get_model_view(next_relation.model)
			q, _ = view._filter_relation(None if vr else next_relation.fieldname, where_map.get(field, None), request, {
				rel[len(field) + 1:]: annotations
				for rel, annotations in include_annotations.items()
				if rel == field or rel.startswith(field + '.')
			})

			# Model default orders (this sometimes matters)
			orders = []
			field_alias = field + '___annotation' if vr else field
			for o in (view.model._meta.ordering if view.model._meta.ordering else BinderModel.Meta.ordering):
				orders.append(prefix_db_expression(o, field_alias))

			# Virtual relation
			if vr:
				virtual_fields.add(field)
				try:
					virtual_annotation = vr['annotation']
				except KeyError:
					raise BinderRequestError('Virtual relation {{{}}}.{{{}}} has no annotation defined.'.format(self.model.__name__, field))

				if vr.get('singular', False):
					singular_fields.add(field)

				# Some virtual withs cannot be (easily) expressed as
				# annotations, so allow for fetching of ids, instead.
				# This does mean you can't filter on this relation
				# unless you write a custom filter, too.
				if isinstance(virtual_annotation, Q):
					annotations[field_alias] = Agg(virtual_annotation, filter=q, ordering=orders)
				else:
					try:
						func = getattr(self, virtual_annotation)
					except AttributeError:
						raise BinderRequestError('Annotation for virtual relation {{{}}}.{{{}}} is {{{}}}, but no method by that name exists.'.format(
							self.model.__name__, field, virtual_annotation
						))
					rel_ids_by_field_by_id[field] = func(request, pks, q)
			# Actual relation
			else:
				if (getattr(self.model, field).__class__ == models.fields.related.ReverseOneToOneDescriptor or
					not any(f.name == field for f in (list(self.model._meta.many_to_many) + list(self._get_reverse_relations())))):
					singular_fields.add(field)

				if Agg != GroupConcat: # HACKK (GROUP_CONCAT can't filter and excludes NULL already)
					q &= Q(**{field+'__pk__isnull': False})
				annotations[field_alias] = Agg(field+'__pk', filter=q, ordering=orders)


		qs = self.model.objects.filter(pk__in=pks).values('pk').annotate(**annotations)
		for record in qs:
			for field in with_map:
				field_alias = field+'___annotation' if field in virtual_fields else field

				if field_alias in annotations:
					value = record[field_alias]
					if Agg == GroupConcat:
						# Stupid assumption that PKs are always integers.
						# Without this, the result types won't be right...
						value = [int(v) for v in value]

					# Make the values distinct.  We can't do this in
					# the Agg() call, because then we get an error
					# regarding order by and values needing to be the
					# same :(
					# We also can't just put it in a set, because we
					# need to preserve the ordering.  So we use a set
					# to keep track of what we've seen and only add
					# new items.
					seen_values = set()
					distinct_values = []
					for v in value:
						if v not in seen_values:
							distinct_values.append(v)
						seen_values.add(v)

					rel_ids_by_field_by_id[field][record['pk']] += distinct_values

		for field, sub_fields in with_map.items():
			next = self._follow_related(field)[0].model

			view = self.get_model_view(next)

			result[field] = (type(view), rel_ids_by_field_by_id[field], field in singular_fields)

			# And recur for subrelations
			if sub_fields:
				wm_scoped = where_map.get(field)
				wm_scoped = wm_scoped['subrels'] if wm_scoped else {}

				flattened_ids = [id for ids in rel_ids_by_field_by_id[field].values() for id in ids]
				subrelations = view._get_with_ids(flattened_ids, request=request, include_annotations=include_annotations, with_map=sub_fields, where_map=wm_scoped)
				for subrelation, data in subrelations.items():
					result['.'.join([field, subrelation])] = data

		return result


	# We have a queryset resulting in a set of ids where model M
	# should be scoped on, but also a set of wheres where model M
	# should further be scoped on.
	#
	# Returns a Q object for this field we should filter on further.
	def _filter_relation(self, field_name, where_map, request, include_annotations):
		# If there are no filters, do nothing
		if where_map is None:
			return Q(), False

		wheres = where_map['filters']

		q = Q()
		need_distinct = False
		for where in wheres:
			field, val = where.split('=')
			filter_description = self._parse_filter(field, val, request, include_annotations, field_name+'__' if field_name else '')
			need_distinct |= filter_description.need_distinct
			q &= filter_description.filter

		return FilterDescription(q, need_distinct)


	def _parse_filter(self, field, value, request, include_annotations, partial=''):
		head, *tail = field.split('.')
		need_distinct = False

		if not tail:
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

			q = self._filter_field(head, qualifier, value, invert, request, include_annotations, partial)
		else:
			q = Q()

		try:
			related = self._follow_related(head)[0]
		except Exception as e:
			related = None
			related_err = e

		if tail:
			if related is None:
				raise related_err

			view = self.get_model_view(related.model)
			filter_description = view._parse_filter('.'.join(tail), value, request, include_annotations, partial + head + '__')
			need_distinct |= filter_description.need_distinct
			q &= filter_description.filter

		# Distinct might be needed when we traverse a relation
		# that is joined in, as it may produce duplicate records.
		# Always doing the distinct works, but has performance
		# implications, hence we avoid it if possible.
		if related is not None:
			related_field = getattr(self.model, related.fieldname)
			if isinstance(related_field, models.fields.related.ReverseManyToOneDescriptor): # m2m or reverse fk
				need_distinct = True

		return FilterDescription(q, need_distinct)



	def _filter_field(self, field_name, qualifier, value, invert, request, include_annotations, partial=''):
		try:
			if field_name in self.hidden_fields:
				raise FieldDoesNotExist()
			field = self.model._meta.get_field(field_name)
		except FieldDoesNotExist:
			rel = partial and '.'.join(partial[:-2].split('__'))
			annotations = self.annotations(request, {'': include_annotations.get(rel)})
			if field_name not in annotations:
				raise BinderRequestError('Unknown field in filter: {{{}}}.{{{}}}.'.format(self.model.__name__, field_name))
			if partial:
				# NOTE: This creates a subquery; try to avoid this!
				qs = annotate(self.model.objects.all(), request, annotations)
				qs = qs.filter(self._filter_field(field_name, qualifier, value, invert, request, {
					rel_[len(rel) + 1:]: annotations
					for rel_, annotations in include_annotations.items()
					if rel_ == rel or rel_.startswith(rel + '.')
				}))
				return Q(**{partial + 'in': qs})
			field = annotations[field_name]['field']

		for field_class in inspect.getmro(field.__class__):
			filter_class = self.get_field_filter(field_class)
			if filter_class:
				filter = filter_class(field)
				try:
					return filter.get_q(qualifier, value, invert, partial)
				except ValidationError as e:
					# TODO: Maybe convert to a BinderValidationError later?
					raise BinderRequestError(e.message)

		# If we get here, we didn't find a suitable filter class
		raise BinderRequestError('Filtering not supported for type {} ({{{}}}.{{{}}}).'
				.format(field.__class__.__name__, self.model.__name__, field_name))



	def _parse_order_by(self, queryset, field, request, partial=''):
		head, *tail = field.split('.')

		if tail:
			next = self._follow_related(head)[0].model
			view = self.get_model_view(next)
			return view._parse_order_by(queryset, '.'.join(tail), request, partial + head + '__')

		if head.endswith('__nulls_last'):
			head = head[:-12]
			nulls_last = True
		elif head.endswith('__nulls_first'):
			head = head[:-13]
			nulls_last = False
		else:
			nulls_last = None

		try:
			self.model._meta.get_field(head)
		except FieldDoesNotExist:
			if head == 'id':
				pk = self.model._meta.pk
				head = pk.get_attname() if pk.one_to_one or pk.many_to_one else pk.name
			elif head not in self.annotations(request):
				raise BinderRequestError('Unknown field in order_by: {{{}}}.{{{}}}.'.format(self.model.__name__, head))

		return (queryset, partial + head, nulls_last)



	def search(self, queryset, search, request):
		if not search:
			return queryset

		if not (self.searches or self.transformed_searches):
			raise BinderRequestError('No search fields defined for this view.')

		q = Q()
		for s, transform in dict(
			self.transformed_searches,
			**{s: int if s == 'id' else str for s in self.searches}
		).items():
			try:
				q |= Q(**{s: transform(search)})
			except ValueError:
				pass
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

		orders = []
		if order_bys:
			for o in order_bys:
				if o.startswith('-'):
					queryset, order, nulls_last = self._parse_order_by(queryset, o[1:], request, partial='-')
				else:
					queryset, order, nulls_last = self._parse_order_by(queryset, o, request)

				if nulls_last is not None:
					if order.startswith('-'):
						desc = True
						order = order[1:]
					else:
						desc = False
					expr = F(order)
					directed_expr = expr.desc if desc else expr.asc
					order = (
						directed_expr(nulls_last=True)
						if nulls_last else
						directed_expr(nulls_first=True)
					)

				orders.append(order)

		# Append model default orders to the API orders.
		# This guarantees stable result sets when paging.
		if queryset.model._meta.ordering:
			orders += queryset.model._meta.ordering
		else:
			# If model._meta.ordering is empty, use the Binder default ordering.
			# This frequently happens due to Meta declarations that don't properly
			# inherit from BinderModel.Meta and don't specify an ordering themselves.
			orders += BinderModel.Meta.ordering
		queryset = queryset.order_by(*orders)

		return queryset


	def _annotate_obj_with_related_withs(self, obj, field_results):
		for (w, (view, ids_dict, is_singular)) in field_results.items():
			if '.' not in w:
				if is_singular:
					try:
						obj[w] = list(ids_dict[obj['id']])[0]
					except IndexError:
						obj[w] = None
				else:
					obj[w] = list(ids_dict[obj['id']])


	def _generate_meta(self, include_meta, queryset, request, pk=None):
		meta = {}

		if not pk and 'total_records' in include_meta:
			# Only 'pk' values should reduce DB server memory a (little?) bit, making
			# things faster.  Not prefetching related models here makes it faster still.
			# See also https://code.djangoproject.com/ticket/23771 and related tickets.
			meta['total_records'] = queryset.prefetch_related(None).values('pk').count()

		return meta


	def get(self, request, pk=None, withs=None, include_annotations=None):
		include_meta = request.GET.get('include_meta', 'total_records').split(',')

		queryset = self.get_queryset(request)
		if pk:
			queryset = queryset.filter(pk=int(pk))

		# No parameter repetition. Should be extended to .params too after filters have been refactored.
		for k, v in request.GET.lists():
			if not k.startswith('.') and len(v) > 1:
				raise BinderRequestError('Query parameter `{}` may not be repeated.'.format(k))

		#### soft-deletes
		queryset = self.filter_deleted(queryset, pk, request.GET.get('deleted'), request)

		#### annotations
		if include_annotations is None:
			include_annotations = self._parse_include_annotations(request)
		queryset = annotate(queryset, request, include_annotations.get(''))

		#### filters
		filters = {k.lstrip('.'): v for k, v in request.GET.lists() if k.startswith('.')}
		for field, values in filters.items():
			for v in values:
				q, distinct = self._parse_filter(field, v, request, include_annotations)
				queryset = queryset.filter(q)
				if distinct:
					queryset = queryset.distinct()

		#### search
		if 'search' in request.GET:
			queryset = self.search(queryset, request.GET['search'], request)

		queryset = self.order_by(queryset, request)

		meta = self._generate_meta(include_meta, queryset, request, pk)

		queryset = self._paginate(queryset, request)

		#### with
		# parse wheres from request
		extras, extras_mapping, extras_reverse_mapping, field_results = self._get_withs(queryset, withs, request=request, include_annotations=include_annotations)

		data = self._get_objs(queryset, request=request, annotations=include_annotations.get(''))
		for obj in data:
			self._annotate_obj_with_related_withs(obj, field_results)

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

		response_data = {'data': data, 'with': extras, 'with_mapping': extras_mapping, 'with_related_name_mapping': extras_reverse_mapping, 'meta': meta, 'debug': debug}

		self._sanity_check_meta_results(request, response_data)

		return JsonResponse(response_data)


	# Hack to auto-detect and inform people when they are accidentally
	# misusing Q() objects which produce multiple records due to
	# joining in the permission view.  This could be fixed by always
	# adding a distinct() call like Binder did originally, but that
	# is hell from a performance standpoint.  The point of Q object
	# support was to improve performance, so I think it is better to
	# simply detect the situation and let people fix their scopes by
	# returning querysets in such situations, instead.
	def _sanity_check_meta_results(self, request, response_data):
		meta = response_data['meta']
		data = response_data['data']

		try:
			limit = int(request.GET.get('limit', 0))
		except ValueError:
			limit = self.limit_default
		offset = int(request.GET.get('offset') or 0)

		if 'total_records' in meta and meta['total_records'] > len(data) and len(data) < limit and (offset + limit) < meta['total_records']:
			logger.error('Detected anomalous total record count versus data response length.  Please check if there are any scopes returning Q() objects which follow one-to-many links!')



	def binder_validation_error(self, obj, validation_error, pk=None):
		model_name = self.get_model_view(obj.__class__)._model_name()

		return BinderValidationError({
			model_name: {
				obj.pk if pk is None else pk: {
					f: [
						{'code': e.code, 'message': e.messages[0]}
						for e in el
					]
					for f, el in validation_error.error_dict.items()
				}
			}
		})



	def _abort_when_standalone_validation(self, request):
		"""Raise a `BinderSkipSave` exception when this is a standalone request."""
		if 'validate' in params:
			if self.allow_standalone_validation:
				params = QueryDict(request.body)
				raise BinderSkipSave
			else:
				raise BinderRequestError('Standalone validation not enabled. You must enable this feature explicitly.')



	# Deserialize JSON to Django Model objects.
	# obj: Model object to update (for PUT), newly created object (for POST)
	# values: Python dict of {field name: value} (parsed JSON)
	# Output: Python dict representation of the updated object
	def _store(self, obj, values, request, ignore_unknown_fields=False, pk=None):
		deferred_m2ms = {}
		ignored_fields = []
		validation_errors = []

		if obj.pk is None:
			self._require_model_perm('add', request, obj.pk)
		else:
			self._require_model_perm('change', request, obj.pk)

		def store_field(obj, field, value, request, pk=pk):
			try:
				func = getattr(self, '_store__' + field)
			except AttributeError:
				func = self._store_field
			return func(obj, field, value, request, pk=pk)

		def store_m2m_field(obj, field, value, request):
			try:
				func = getattr(self, '_store_m2m__' + field)
			except AttributeError:
				func = self._store_m2m_field
			return func(obj, field, value, request)

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


		if validation_errors:
			raise sum(validation_errors, None)

		try:
			obj.save()
		except ValidationError as ve:
			validation_errors.append(self.binder_validation_error(obj, ve, pk=pk))


		for field, value in deferred_m2ms.items():
			try:
				store_m2m_field(obj, field, value, request)
			except BinderValidationError as bve:
				validation_errors.append(bve)

		if validation_errors:
			raise sum(validation_errors, None)

		# Skip re-fetch and serialization via get_objs if we're in
		# multi-put (data is discarded!).
		if getattr(request, '_is_multi_put', False):
			return None

		# Permission checks are done at this point, so we can avoid get_queryset()
		include_annotations = self._parse_include_annotations(request)
		data = self._get_objs(
			annotate(self.model.objects.filter(pk=obj.pk), request, include_annotations.get('')),
			request=request,
			annotations=include_annotations.get(''),
		)[0]
		data['_meta'] = {'ignored_fields': ignored_fields}
		return data



	# NOTE: This is misnamed because it also stores the reverse side
	# of OneToOne fields.
	def _store_m2m_field(self, obj, field, value, request):
		validation_errors = []

		# Can't use isinstance() because apparantly ManyToManyDescriptor is a subclass of
		# ReverseManyToOneDescriptor. Yes, really.
		if getattr(obj._meta.model, field).__class__ == models.fields.related.ReverseManyToOneDescriptor:
			#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
			if any(v for v in value if v < 0):
				return
			# If the m2m to be set is actually a reverse FK relation, we need to do extra magic.
			# We figure out if the remote objects are added or removed. The added ones, we modify/save
			# explicitly rather than using the reverse relation manager, otherwise the history layer
			# doesn't see the changes. The same goes for the removed objects, except there we also
			# DELETE them if the FK is non-nullable. Interesting stuff.
			obj_field = getattr(obj, field)
			old_ids = set(obj_field.values_list('id', flat=True))
			new_ids = set(value)

			rmobjs = obj_field.model.objects.filter(id__in=old_ids - new_ids)
			# Skip already softdeleted objects for models which
			# support softdeletion (this could be a lot of records)
			if any([f.name == 'deleted' for f in obj_field.model._meta.fields]):
				rmobjs = rmobjs.exclude(deleted=True)

			for rmobj in rmobjs:
				rmobj_view = self.get_model_view(rmobj.__class__)
				method = getattr(rmobj, '_binder_unset_relation_{}'.format(obj_field.field.name), None)
				if callable(method):
					try:
						method(request)
					except BinderValidationError as bve:
						validation_errors.append(bve)
				elif obj_field.field.null:
					try:
						rmobj_view._store(rmobj, {obj_field.field.name: None}, request)
					except BinderValidationError as bve:
						validation_errors.append(bve)
				else:
					# Actually use the view to delete this, to not duplicate the deletion logic here
					rmobj_view.delete_obj(rmobj, False, request)


			for addobj in obj_field.model.objects.filter(id__in=new_ids - old_ids):
				setattr(addobj, obj_field.field.name, obj)
				try:
					addobj.save()
				except ValidationError as ve:
					validation_errors.append(self.binder_validation_error(addobj, ve))
				else:
					addobj.save()
		elif getattr(obj._meta.model, field).__class__ == models.fields.related.ReverseOneToOneDescriptor:
			#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
			if any(v for v in value if v is not None and v < 0):
				return

			field_descriptor = getattr(obj._meta.model, field)
			if value[0] is None:
				try:
					getattr(obj, field).delete()
				except ObjectDoesNotExist:
					pass
			else:
				remote_obj = field_descriptor.related.remote_field.model.objects.get(pk=value[0])
				setattr(remote_obj, field_descriptor.related.remote_field.name, obj)
				try:
					remote_obj.save()
					remote_obj.refresh_from_db()
				except ValidationError as ve:
					validation_errors.append(self.binder_validation_error(remote_obj, ve))
		elif any(f.name == field for f in self._get_reverse_relations()):
			#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
			if any(v for v in value if v < 0):
				return
			getattr(obj, field).set(value)
		elif any(f.name == field for f in self.model._meta.many_to_many):
			# Only try saving an m2m field if the base model field save was succesfull (checked by looking if it has id)
			if obj.id:
				getattr(obj, field).set(value)
		else:
			setattr(obj, field, value)

		if validation_errors:
			raise sum(validation_errors, None)




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
		if field in [
			'id', 'pk', 'deleted', '_meta',
			*self.unwritable_fields,
			*self.shown_properties,
			*self.file_fields,
			*self.annotations(request),
		]:
			raise BinderReadOnlyFieldError(self.model.__name__, field)

		if obj.pk is not None and field in self.unupdatable_fields:
			raise BinderReadOnlyFieldError(self.model.__name__, field)

		# Regular fields and FKs
		for f in self.model._meta.fields:
			if f.name == field:
				if isinstance(f, models.ForeignKey):
					if not (value is None or isinstance(value, int)):
						raise BinderFieldTypeError(self.model.__name__, field)

					# Previously, this value was updated using the following code:
					# - setattr(obj, f.attname, value)
					# The problem is that this updates the obj id, but not the related object itself
					# This is not a problem if the object is not evaluated yet before (Since it will be gotten from
					# the db afterwards). But it is a problem if the object is evaluated, since it then has the old
					# value cached.
					if value is None:
						# Special case if the value is none, then we can set the field name to none as well.
						# Updating f.name, will also update the underlaying pk
						setattr(obj, f.name, None)
					else:
						# Otherwise, update the relation
						try:
							setattr(obj, f.name, f.remote_field.model.objects.get(pk=value))
						except f.remote_field.model.DoesNotExist:
							# Hack, set the id directly. This does the actual check, and throws the BinderError in
							# the same way the old case has.
							setattr(obj, f.attname, value)
				elif isinstance(f, models.IntegerField):
					if value is None or value == '':
						value = None
					else:
						try:
							value = int(value)
						except ValueError:
							model_name = self.get_model_view(obj.__class__)._model_name()
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
							model_name = self.get_model_view(obj.__class__)._model_name()
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
					except TypeError:
						raise BinderFieldTypeError(self.model.__name__, field)
					except ValidationError as ve:
						# This would be nice, but this particular validation error
						# has no error dict... (TODO FIXME)
						# raise self.binder_validation_error(obj, ve, pk=pk)

						model_name = self.get_model_view(obj.__class__)._model_name()
						raise BinderValidationError({
							model_name: {
								obj.pk if pk is None else pk: {
									f.name: [
										{'code': ve.code, 'message': ve.messages[0]}
									]
								}
							}
						})
					setattr(obj, f.attname, value)
				return False

		# m2ms/reverse relations
		for f in list(self.model._meta.many_to_many) + list(self._get_reverse_relations()):
			if f.name == field:
				# Force it to be seen as a deferred field
				if isinstance(obj._meta.get_field(field), models.OneToOneRel):
					if value is not None and not isinstance(value, int):
						raise BinderFieldTypeError(self.model.__name__, field)

					value = [value]
				elif not (isinstance(value, list) and all(isinstance(v, int) for v in value)):
					raise BinderFieldTypeError(self.model.__name__, field)
				# FIXME
				# Check if the ids being saved as m2m actually exist. This kinda sucks, it would be much
				# better to have this handled by the DB transaction layer. Which DOES actually check and
				# enforce this, but on error this raises an exception at a point where we can't catch it.
				# So yeah, we kludge around here. :(
				#ids = set(value)
				#### XXX FIXME XXX ugly quick fix for reverse relation + multiput issue
				ids = set(v for v in value if v is not None and v > 0)
				ids -= set(obj._meta.get_field(field).remote_field.model.objects.filter(id__in=ids).values_list('id', flat=True))
				if ids:
					field_name = obj._meta.get_field(field).remote_field.model.__name__
					model_name = self.get_model_view(obj.__class__)._model_name()
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

		data = body.get('with', {})
		if not isinstance(data, dict):
			raise BinderRequestError('with should be a dict')

		deletions = body.get('with_deletions', {})
		if not isinstance(deletions, dict):
			raise BinderRequestError('with_deletions should be a dict')

		modelname = self._model_name()

		try:
			data[modelname] = body['data']
		except KeyError:
			pass
		else:
			if not isinstance(data[modelname], list):
				raise BinderRequestError('data should be a list')

		try:
			deletions[modelname] = body['deletions']
		except KeyError:
			pass
		else:
			if not isinstance(deletions[modelname], list):
				raise BinderRequestError('deletions should be a list')

		return data, deletions



	# Sort object values by model/id
	def _multi_put_collect_objects(self, data):
		objects = {}
		for modelname, objs in data.items():
			if not isinstance(objs, list):
				raise BinderRequestError('with.{} value should be a list'.format(modelname))

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


	def _multi_put_override_superclass(self, objects):
		overrides = {}

		# Collect overrides
		for (cls, mid), data in objects.items():
			for subcls in getsubclasses(cls):
				# Get key of field pointing to subclass
				subkey = subcls._meta.pk.remote_field.name
				# Get id of subclass
				subid = data.pop(subkey, None)
				if subid is None:
					continue
				# Check if class is in objects
				if (subcls, subid) not in objects:
					continue
				# Add to overrides
				overrides[(cls, mid)] = (subcls, subid)

		# Move data to overrides
		for source in list(overrides):
			# Follow overrides to final override
			target = overrides[source]
			while target in overrides:
				target = overrides[target]
			overrides[source] = target
			# Pop data of source and set as default for target
			for key, value in objects.pop(source).items():
				objects[target].setdefault(key, value)

		# Fix foreign keys in data according to overrides
		for (cls, _), data in objects.items():
			for field in cls._meta.get_fields():
				if (
					field.name not in data or
					not field.is_relation or
					field.related_model is None
				):
					# Only look at relations that are included
					continue

				if isinstance(data[field.name], int):
					target = (field.related_model, data[field.name])
					if target in overrides:
						data[field.name] = overrides[target][1]
				elif isinstance(data[field.name], list):
					for i, mid in enumerate(data[field.name]):
						if isinstance(mid, int):
							target = (field.related_model, mid)
							if target in overrides:
								data[field.name][i] = overrides[target][1]

		return objects, overrides


	def _multi_put_convert_backref_to_forwardref(self, objects):
		for (model, mid), values in objects.items():
			for field in filter(lambda f: f.one_to_many or f.one_to_one, model._meta.get_fields()):
				if field.name in values:
					if field.one_to_many:
						if not isinstance(values[field.name], list) or not all(isinstance(v, int) for v in values[field.name]):
							raise BinderFieldTypeError(model.__name__, field.name)
						rids = values[field.name]
					elif field.one_to_one:
						if isinstance(values[field.name], int):
							rids = [values[field.name]]
						elif values[field.name] is None:
							rids = []
						else:
							raise BinderFieldTypeError(model.__name__, field.name)

					for rid in rids:
						if (field.related_model, rid) in objects:
							objects[(field.related_model, rid)][field.remote_field.name] = mid
						for submodel in getsubclasses(field.related_model):
							if (submodel, rid) in objects:
								objects[(submodel, rid)][field.remote_field.name] = mid
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

			ordered_objects += sorted(
				this_batch,
				key=lambda obj: (obj[0].__name__, sign(obj[1]), abs(obj[1])),
			)

		return ordered_objects



	def _multi_put_save_objects(self, ordered_objects, objects, request):
		new_id_map = {}
		validation_errors = []

		# Gather non-negative oids per model (unordered)
		model_oids = defaultdict(set)
		for model, oid in ordered_objects:
			if oid >= 0:
				model_oids[model].add(oid)

		# Do one big query to get and lock all the objects of each
		# type.  This saves us from querying each individual object in
		# the loop below (with one DB round trip per item).
		locked_objects = {}
		for model, oids in model_oids.items():
			# NOTE: Shouldn't we call get_queryset on the
			# corresponding view here?  That would make it
			# more consistent with non-multi-PUT and POST,
			# also requiring view permissions.
			qs = model.objects.filter(pk__in=oids).select_for_update()
			for obj in qs:
				locked_objects[(model, obj.pk)] = obj


		for model, oid in ordered_objects:
			values = objects[(model, oid)]
			logger.info('Saving {} {}'.format(model.__name__, oid))

			if oid >= 0:
				try:
					obj = locked_objects[(model, oid)]
				except KeyError:
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

			view = self.get_model_view(model)
			try:
				view._store(obj, values, request, pk=oid)
			except BinderValidationError as e:
				validation_errors.append(e)
			if oid < 0:
				new_id_map[(model, oid)] = obj.id
				for base in getmro(model)[1:]:
					if not (
						hasattr(base, 'Meta') and
						getattr(base.Meta, 'abstract', False)
					) and isinstance(base, BinderModel):
						new_id_map[(base, oid)] = obj.id
				logger.info('Saved as id {}'.format(obj.id))

		if validation_errors:
			raise sum(validation_errors, None)

		return new_id_map


	def _multi_put_id_map_add_overrides(self, new_id_map, overrides):
		for source, target in overrides.items():
			if target in new_id_map:
				new_id_map[source] = new_id_map[target]


	def _multi_put_deletions(self, deletions, new_id_map, request):
		for modelname, pks in deletions.items():
			if not isinstance(pks, list):
				raise BinderRequestError(
					'with_deletions.{} value should be a list'
					.format(modelname)
				)

			try:
				model = self.router.name_models[modelname]
			except KeyError:
				raise BinderRequestError(
					'with_deletions.{} is not a valid model name'
					.format(modelname)
				)

			model_view = self.get_model_view(model)

			for i, pk in enumerate(pks):
				if not isinstance(pk, int):
					raise BinderRequestError(
						'with_deletions.{}[{}] should be a numeric id'
						.format(modelname, i)
					)

				if pk < 0:
					try:
						pk = new_id_map.pop((model, pk))
					except KeyError:
						raise BinderRequestError(
							'with_deletions.{}[{}] refers to unspecified '
							'{}[{}]'
							.format(modelname, i, modelname, pk)
						)

				try:
					obj = model.objects.select_for_update().get(pk=pk)
				except ObjectDoesNotExist:
					raise BinderNotFound('{}[{}]'.format(modelname, pk))

				if hasattr(obj, 'deleted') and obj.deleted:
					raise BinderIsDeleted()

				model_view.delete_obj(obj, False, request)

		return new_id_map


	def multi_put(self, request):
		logger.info('ACTIVATING THE MULTI-PUT!!!!!')

		# Hack to communicate to _store() that we're not interested in
		# the new data (for perf reasons).
		request._is_multi_put = True

		data, deletions = self._multi_put_parse_request(request)
		objects = self._multi_put_collect_objects(data)
		objects, overrides = self._multi_put_override_superclass(objects) # model inheritance
		objects = self._multi_put_convert_backref_to_forwardref(objects)
		dependencies = self._multi_put_calculate_dependencies(objects)
		ordered_objects = self._multi_put_order_dependencies(dependencies)
		new_id_map = self._multi_put_save_objects(ordered_objects, objects, request) # may raise validation errors
		self._multi_put_id_map_add_overrides(new_id_map, overrides) # model inheritance
		new_id_map = self._multi_put_deletions(deletions, new_id_map, request) # may raise validation errors

		self._abort_when_standalone_validation(request)

		output = defaultdict(list)
		for (model, oid), nid in new_id_map.items():
			output[self.get_model_view(model)._model_name()].append((oid, nid))

		return JsonResponse({'idmap': output})

	def _get_request_values(self, request):
		return jsonloads(request.body)

	def put(self, request, pk=None):
		if pk is None:
			return self.multi_put(request)

		self._require_model_perm('change', request, pk)

		values = self._get_request_values(request)

		try:
			obj = self.get_queryset(request).select_for_update().get(pk=int(pk))
			# Permission checks are done at this point, so we can avoid get_queryset()
			include_annotations = self._parse_include_annotations(request)
			old = self._get_objs(
				annotate(self.model.objects.filter(pk=int(pk)), request, include_annotations.get('')),
				request,
				include_annotations.get(''),
			)[0]
		except ObjectDoesNotExist:
			raise BinderNotFound()

		if hasattr(obj, 'deleted') and obj.deleted:
			raise BinderIsDeleted()

		data = self._store(obj, values, request)

		self._abort_when_standalone_validation(request)

		new = dict(data)
		new.pop('_meta', None)

		meta = data.setdefault('_meta', {})
		meta['with'], meta['with_mapping'], meta['with_related_name_mapping'], field_results = self._get_withs([new['id']], request=request, withs=None)
		self._annotate_obj_with_related_withs(data, field_results)

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

		values = self._get_request_values(request)

		data = self._store(self.model(), values, request)

		self._abort_when_standalone_validation(request)

		new = dict(data)
		new.pop('_meta', None)

		meta = data.setdefault('_meta', {})
		meta['with'], meta['with_mapping'], meta['with_related_name_mapping'], field_results = self._get_withs([new['id']], request=request, withs=None)
		self._annotate_obj_with_related_withs(data, field_results)

		logger.info('POST created {} #{}'.format(self._model_name(), data['id']))
		for c in self._obj_diff({}, new, '{}[{}]'.format(self._model_name(), data['id'])):
			logger.debug('POST ' + c)

		return JsonResponse(data)



	def delete(self, request, pk=None, undelete=False, skip_body_check=False):
		if not undelete:
			self._require_model_perm('delete', request)

		if pk is None:
			raise BinderMethodNotAllowed()

		if not skip_body_check:
			# FIXME: ugly workaround, remove when Django bug fixed
			# Try/except because https://code.djangoproject.com/ticket/27005
			try:
				if request.body not in (b'', b'{}'):
					raise BinderRequestError('{}DELETE body must be empty or empty json object.'.format('UN' if undelete else ''))
			except ValueError:
				pass

		try:
			obj = self.get_queryset(request).select_for_update().get(pk=int(pk))
		except ObjectDoesNotExist:
			raise BinderNotFound()

		self.delete_obj(obj, undelete, request)

		self._abort_when_standalone_validation(request)

		logger.info('{}DELETEd {} #{}'.format('UN' if undelete else '', self._model_name(), pk))

		return HttpResponse(status=204)  # No content



	def delete_obj(self, obj, undelete, request):
		return self.soft_delete(obj, undelete, request)



	def soft_delete(self, obj, undelete, request):
		# Not only for soft delets, actually handles all deletions
		try:
			if obj.deleted and not undelete:
				raise BinderIsDeleted()
			if not obj.deleted and undelete:
				raise BinderIsNotDeleted()
		except AttributeError:
			if undelete:  # Should never happen
				raise BinderMethodNotAllowed()
			else:
				try:
					obj.delete()
				except models.ProtectedError as e:
					protected_objects = defaultdict(list)
					for prot in e.protected_objects:
						protected_objects[self.get_model_view(prot.__class__)._model_name()] += [prot.id]
					raise BinderValidationError({
						self._model_name(): {
							obj.pk: {
								'id': [{
									'code': 'protected',
									'message': 'Could not delete object {}'.format(obj.id),
									'objects': protected_objects,
								}]
							}
						}
					})
				return

		obj.deleted = not undelete
		try:
			obj.save()
		except ValidationError as ve:
			raise self.binder_validation_error(obj, ve)



	def dispatch_file_field(self, request, pk=None, file_field=None):
		if not request.method in ('GET', 'POST', 'DELETE'):
			raise BinderMethodNotAllowed()

		if isinstance(pk, self.model):
			obj = pk
			pk = obj.pk
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

			try:
				if file.size > self.max_upload_size * 10**6:
					raise BinderFileSizeExceeded(self.max_upload_size)

				field = self.model._meta.get_field(file_field_name)

				if getattr(field, 'allowed_extensions', None) is not None:
					extension = None if '.' not in file.name else file.name.split('.')[-1]

					if extension not in field.allowed_extensions:
						raise BinderFileTypeIncorrect([{'extension': t} for t in field.allowed_extensions])

				if isinstance(field, models.fields.files.ImageField):
					try:
						img = Image.open(file)
					except Exception:
						raise BinderImageError('Could not parse the file as an image.')

					format = img.format.lower()
					if not format in ('png', 'gif', 'jpeg'):
						raise BinderFileTypeIncorrect([{'extension': t, 'mimetype': 'image/' + t} for t in ['jpeg', 'png', 'gif']])

					width, height = img.size
					if format == 'jpeg':
						img2 = image_transpose_exif(img)

						if img2 != img:
							file.seek(0)  # Do not append to the existing file!
							file.truncate()
							img2.save(file, 'jpeg')
							img = img2

					# Determine resize threshold
					try:
						max_size = self.image_resize_threshold[file_field_name]
					except TypeError:
						max_size = self.image_resize_threshold

					try:
						max_width, max_height = max_size
					except (TypeError, ValueError):
						max_width, max_height = max_size, max_size

					try:
						format_override = self.image_format_override.get(file_field_name)
					except AttributeError:
						format_override = self.image_format_override

					changes = False

					# FIXME: hardcoded max
					# Flat out refuse images exceeding this size, to prevent DoS.
					width_limit, height_limit = max(max_width, 4096), max(max_height, 4096)
					if width > width_limit or height > height_limit:
						raise BinderImageSizeExceeded(width_limit, height_limit)

					# Resize images that are too large.
					if width > max_width or height > max_height:
						img.thumbnail((max_width, max_height), Image.ANTIALIAS)
						logger.info('image dimensions ({}x{}) exceeded ({}, {}), resizing.'.format(width, height, max_width, max_height))
						if img.mode not in ["1", "L", "P", "RGB", "RGBA"]:
							img = img.convert("RGB")
						if format != 'jpeg':
							format = 'png'
						changes = True

					if format_override and format != format_override:
						format = format_override
						changes = True

					filename = '{}.{}'.format(os.path.basename(file.name), format)

					if changes:
						file = io.BytesIO()
						img.save(file, format)
				else:
					filename = file.name

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

				file_field.delete(save=False)
				# This triggers a save on obj
				file_field.save(filename, django.core.files.File(file))

				# FIXME: duplicate code
				new_hash = hashlib.sha256()
				for c in file_field.file.chunks():
					new_hash.update(c)
				new_hash = new_hash.hexdigest()

				logger.info('POST updated {}[{}].{}: {} -> {}'.format(self._model_name(), pk, file_field_name, old_hash, new_hash))
				path = self.router.model_route(self.model, obj.id, field)

				# {duplicate-binder-file-field-hash-code}
				if isinstance(field, BinderFileField):
					path += '?h={}&content_type={}&filename={}'.format(
						file_field.content_hash,
						file_field.content_type or '',
						os.path.basename(file_field.name),
					)

				return JsonResponse( {"data": {file_field_name: path}} )

			except ValidationError as ve:
				raise self.binder_validation_error(obj, ve, pk=pk)

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
