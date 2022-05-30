import os
import datetime

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Count
from django.db.models.signals import post_delete

from binder.models import BinderModel, BinderImageField
from binder.stored import Stored
from binder.plugins.loaded_values import LoadedValuesMixin

def delete_files(sender, instance=None, **kwargs):
	for field in sender._meta.fields:
		if isinstance(field, models.fields.files.FileField):
			try:
				file = getattr(instance, field.name).path
				os.unlink(file)
			except (FileNotFoundError, ValueError):
				pass

# From the api docs: a zoo with a name.  It also has a founding date,
# which is nullable (representing "unknown").
class Zoo(LoadedValuesMixin, BinderModel):
	name = models.TextField()
	founding_date = models.DateField(null=True, blank=True)
	floor_plan = models.ImageField(upload_to='floor-plans', null=True, blank=True)
	# It is important that this m2m relationship is defined on this model, one of the tests depends on this fact
	contacts = models.ManyToManyField('ContactPerson', blank=True, related_name='zoos')
	# We assume that a person can only be the director of one zoo, one of the tests depends on this fact
	director = models.OneToOneField('ContactPerson', on_delete=models.SET_NULL, blank=True, null=True, related_name='managing_zoo')
	most_popular_animals = models.ManyToManyField('Animal', blank=True, related_name='+')
	opening_time = models.TimeField(default=datetime.time(9, 0, 0))

	django_picture = models.ImageField(upload_to='foo/bar/%Y/%m/%d/', blank=True, null=True)
	binder_picture = BinderImageField(upload_to='foo/bar/%Y/%m/%d/', blank=True, null=True)

	django_picture_not_null = models.ImageField(blank=True)
	binder_picture_not_null = BinderImageField(blank=True)

	binder_picture_custom_extensions = BinderImageField(allowed_extensions=['png'], blank=True, null=True)

	stored_animal_count = Stored(Count('animals'))

	def __str__(self):
		return 'zoo %d: %s' % (self.pk, self.name)

	@property
	def animal_count(self):
		return self.animals.count()


	def clean(self):
		if self.name == 'very_special_forbidden_zoo_name':
			raise ValidationError(
				code='invalid',
				message='Very special validation check that we need in `tests.M2MStoreErrorsTest`.'
			)

		errors = {}

		if self.floor_plan and self.name == 'Nowhere':
			errors['floor_plan'] = ValidationError('Nowhere may not have a floor plan!', code='no plan')
			errors['name'] = ValidationError('Nowhere may not have a floor plan!', code='nowhere')

		if errors:
			raise ValidationError(errors)


post_delete.connect(delete_files, sender=Zoo)
