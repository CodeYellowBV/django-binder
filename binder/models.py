import re
import warnings
import hashlib
import mimetypes
from datetime import date, datetime, time
from contextlib import suppress

from django.db import models
from django.db.models.fields.reverse_related import ForeignObjectRel
from django.db.models.fields.files import FieldFile, FileDescriptor, FileField
from django.contrib.postgres.fields import CITextField, ArrayField, JSONField
from django.db.models import signals, F
from django.core.files.base import File
from django.core.exceptions import ValidationError
from django.db.models.query_utils import Q
from django.db.models.expressions import BaseExpression
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from binder.json import jsonloads

from binder.exceptions import BinderRequestError

from . import history


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

	def __call__(self, **kwargs):
		return models.CharField(
			choices=self.choices(),
			max_length=max(map(len, self.items.values())),
			**kwargs
		)



class FieldFilter(object):
	# The classes that this filter applies to (should be mutually
	# exclusive with the other classes)
	fields = []
	# The list of allowed qualifiers
	allowed_qualifiers = []

	def __init__(self, field):
		self.field = field



	def field_description(self):
		return '{} {{{}}}.{{{}}}'.format(self.field.__class__.__name__, self.field.model.__name__, self.field.name)



	def clean_value(self, qualifier, v):
		raise ValueError('FieldFilter {} has not overridden the clean_value method'.format(self.__class__.name))



	def check_qualifier(self, qualifier):
		if qualifier not in self.allowed_qualifiers:
			raise BinderRequestError('Qualifier {} not supported for type {} ({}).'
					.format(qualifier, self.__class__.__name__, self.field_description()))



	def get_q(self, qualifier, value, invert, partial=''):
		self.check_qualifier(qualifier)

		# TODO: Try to make the splitting and cleaning more re-usable
		if qualifier in ('in', 'range'):
			values = value.split(',')
			if qualifier == 'range':
				if len(values) != 2:
					raise BinderRequestError('Range requires exactly 2 values for {}.'.format(self.field_description()))
		else:
			values = [value]


		if qualifier == 'isnull':
			cleaned_value = True
		elif qualifier in ('in', 'range'):
			cleaned_value = [self.clean_value(qualifier, v) for v in values]
		else:
			try:
				cleaned_value = self.clean_value(qualifier, values[0])
			except IndexError:
				raise ValidationError('Value for filter {{{}}}.{{{}}} may not be empty.'.format(self.field.model.__name__, self.field.name))

		suffix = '__' + qualifier if qualifier else ''
		if invert:
			return ~Q(**{partial + self.field.name + suffix: cleaned_value})
		else:
			return Q(**{partial + self.field.name + suffix: cleaned_value})



