import re
from operator import itemgetter

from django.db import models
from django.db.models import signals

from . import history



class CaseInsensitiveCharField(models.CharField):
	def db_type(self, connection):
		return "citext"



class UpperCaseCharField(CaseInsensitiveCharField):
	def get_prep_value(self, value):
		value = super().get_prep_value(value)
		if value is None:
			return None
		return value.upper()



class LowerCaseCharField(CaseInsensitiveCharField):
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
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if self.Binder.history:
			self._history = self.binder_concrete_fields_as_dict()
			if not self.id:
				self._history = {k: history.NewInstanceField for k in self._history}



	binder_is_binder_model = True


	# FIXME: rename
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
			return sorted(set(field.values_list('id', flat=True)))

		# Extended m2m; get dicts of the intermediary join table objects
		data = list(field.through.objects.filter(**{field.source_field.name: self.id}).values())
		# Then, modify them to leave out the PKs and source ids. Also, rename target ids to 'id'.
		for d in data:
			d.pop('id')
			d.pop(field.source_field.name + '_id')
			d['id'] = d.pop(field.target_field.name + '_id')
		# And sort them by (target) id. Sorting the dicts alphabetically would also be nice, but eh.
		return sorted(data, key=itemgetter('id'))



	def save(self, *args, **kwargs):
		# For any changed FK, flag reverse relations as dirty in the history layer
		# It is OK to do this before the super save() because the history commit will check for actual changes
		# This has to happen before the super save() because it needs to get the reverse FK values before the change.
		if self.Binder.history:
			for field_name, new_value in self.binder_concrete_fields_as_dict().items():
				old_value = self._history[field_name]
				if old_value != new_value:
					field = self._meta.get_field(field_name)
					if (not isinstance(field, models.fields.related.OneToOneField) and
					    isinstance(field, models.fields.related.ForeignKey) and
					    field.remote_field.name != '+'):
						history.change(field.remote_field.model, old_value, field.remote_field.name, history.DeferredM2M, history.DeferredM2M)
						history.change(field.remote_field.model, new_value, field.remote_field.name, history.DeferredM2M, history.DeferredM2M)

		super().save(*args, **kwargs)

		# Record changes to normal fields.
		# This has to happen after the super save() so unsuccessful save()s are aborted before the
		# changes are recorded by the history module.
		if self.Binder.history:
			for field_name, new_value in self.binder_concrete_fields_as_dict().items():
				old_value = self._history[field_name]
				if old_value != new_value:
					history.change(self.__class__, self.id, field_name, old_value, new_value)
					self._history[field_name] = new_value



	def delete(self, *args, **kwargs):
		if self.Binder.history:
			history.change(self.__class__, self.id, 'id', self.id, None)
			for field_name, old_value in self._history.items():
				field = self._meta.get_field(field_name)
				if isinstance(field, models.fields.related.ForeignKey) and field.remote_field.name != '+':
					history.change(field.remote_field.model, old_value, field.remote_field.name, history.DeferredM2M, history.DeferredM2M)

		super().delete(*args, **kwargs)



	class Binder:
		history = False



	class Meta:
		abstract = True
		ordering = ['id']



def history_m2m_change(sender, instance=None, action=None, reverse=None, pk_set=None, model=None, **kwargs):
	if action not in ('pre_add', 'pre_remove', 'pre_clear'):
		return

	# POV: model defining the m2m; signal history layer that this m2m will change
	if not reverse:
		# Find the corresponding field on the instance
		field = [f for f in instance._meta.get_fields() if f.concrete and f.many_to_many and f.remote_field.through == sender][0]

		history.change(instance.__class__, instance.id, field.name, history.DeferredM2M, history.DeferredM2M)
		return


	# reverse = True; POV: model NOT defining the m2m

	# Find the corresponding fields on the local and remote (defining) model
	field = [f for f in instance._meta.get_fields() if not f.concrete and f.many_to_many and f.through == sender][0]
	remote_field = [f for f in model._meta.get_fields() if f.concrete and f.many_to_many and f.remote_field.through == sender][0]

	# If clearing, find all the remote ids that need to be updated
	if action == 'pre_clear':
		pk_set = getattr(instance, field.name).values_list('id', flat=True)

	# Update the remote ids.
	for oid in pk_set:
		history.change(model, oid, remote_field.name, history.DeferredM2M, history.DeferredM2M)



def install_m2m_signal_handlers(model):
	if model is None:
		return

	if not model.Meta.abstract and model.Binder.history:
		for field in model._meta.get_fields():
			if field.many_to_many and field.concrete:
				signals.m2m_changed.connect(history_m2m_change, getattr(model, field.name).through)

	for sub in model.__subclasses__():
		install_m2m_signal_handlers(sub)
