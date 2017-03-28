from django.db import models

import binder.models
from binder.models import BinderModel

# From the api docs: a zoo with a name.  It also has a founding date,
# which is nullable (representing "unknown").
class Zoo(BinderModel):
	name=models.TextField()
	founding_date=models.DateField(null=True, blank=True)

	def __str__(self):
		return 'zoo %d: %s' % (self.pk or 0, self.name)
