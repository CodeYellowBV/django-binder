from collections import namedtuple, defaultdict
import logging
import re

from django.db import connection
from django.db.models import Value, F
from django.conf import settings

from ...decorators import view_logger, handle_exceptions, allowed_methods
from ...json import JsonResponse
from ...views import ModelView, annotate, split_par_aware, RelatedModel
from ...exceptions import BinderRequestError


logger = logging.getLogger()


LIMIT_DEFAULT = 20
LIMIT_MAX = None


FakeRequest = namedtuple('FakeRequest', ['GET'])
CombinedOrderBy = namedtuple('CombinedOrderBy', ['fields', 'inverted', 'nulls_last'])


@view_logger(logger)
@handle_exceptions
@allowed_methods('GET')
def combined_view(request, router, names):
	names = names.split('/') if names else []

	# Get views per name
	views = {}
	for name in names:
		try:
			view_cls = router.model_views[router.name_models[name]]
		except KeyError:
			raise BinderRequestError(f'Unknown model: {{{name}}}')
		view = view_cls()
		view.router = router
		views[name] = view

	# No parameter repetition. Should be extended to .params too after filters have been refactored.
	for k, v in request.GET.lists():
		if not k.startswith('.') and len(v) > 1:
			raise BinderRequestError('Query parameter `{}` may not be repeated.'.format(k))

	# Parse include annotations
	include_annotations = {}

	try:
		includes = list(split_par_aware(request.GET['include_annotations']))
	except KeyError:
		includes = []

	subincludes = {name: [] for name in names}
	for include in includes:
		match = re.match(r'(\w+)(:\.|\()(.*)', include)
		if not match:
			raise BinderRequestError(f'Annotation on top model in combined view not allowed: {{include_annotations={include}}}')
		name, sep, subinclude = match.groups()
		if sep == '(':
			if not subinclude.endswith(')'):
				raise BinderRequestError(f'SyntaxError in {{include_annotations={include}}}')
			subinclude = subinclude[:-1]
		try:
			subincludes[name].append(subinclude)
		except KeyError:
			raise BinderRequestError(f'Unknown relation {{{name}}}.')

	for name in names:
		subinclude_annotations = views[name]._parse_include_annotations(FakeRequest({'include_annotations': ','.join(subincludes[name])} if subincludes[name] else {}))
		for rel, annotations in subinclude_annotations.items():
			include_annotations[f'{name}.{rel}' if rel else name] = annotations

	# Get filtered & annotated querysets per name
	querysets = {}
	for name in names:
		view = views[name]

		queryset = view.get_queryset(request)

		# soft-deletes
		queryset = view.filter_deleted(queryset, None, request.GET.get('deleted'), request)

		# annotations
		sub_include_annotations = {
			relation[len(name) + 1:]: annotations
			for relation, annotations in include_annotations.items()
			if relation == name or relation.startswith(f'{name}.')
		}
		queryset = annotate(queryset, request, sub_include_annotations.get(''))

		# filters
		filters = {
			'id' if k == f'.{name}' else k[len(name) + 2:]: v
			for k, v in request.GET.lists()
			if k == f'.{name}' or k.startswith(f'.{name}.')
		}
		for field, values in filters.items():
			for v in values:
				q, distinct = view._parse_filter(field, v, request, sub_include_annotations)
				queryset = queryset.filter(q)
				if distinct:
					queryset = queryset.distinct()

		# search
		if 'search' in request.GET:
			queryset = view.search(queryset, request.GET['search'], request)

		querysets[name] = queryset

	# Meta
	include_meta = request.GET.get('include_meta', 'total_records').split(',')
	meta = {}
	if 'total_records' in include_meta:
		meta['total_records'] = sum(
			queryset.prefetch_related(None).values('pk').count()
			for queryset in querysets.values()
		)

	# Parse pagination
	limit = LIMIT_DEFAULT
	if request.GET.get('limit') == 'none':
		limit = None
	elif 'limit' in request.GET:
		try:
			limit = int(request.GET.get('limit'))
			if limit < 0:
				raise BinderRequestError('Limit must be nonnegative.')
		except ValueError:
			raise BinderRequestError('Invalid characters in limit.')

	if LIMIT_MAX:
		if not limit or limit > LIMIT_MAX:
			raise BinderRequestError('Limit exceeds maximum of {} for this view.'.format(LIMIT_MAX))

	try:
		offset = int(request.GET.get('offset') or 0)
		if offset < 0:
			raise BinderRequestError('Offset must be nonnegative.')
	except ValueError:
		raise BinderRequestError('Invalid characters in offset.')

	# Combining, ordering & pagination
	try:
		order_bys = list(split_par_aware(request.GET['order_by']))
	except KeyError:
		order_bys = []
	# Add id if its not in there yet to make sure ordering is deterministic
	if 'id' not in order_bys and '-id' not in order_bys:
		order_bys.append('id')

	for i, order_by in enumerate(order_bys):
		# Handle modifiers first
		inverted = False
		if order_by.startswith('-'):
			inverted = True
			order_by = order_by[1:]

		if order_by.endswith('__nulls_last'):
			order_by = order_by[:-len('__nulls_last')]
			nulls_last = True
		elif order_by.endswith('__nulls_first'):
			order_by = order_by[:-len('__nulls_first')]
			nulls_last = False
		else:
			nulls_last = None

		# Parse multiple order bys if surrounded by parenthesis, otherwise same order by for all names
		if order_by.startswith('('):
			if not order_by.endswith(')'):
				raise BinderRequestError(f'Unmatched left parenthesis in order by. {{order_by={order_by}}}')
			order_by = order_by[1:-1].split(',')
			if len(order_by) != len(names):
				raise BinderRequestError(f'Invalid amount of params in order by, should match the amount of models. {{order_by=({",".join(order_by)})}}')
		else:
			order_by = [order_by for _ in names]

		order_bys[i] = CombinedOrderBy(dict(zip(names, order_by)), inverted, nulls_last)

	queries = []
	params = []
	for i, name in enumerate(names):
		queryset = querysets[name]
		suborder_bys = []
		id_expr = F('id') * Value(len(names)) + Value(i)
		for order_by in order_bys:
			# So this is a bit of a hack, filtering on annotations is normally
			# only possible on the top model so binder assumes this is always
			# the case which is valid. However in our case we want to always
			# filter on the submodel. We thus patch the annotations function
			# temporarily
			old_annotations = views[name].annotations
			views[name].annotations = lambda *args, **kwargs: include_annotations.get(name)
			try:
				queryset, field, nulls_last = views[name]._parse_order_by(queryset, order_by.fields[name], request)
			finally:
				views[name].annotations = old_annotations
			suborder_bys.append(id_expr if field == 'id' else F(field))
		queryset = queryset.values_list(
			id_expr,
			*suborder_bys,
		)
		compiler = queryset.query.get_compiler(using=queryset.db)
		query, subparams = compiler.as_sql()
		queries.append(query)
		params.extend(subparams)

	query = (
		'SELECT combined.id ' +
		'FROM (' + ' UNION '.join(f"({query})" for query in queries) + ') AS combined (id' + ''.join(f', ordering_{i}' for i in range(len(order_bys))) + ')' +
		(' ORDER BY ' + ', '.join(
			f'combined.ordering_{i}' +
			{True: ' DESC', False: ' ASC'}[order_by.inverted] +
			{True: ' NULLS LAST', False: ' NULLS FIRST', None: ''}[order_by.nulls_last]
			for i, order_by in enumerate(order_bys)
		) if order_bys else '')
	)
	if limit is not None:
		query += ' LIMIT %s'
		params.append(limit)
	if offset != 0:
		query += ' OFFSET %s'
		params.append(offset)
	params = tuple(params)

	with connection.cursor() as cursor:
		cursor.execute(query, params)
		objs = cursor.fetchall()

	# Get base data
	data = []
	for pk, in objs:
		name_pk, name_index = divmod(pk, len(names))
		name = names[name_index]
		data.append({
			'id': pk,
			**{name_: name_pk if name_ == name else None for name_ in names},
		})

	# Get withs

	# Custom view so that we can reuse as much of the with logic as possible
	class CombinedView(ModelView):

		def _follow_related(self, fieldspec):
			if not fieldspec:
				return ()

			if isinstance(fieldspec, str):
				fieldspec = fieldspec.split('.')

			fieldname, *fieldspec = fieldspec

			if fieldname not in names:
				raise BinderRequestError(f'Field is not a related object {{{fieldname}}}.')

			view = views[name]
			return (RelatedModel(fieldname, view.model, None),) + view._follow_related(fieldspec)

		def _get_with_ids(self, pks, request, include_annotations, with_map, where_map):
			rel_ids_by_field_by_id = defaultdict(lambda: defaultdict(list))

			for pk in pks:
				rel_pk, rel_index = divmod(pk, len(names))
				rel_name = names[rel_index]
				if rel_name in with_map:
					rel_ids_by_field_by_id[rel_name][pk].append(rel_pk)

			result = {}
			for field, sub_fields in with_map.items():
				view = views[field]

				result[field] = (type(view), rel_ids_by_field_by_id[field], True)

				# And recur for subrelations
				if sub_fields:
					wm_scoped = where_map.get(field)
					wm_scoped = wm_scoped['subrels'] if wm_scoped else {}

					flattened_ids = [id for ids in rel_ids_by_field_by_id[field].values() for id in ids]
					subrelations = view._get_with_ids(flattened_ids, request=request, include_annotations=include_annotations, with_map=sub_fields, where_map=wm_scoped)
					for subrelation, data in subrelations.items():
						result['.'.join([field, subrelation])] = data

			return result


	combined_view = CombinedView()
	combined_view.router = router

	extras, extras_mapping, extras_reverse_mapping, _ = combined_view._get_withs(
		pks=[obj['id'] for obj in data],
		wheres=None,
		request=request,
		withs=None,
		include_annotations=include_annotations,
	)

	# Get debug info
	debug = {'request_id': request.request_id}
	if settings.DEBUG and 'debug' in request.GET:
		debug['queries'] = ['{}s: {}'.format(q['time'], q['sql'].replace('"', '')) for q in connection.queries]
		debug['query_count'] = len(connection.queries)

	# Return response
	return JsonResponse({
		'data': data,
		'with': extras,
		'with_mapping': extras_mapping,
		'with_related_name_mapping': extras_reverse_mapping,
		'meta': meta,
		'debug': debug,
	})
