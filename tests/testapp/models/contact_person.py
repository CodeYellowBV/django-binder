from django.db import models
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name = models.CharField(unique=True, max_length=50)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	def __str__(self):
		return 'contact_person %d: %s' % (self.pk, self.name)
