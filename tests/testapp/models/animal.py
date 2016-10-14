from django.db import models

import binder.models
from binder.models import BinderModel

# From the api docs: an animal with a name.  We don't use the
# CaseInsensitiveCharField because it's so much simpler to use
# memory-backed sqlite than Postgres in the tests.  Eventually we
# might switch and require Postgres for tests, if we need many
# Postgres-specific things.
class Animal(BinderModel):
	name=models.TextField()
	zoo=models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)

	def __str__(self):
		return 'animal %d: %s' % (self.pk or 0, self.name)

	class Binder:
		history = True
