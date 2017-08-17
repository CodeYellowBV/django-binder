from django.db import models

import binder.models
from binder.models import BinderModel

# Some of our fictitious animals actually wear clothes/costumes...
# Each costume is unique to an animal (one to one mapping)
class Costume(BinderModel):
	class Meta:
		ordering = ['animal_id']
		
	nickname = models.TextField(blank=True)
	description = models.TextField(blank=True, null=True)
	animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='costume', primary_key=True)

	def __str__(self):
		return 'costume %d: %s (for %s)' % (self.pk or 0, self.description, self.animal)
