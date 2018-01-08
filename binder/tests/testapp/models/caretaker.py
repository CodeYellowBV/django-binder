from django.db import models
from binder.models import BinderModel

class Caretaker(BinderModel):
	name = models.TextField()
	last_seen = models.DateTimeField(null=True, blank=True)

	# We have the ssn for each caretaker. We have to make sure that nobody can access this ssn in anyway, since
	# this shouldn't be accessible
	ssn = models.TextField(default='my secret ssn')

	def __str__(self):
		return 'caretaker %d: %s' % (self.pk, self.name)

	class Binder:
		history = True
