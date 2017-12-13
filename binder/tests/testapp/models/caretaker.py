from django.db import models
from binder.models import BinderModel

class Caretaker(BinderModel):
	name = models.TextField()
	last_seen = models.DateTimeField(null=True, blank=True)

	def __str__(self):
		return 'caretaker %d: %s' % (self.pk, self.name)

	class Binder:
		history = True
