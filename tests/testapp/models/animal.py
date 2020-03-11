from django.db import models
from binder.models import BinderModel
from binder.exceptions import BinderValidationError
from binder.plugins.loaded_values import LoadedValuesMixin

# From the api docs: an animal with a name.
class Animal(LoadedValuesMixin, BinderModel):
	name = models.TextField(max_length=64)
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)
	zoo_of_birth = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='+', blank=True, null=True) # might've been born outside captivity
	caretaker = models.ForeignKey('Caretaker', on_delete=models.PROTECT, related_name='animals', blank=True, null=True)
	deleted = models.BooleanField(default=False)  # Softdelete

	def __str__(self):
		return 'animal %d: %s' % (self.pk, self.name)

	def _binder_unset_relation_caretaker(self, request):
		raise BinderValidationError({'animal': {self.pk: {'caretaker': [{
			'code': 'cant_unset',
			'message': 'You can\'t unset zoo.',
		}]}}})

	class Binder:
		history = True