class IntegerFieldFilter(FieldFilter):
	fields = [
		models.IntegerField,
		models.ForeignKey,
		models.AutoField,
		models.ManyToOneRel,
		models.ManyToManyField,
		models.ManyToManyRel,
	]
	allowed_qualifiers = [None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull']

	def clean_value(self, qualifier, v):
		try:
			return int(v)
		except ValueError:
			raise ValidationError('Invalid value {{{}}} for {}.'.format(v, self.field_description()))



class FloatFieldFilter(FieldFilter):
	fields = [models.FloatField]
	allowed_qualifiers = [None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull']

	def clean_value(self, qualifier, v):
		try:
			return float(v)
		except ValueError:
			raise ValidationError('Invalid value {{{}}} for {}.'.format(v, self.field_description()))



class DateFieldFilter(FieldFilter):
	fields = [models.DateField]
	# Maybe allow __startswith? And __year etc?
	allowed_qualifiers = [None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull']

	def clean_value(self, qualifier, v):
		if not re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', v):
			raise ValidationError('Invalid YYYY-MM-DD value {{{}}} for {}.'.format(v, self.field_description()))
		else:
			return parse_date(v)
		return v



class DateTimeFieldFilter(FieldFilter):
	fields = [models.DateTimeField]
	# Maybe allow __startswith? And __year etc?
	allowed_qualifiers = [None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull']

	def clean_value(self, qualifier, v):
		if re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}[T ][0-9]{2}:[0-9]{2}:[0-9]{2}([.][0-9]+)?([A-Za-z]+|[+-][0-9]{1,4})$', v):
			return parse_datetime(v)
		if re.match('^[0-9]{4}-[0-9]{2}-[0-9]{2}$', v):
			return parse_date(v)
		else:
			raise ValidationError('Invalid YYYY-MM-DD(.mmm)ZONE value {{{}}} for {}.'.format(v, self.field_description()))
		return v


	def get_q(self, qualifier, value, invert, partial=''):
		self.check_qualifier(qualifier)

		# TODO: Try to make the splitting and cleaning more re-usable
		if qualifier in ('in', 'range'):
			values = value.split(',')
			if qualifier == 'range':
				if len(values) != 2:
					raise BinderRequestError('Range requires exactly 2 values for {}.'.format(self.field_description()))
		else:
			values = [value]


		if qualifier == 'isnull':
			cleaned_value = True
		elif qualifier in ('in', 'range'):
			cleaned_value = [self.clean_value(qualifier, v) for v in values]
			types = {type(v) for v in cleaned_value}
			if len(types) != 1:
				raise ValidationError('Values for filter {{{}}}.{{{}}} must be the same types.'.format(self.field.model.__name__, self.field.name))
			if isinstance(cleaned_value[0], date) and not isinstance(cleaned_value[0], datetime):
				qualifier = 'date__' + qualifier
		else:
			try:
				cleaned_value = self.clean_value(qualifier, values[0])
				if isinstance(cleaned_value, date) and not isinstance(cleaned_value, datetime):
					qualifier = 'date__' + qualifier if qualifier else 'date'
			except IndexError:
				raise ValidationError('Value for filter {{{}}}.{{{}}} may not be empty.'.format(self.field.model.__name__, self.field.name))

		suffix = '__' + qualifier if qualifier else ''
		if invert:
			return ~Q(**{partial + self.field.name + suffix: cleaned_value})
		else:
			return Q(**{partial + self.field.name + suffix: cleaned_value})



class TimeFieldFilter(FieldFilter):
	fields = [models.TimeField]
	# Maybe allow __startswith? And __year etc?
	allowed_qualifiers = [None, 'in', 'gt', 'gte', 'lt', 'lte', 'range', 'isnull']
	time_re = re.compile(r'^(\d{2}):(\d{2}):(\d{2})(?:\.(\d+))?(Z|[+-]\d{2}(?:\d{2})?)$')

	def clean_value(self, qualifier, v):
		# Match value
		match = self.time_re.match(v)
		if not match:
			raise ValidationError('Invalid HH:MM:SS(.mmm) value {{{}}} for {}.'.format(v, self.field_description()))
		# Get values
		hour, minute, second, microsecond, tzinfo = match.groups()
		hour = int(hour)
		minute = int(minute)
		second = int(second)
		microsecond = int((microsecond or '').ljust(6, '0'))
		if tzinfo == 'Z':
			tzinfo = timezone.utc
		else:
			tzinfo = tzinfo.ljust(5, '0')
			offset = int(tzinfo[1:3]) * 60 + int(tzinfo[3:5])
			if tzinfo.startswith('-'):
				offset = -offset
			tzinfo = timezone.get_fixed_timezone(offset)
		# Create time object
		return time(
			hour=hour,
			minute=minute,
			second=second,
			microsecond=microsecond,
			tzinfo=tzinfo,
		)



class BooleanFieldFilter(FieldFilter):
	fields = [models.BooleanField]
	allowed_qualifiers = [None]

	def clean_value(self, qualifier, v):
		if v == 'true':
			return True
		elif v == 'false':
			return False
		else:
			raise ValidationError('Invalid value {{{}}} for {}.'.format(v, self.field_description()))



class TextFieldFilter(FieldFilter):
	fields = [models.CharField, models.TextField]
	allowed_qualifiers = [None, 'in', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'exact', 'isnull']

	# Always valid(?)
	def clean_value(self, qualifier, v):
		return v


class UUIDFieldFilter(FieldFilter):
	fields = [models.UUIDField]
	allowed_qualifiers = [None, 'in', 'iexact', 'contains', 'icontains', 'startswith', 'istartswith', 'endswith', 'iendswith', 'exact']

	# Always valid; when using "contains" this doesn't need to be
	# an actually formatted uuid.
	def clean_value(self, qualifier, v):
		return v


class ArrayFieldFilter(FieldFilter):
	fields = [ArrayField]
	allowed_qualifiers = [None, 'contains', 'contained_by', 'overlap', 'isnull']

	# Some copy/pasta involved....
	def get_field_filter(self, field_class, reset=False):
		f = not reset and getattr(self, '_field_filter', None)

		if not f:
			f = None
			for field_filter_cls in FieldFilter.__subclasses__():
				for field_cls in field_filter_cls.fields:
					if field_cls == field_class:
						f = field_filter_cls
						break
			self._field_filter = f

		return f


	def clean_value(self, qualifier, v):
		Filter = self.get_field_filter(self.field.base_field.__class__)
		filter = Filter(self.field.base_field)
		if v == '': # Special case: This should represent the empty array, not an array with one empty string
			return []
		else:
			values = v.split(',')
			return map(lambda v: filter.clean_value(qualifier, v), values)


class JSONFieldFilter(FieldFilter):
	fields = [JSONField]
	# TODO: Element or path-based lookup is not supported yet
	allowed_qualifiers = [None, 'contains', 'contained_by', 'has_key', 'has_any_keys', 'has_keys', 'isnull']

	def clean_value(self, qualifier, v):
		if qualifier == 'has_key':
			return v
		elif qualifier in ('has_keys', 'has_any_keys'):
			if v == '':
				return []
			else:
				return v.split(',')
		else:
			# Use bytes to allow decode() to work.  We don't just
			# json.loads because we want to behave identically to
			# any other Binder JSON decode when there are errors.
			return jsonloads(bytes(v, 'utf-8'))



class BinderModelBase(models.base.ModelBase):
	def __new__(cls, name, bases, attrs):
		# Verify that any Foo(BinderModel).Meta descends from BinderModel.Meta. Django messes
		# around with Meta a lot in its metaclass, to the point where we can no longer check this.
		# So we have to inject our own metaclass.__new__ to find this. See #96
		# Bonus points: this way we throw all these warnings at startup.

		# NameError: happens when name='BinderModel' -> ignore
		# KeyError:  happens when Foo doesn't declare Meta -> ignore
		with suppress(NameError, KeyError):
			if not issubclass(attrs['Meta'], BinderModel.Meta):
				warnings.warn(RuntimeWarning('{}.{}.Meta does not descend from BinderModel.Meta'.format(attrs.get('__module__'), name)))
		return super().__new__(cls, name, bases, attrs)



class BinderModel(models.Model, metaclass=BinderModelBase):
	def binder_concrete_fields_as_dict(self, skip_deferred_fields=False):
		fields = {}
		deferred_fields = self.get_deferred_fields()

		for field in [f for f in self._meta.get_fields() if f.concrete and not f.many_to_many]:
			if skip_deferred_fields and field.attname in deferred_fields:
				continue
			elif isinstance(field, models.ForeignKey):
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
		ordering = ['pk']

	@classmethod
	def annotations(cls):
		ann_name = '_{}__annotations'.format(cls.__name__)
		if not hasattr(cls, ann_name):
			setattr(cls, ann_name, {})
			if hasattr(cls, 'Annotations'):
				for attr in dir(cls.Annotations):
					# Check for reserved python internal attribute
					if attr.startswith('__') and attr.endswith('__'):
						continue

					expr = getattr(cls.Annotations, attr)
					fix_output_field(expr, cls)

					if callable(expr) and not isinstance(expr, F) and not isinstance(expr, BaseExpression):
						expr = expr()

					if isinstance(expr, F):
						field = expr._output_field_or_none
					elif isinstance(expr, BaseExpression):
						field = expr.field.clone()
						field.name = attr
						field.model = cls
					else:
						warnings.warn(
							'{}.Annotations.{} was ignored because it is not '
							'a valid django query expression.'.format(cls.__name__, attr)
						)
						continue

					getattr(cls, ann_name)[attr] = {'field': field, 'expr': expr}
		return getattr(cls, ann_name)


def history_obj_post_init(sender, instance, **kwargs):
	instance._history = instance.binder_concrete_fields_as_dict(skip_deferred_fields=True)

	if not instance.pk:
		instance._history = {k: history.NewInstanceField for k in instance._history}



def history_obj_post_save(sender, instance, **kwargs):
	for field_name, new_value in instance.binder_concrete_fields_as_dict().items():
		try:
			old_value = instance._history[field_name]
			if old_value != new_value:
				history.change(sender, instance.pk, field_name, old_value, new_value)
				instance._history[field_name] = new_value
		except KeyError:
			# Unfetched field (using only(...)), we don't know if it's
			# been changed...
			pass



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
		install_history_signal_handlers(sub)


def serialize_tuple(values):
	return ','.join(re.sub(r'([,\\])', r'\\\1', value) for value in values)


def parse_tuple(content):
	values = []

	chars = iter(content)
	value = ''
	for char in content:
		if char == ',':
			values.append(value)
			value = ''
			continue
		if char == '\\':
			char = next(chars)
		value += char
	values.append(value)

	return values


class BinderFieldFile(FieldFile):
	"""
	An extended FieldFile that also stores the content hash and content type
	"""

	def __init__(self, instance, field, name, content_hash, content_type):
		super().__init__(instance, field, name)
		self._content_hash = content_hash
		self._content_type = content_type

	@property
	def content_hash(self):
		if self.name is None:
			self._content_hash = None
		elif self._content_hash is None:
			hasher = hashlib.sha1()
			with self.open('rb') as fh:
				while True:
					chunk = fh.read(4096)
					if not chunk:
						break
					hasher.update(chunk)
			self._content_hash = hasher.hexdigest()
		return self._content_hash

	@property
	def content_type(self):
		if self.name is None:
			self._content_type is None
		elif self._content_type is None:
			self._content_type, _ = mimetypes.guess_type(self.path)
		return self._content_type

	# So here we have a bunch of methods that might alter the data or name of
	# the associated file, in this case we just set the content type and hash
	# to None so that they will get calculated when accessed
	def open(self, mode='rb'):
		# These chars allow for modification on the file, in this case we
		# assume the content hash is not valid anymore
		if any(char in mode for char in 'wxa+'):
			self._content_hash = None
		return super().open(mode)

	def save(self, *args, **kwargs):
		# So in this case both the name and the content can change so we
		# reset everything
		self._content_hash = None
		self._content_type = None
		return super().save(*args, **kwargs)


class BinderFileDescriptor:
	# This class is largely copy pasted from django since it is sadly not very
	# extensible

	def __init__(self, field):
		self.field = field

	def __get__(self, instance, cls=None):
		if instance is None:
			return self

		# This is slightly complicated, so worth an explanation.
		# instance.file`needs to ultimately return some instance of `File`,
		# probably a subclass. Additionally, this returned object needs to have
		# the FieldFile API so that users can easily do things like
		# instance.file.path and have that delegated to the file storage engine.
		# Easy enough if we're strict about assignment in __set__, but if you
		# peek below you can see that we're not. So depending on the current
		# value of the field we have to dynamically construct some sort of
		# "thing" to return.

		# The instance dict contains whatever was originally assigned
		# in __set__.
		if self.field.name in instance.__dict__:
			file = instance.__dict__[self.field.name]
		else:
			instance.refresh_from_db(fields=[self.field.name])
			file = getattr(instance, self.field.name)

		# If this value is a string (instance.file = "path/to/file") or None
		# then we simply wrap it with the appropriate attribute class according
		# to the file field. [This is FieldFile for FileFields and
		# ImageFieldFile for ImageFields; it's also conceivable that user
		# subclasses might also want to subclass the attribute class]. This
		# object understands how to convert a path to a file, and also how to
		# handle None.
		if isinstance(file, str) or file is None:
			if file is not None:
				file, content_hash, content_type = parse_tuple(file)
			else:
				content_hash = None
				content_type = None
			attr = self.field.attr_class(
				instance, self.field, file, content_hash, content_type,
			)
			instance.__dict__[self.field.attname] = attr

		# Other types of files may be assigned as well, but they need to have
		# the FieldFile interface added to them. Thus, we wrap any other type of
		# File inside a FieldFile (well, the field's attr_class, which is
		# usually FieldFile).
		elif isinstance(file, File) and not isinstance(file, BinderFieldFile):
			# If we do not provide a content type/hash it will be calculated
			file_copy = self.field.attr_class(
				instance, self.field, file.name, None, None,
			)
			file_copy.file = file
			file_copy._committed = False
			instance.__dict__[self.field.attname] = file_copy

		# Finally, because of the (some would say boneheaded) way pickle works,
		# the underlying FieldFile might not actually itself have an associated
		# file. So we need to reset the details of the FieldFile in those cases.
		elif isinstance(file, BinderFieldFile) and not hasattr(file, 'field'):
			file.instance = instance
			file.field = self.field
			file.storage = self.field.storage

		# Make sure that the instance is correct.
		elif isinstance(file, BinderFieldFile) and instance is not file.instance:
			file.instance = instance

		# That was fun, wasn't it?
		return instance.__dict__[self.field.attname]

	def __set__(self, instance, value):
		instance.__dict__[self.field.name] = value


class BinderFileField(FileField):

	attr_class = BinderFieldFile
	descriptor_class = BinderFileDescriptor

	def __init__(self, *args, **kwargs):
		# Since we also need to store a content type and a hash in the field
		# we up the default max_length from 100 to 200
		kwargs.setdefault('max_length', 200)
		return super().__init__(*args, **kwargs)

	def get_prep_value(self, value):
		if value is None:
			return None

		return serialize_tuple((
			value.name,
			value.content_hash,
			value.content_type,
		))

	def deconstruct(self):
		name, path, args, kwargs = super().deconstruct()
		# Standard file field omits max length when it is 100 so we readd that
		# as the default and then omit if it is 200, which is our default
		if kwargs.setdefault('max_length', 100) == 200:
			del kwargs['max_length']
		return name, path, args, kwargs
