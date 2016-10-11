from django.db import models

import binder.models
from binder.models import BinderModel

# From the api docs: a zoo with a name.
class Zoo(BinderModel):
	name=models.TextField()

	def __str__(self):
		return 'zoo %d: %s' % (self.pk or 0, self.name)
