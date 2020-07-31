from django.db import models
from django.db.models import Count, F, Max
from binder.models import BinderModel

class Caretaker(BinderModel):
	name = models.TextField()
	first_seen = models.DateTimeField(null=True, blank=True)
	last_seen = models.DateTimeField(null=True, blank=True)

	# We have the ssn for each caretaker. We have to make sure that nobody can access this ssn in anyway, since
	# this shouldn't be accessible
	ssn = models.TextField(default='my secret ssn')

	def __str__(self):
		return 'caretaker %d: %s' % (self.pk, self.name)

	class Binder:
		history = True

	class Annotations:
		best_animal = Max('animals__name')
		animal_count = Count('animals')
		bsn = F('ssn')  # simple alias
		last_present = F('last_seen')
