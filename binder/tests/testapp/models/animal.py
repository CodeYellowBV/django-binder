from django.db import models
from binder.models import BinderModel
from binder.exceptions import BinderValidationError

# From the api docs: an animal with a name.  We don't use the
# CaseInsensitiveCharField because it's so much simpler to use
# memory-backed sqlite than Postgres in the tests.  Eventually we
# might switch and require Postgres for tests, if we need many
# Postgres-specific things.
class Animal(BinderModel):
	name = models.TextField(max_length=64)
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)
	caretaker = models.ForeignKey('Caretaker', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)
	deleted = models.BooleanField(default=False) # Softdelete

	def __str__(self):
		return 'animal %d: %s' % (self.pk or 0, self.name)

	def _binder_unset_relation_caretaker(self):
		raise BinderValidationError({'animal': {self.pk: {'caretaker': [{
			'code': 'cant_unset',
			'message': 'You can\'t unset zoo.',
		}]}}})

	class Binder:
		history = True
