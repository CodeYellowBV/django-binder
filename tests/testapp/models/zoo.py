import os
from django.db import models
from django.db.models.signals import post_delete

import binder.models
from binder.models import BinderModel

def delete_files(sender, instance=None, **kwargs):
	for field in sender._meta.fields:
		if isinstance(field, models.fields.files.FileField):
			try:
				file = getattr(instance, field.name).path
				os.unlink(file)
			except:
				pass

# From the api docs: a zoo with a name.  It also has a founding date,
# which is nullable (representing "unknown").
class Zoo(BinderModel):
	name = models.TextField()
	founding_date = models.DateField(null=True, blank=True)
	floor_plan = models.ImageField(upload_to='floor-plans', null=True, blank=True)

	def __str__(self):
		return 'zoo %d: %s' % (self.pk or 0, self.name)

post_delete.connect(delete_files, sender=Zoo)
