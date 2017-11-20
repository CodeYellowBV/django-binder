import re
import warnings

from django.db import models
from django.contrib.postgres.fields import CITextField
from django.db.models import signals

from . import history



class CaseInsensitiveCharField(CITextField):
	def __init__(self, *args, **kwargs):
		warnings.warn(DeprecationWarning('CaseInsensitiveCharField is deprecated, use django.contrib.postgres.fields.CITextField instead'))
		return super().__init__(*args, **kwargs)


class UpperCaseCharField(CITextField):
	def get_prep_value(self, value):
		value = super().get_prep_value(value)
		if value is None:
			return None
		return value.upper()



class LowerCaseCharField(CITextField):
	def get_prep_value(self, value):
		value = super().get_prep_value(value)
		if value is None:
			return None
		return value.lower()



class ChoiceEnum(object):
	def __init__(self, *args, **kwargs):
		self.items = kwargs
		for k in args:
			if k == '':
				self.items['NONE'] = ''
			else:
				self.items[re.sub('[ /+-]', '_', k).upper()] = k
		self.__dict__.update(self.items)

	def choices(self):
		return tuple(sorted((v, k) for k, v in self.items.items()))

	def name(self, value, default=None):
		if value is None:
			return default
		for k, v in self.items.items():
			if v == value:
				return k
		raise ValueError()



class BinderModel(models.Model):
	def binder_concrete_fields_as_dict(self):
		fields = {}
		for field in [f for f in self._meta.get_fields() if f.concrete and not f.many_to_many]:
			if isinstance(field, models.ForeignKey):
				fields[field.name] = getattr(self, field.name + '_id')
			elif isinstance(field, models.FileField):
				fields[field.name] = str(getattr(self, field.name))
			else:
				fields[field.name] = getattr(self, field.name)
		return fields

	def binder_serialize_m2m_field(self, field):
		if isinstance(field, str):
			field = getattr(self, field)

		try:
			extended_m2m = field.through.binder_is_binder_model
		except AttributeError:
			extended_m2m = False

		# Regular many to many; get a list of the target ids.
		if not extended_m2m:
			return set(field.values_list('id', flat=True))

		# Extended m2m; get dicts of the intermediary join table objects
		data = list(field.through.objects.filter(**{field.source_field.name: self.id}).values())
		# Then, modify them to leave out the PKs and source ids. Also, rename target ids to 'id'.
		for d in data:
			d.pop('id')
			d.pop(field.source_field.name + '_id')
			d['id'] = d.pop(field.target_field.name + '_id')

		return set(sorted(d.items()) for d in data)

	binder_is_binder_model = True

	class Binder:
		history = False

	class Meta:
		abstract = True
		ordering = ['id']



def history_obj_post_init(sender, instance, **kwargs):
	instance._history = instance.binder_concrete_fields_as_dict()

	if not instance.pk:
		instance._history = {k: history.NewInstanceField for k in instance._history}



def history_obj_post_save(sender, instance, **kwargs):
	for field_name, new_value in instance.binder_concrete_fields_as_dict().items():
		old_value = instance._history[field_name]
		if old_value != new_value:
			history.change(sender, instance.pk, field_name, old_value, new_value)
			instance._history[field_name] = new_value



def history_obj_post_delete(sender, instance, **kwargs):
	history.change(sender, instance.pk, 'pk', instance.pk, None)



def history_obj_m2m_changed(sender, instance, action, reverse, model, pk_set, **kwargs):
	if reverse or action not in ('pre_add', 'pre_remove', 'pre_clear'):
		return

	# Find the corresponding field on the instance
	field = [f for f in instance._meta.get_fields() if f.concrete and f.many_to_many and f.remote_field.through == sender][0]

	history.change(instance.__class__, instance.id, field.name, history.DeferredM2M, history.DeferredM2M)



# FIXME: remove
def install_m2m_signal_handlers(model):
	warnings.warn(DeprecationWarning('install_m2m_signal_handlers() is deprecated, call install_history_signal_handlers() instead!'))
	install_history_signal_handlers(model)



def install_history_signal_handlers(model):
	if model is None:
		return

	if not model.Meta.abstract and model.Binder.history:
		signals.post_init.connect(history_obj_post_init, model)
		signals.post_save.connect(history_obj_post_save, model)
		signals.post_delete.connect(history_obj_post_delete, model)

		for field in model._meta.get_fields():
			if field.many_to_many and field.concrete:
				signals.m2m_changed.connect(history_obj_m2m_changed, getattr(model, field.name).through)

	for sub in model.__subclasses__():
		install_m2m_signal_handlers(sub)
