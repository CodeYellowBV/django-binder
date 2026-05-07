from django.db import models
from django.core.exceptions import ValidationError
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name = models.CharField(primary_key=True, max_length=50)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	@classmethod
	def format_instance_for_history(cls, pk: str):
		try:
			return ContactPerson.objects.get(pk=pk).name
		except:
			return 'deleted? ' + str(pk)

	def __str__(self):
		return 'contact_person %d: %s' % (self.pk, self.name)

	def clean(self):
		if self.name == 'very_special_forbidden_contact_person_name':
			raise ValidationError(
				code='invalid',
				message='Very special validation check that we need in `tests.M2MStoreErrorsTest`.'
			)
