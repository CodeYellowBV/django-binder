from django.db import models
from django.core.exceptions import ValidationError
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name = models.CharField(primary_key=True, max_length=50)
	nick_name = models.TextField(blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
	first_zoo = models.ForeignKey('Zoo', on_delete=models.SET_NULL, blank=True, null=True, related_name='originals')
	successor = models.ForeignKey('ContactPerson', on_delete=models.SET_NULL, blank=True, null=True, related_name='succeeds')

	pk_regex = '.*'

	@classmethod
	def format_instance_for_history(cls, pk):
		if isinstance(pk, str):
			return pk.upper()
		else:
			return pk

	def __str__(self):
		return 'contact_person %s' % (self.pk)

	def clean(self):
		if self.name == 'very_special_forbidden_contact_person_name':
			raise ValidationError(
				code='invalid',
				message='Very special validation check that we need in `tests.M2MStoreErrorsTest`.'
			)

	class Binder:
		history = True
