from django.db import models

import binder.models
from binder.models import BinderModel

class Caretaker(BinderModel):
	name=models.TextField()

	def __str__(self):
		return 'caretaker %d: %s' % (self.pk or 0, self.name)

	class Binder:
		history = True
