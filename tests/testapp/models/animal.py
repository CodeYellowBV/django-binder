from django.db import models
from django.db.models import Value, F, Func
from binder.models import BinderModel, ContextAnnotation
from binder.exceptions import BinderValidationError
from binder.plugins.loaded_values import LoadedValuesMixin


class Concat(Func):
	function = 'CONCAT'
	output_field = models.TextField()

# From the api docs: an animal with a name.
class Animal(LoadedValuesMixin, BinderModel):
	name = models.TextField(max_length=64)
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)
	zoo_of_birth = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='+', blank=True, null=True) # might've been born outside captivity
	caretaker = models.ForeignKey('Caretaker', on_delete=models.PROTECT, related_name='animals', blank=True, null=True)
	deleted = models.BooleanField(default=False)  # Softdelete
	birth_date = models.DateField(blank=True, null=True)

	def __str__(self):
		return 'animal %d: %s' % (self.pk, self.name)

	def _binder_unset_relation_caretaker(self, request):
		raise BinderValidationError({'animal': {self.pk: {'caretaker': [{
			'code': 'cant_unset',
			'message': 'You can\'t unset zoo.',
		}]}}})

	class Binder:
		history = True

	class Annotations:
		prefixed_name = ContextAnnotation(lambda request: Concat(
			Value(request.GET.get('animal_name_prefix', 'Sir') + ' '),
			F('name'),
		))
		magic_number = Value(2)
