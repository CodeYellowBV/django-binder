from collections import namedtuple

from django.db.models import F, Aggregate
from django.db.models.signals import post_save, class_prepared
from django.db.models.expressions import BaseExpression
from django.conf import settings

from .signal import apps_ready


Dep = namedtuple('Dep', ['model', 'fields', 'rev_path', 'rev_field'])


def get_deps_base(model, expr):
	"""
	Given a model and an expr yield all changes that could affect the result
	of this expr.

	A change is defined as a 4-tuple of (model, changed, rev_path, rev_field).
	"""
	from ..plugins.loaded_values import LoadedValuesMixin

	if not issubclass(model, LoadedValuesMixin):
		raise ValueError(f'{model} should inherit from LoadedValuesMixin if you want to use it in a stored field')

	if isinstance(expr, Aggregate):
		expr, = expr.source_expressions

	if isinstance(expr, F):
		head, sep, tail = expr.name.partition('__')

		field = model._meta.get_field(head)
		if not sep and field.is_relation:
			sep = '__'
			tail = 'id'

		if not sep:
			if head != 'id':
				yield Dep(model, {head}, 'id', 'id')
			return

		if not field.is_relation:
			raise ValueError(f'expected {model.__name__}.{field} to be a relation')

		if field.one_to_many:
			yield Dep(field.related_model, {field.remote_field.name}, 'id', field.remote_field.column)
		elif field.many_to_one:
			yield Dep(model, {head}, 'id', 'id')
		else:
			raise ValueError('unsupported type of relation')

		for dep in get_deps(field.related_model, F(tail)):
			if dep.rev_path != 'id':
				yield dep._replace(rev_path=f'{head}__{dep.rev_path}')
			elif field.one_to_many:
				yield dep._replace(rev_field=field.remote_field.column)
			else:
				yield dep._replace(rev_path=head)

	else:
		raise ValueError(f'cannot infer deps for {expr!r}')


def get_deps(*args, **kwargs):
	deps = {}
	for dep in get_deps_base(*args, **kwargs):
		key = dep._replace(fields=None)
		try:
			base_dep = deps[key]
		except KeyError:
			deps[key] = dep
		else:
			deps[key] = dep._replace(fields=base_dep.fields | dep.fields)
	return deps.values()


class Stored:

	def __init__(self, expr):
		self.expr = expr

	def __set_name__(self, model, name):
		from ..views import fix_output_field

		if 'binder.stored' not in settings.INSTALLED_APPS:
			raise ValueError('cannot use Stored if \'binder.stored\' is not in INSTALLED_APPS')

		# We dont actually want this to be the attribute
		delattr(model, name)

		# Get field
		fix_output_field(self.expr, model)
		if isinstance(self.expr, F):
			field = self.expr._output_field_or_none
		elif isinstance(self.expr, BaseExpression):
			field = self.expr.field
		else:
			raise ValueError(
				'{}.{} is not a valid django query expression'
				.format(model.__name__, name)
			)

		# Make blank & nullable copy of field
		_, _, args, kwargs = field.deconstruct()
		kwargs['blank'] = True
		kwargs['null'] = True
		field = type(field)(*args, **kwargs)
		field.__binder_stored_expr = self.expr

		# Add the field
		def add_field(**kwargs):
			class_prepared.disconnect(add_field, sender=model)

			model.add_to_class(name, field)

		class_prepared.connect(add_field, sender=model, weak=False)

		# Add triggers for deps
		def add_triggers(**kwargs):
			apps_ready.disconnect(add_triggers)

			register_init(model, name, self.expr)
			for dep in get_deps(model, self.expr):
				register_dep(model, name, self.expr, dep)

		apps_ready.connect(add_triggers, weak=False)


def update_queryset(queryset, name, expr):
	for pk, value in queryset.annotate(value=expr).values_list('pk', 'value'):
		queryset.model.objects.filter(pk=pk).update(**{name: value})


def register_init(model, name, expr):
	def update_values(instance, **kwargs):
		if instance.field_changed('id'):
			update_queryset(model.objects.filter(id=instance.id), name, expr)

	post_save.connect(update_values, sender=model, weak=False)


def register_dep(model, name, expr, dep):
	def update_values(instance, **kwargs):
		if instance.field_changed('id', *dep.fields):
			ids = [getattr(instance, dep.rev_field)]
			if instance.field_changed(dep.rev_field):
				ids.append(instance.get_old_value(dep.rev_field))
			update_queryset(model.objects.filter(id__in=ids), name, expr)

	post_save.connect(update_values, sender=dep.model, weak=False)
