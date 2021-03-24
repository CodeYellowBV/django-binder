from django.db import models
from django.core.exceptions import ValidationError
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name = models.CharField(unique=True, max_length=50)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return 'contact_person %d: %s' % (self.pk, self.name)

	def clean(self):
		if self.name == 'very_special_forbidden_contact_person_name':
			raise ValidationError(
				code='invalid',
				message='Very special validation check that we need in `tests.M2MStoreErrorsTest`.'
			)
