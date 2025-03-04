from django.db import models
from binder.models import BinderModel
from binder.plugins.loaded_values import LoadedValuesMixin

# Zoos have to protect their employees' privacy
class ZooEmployee(LoadedValuesMixin, BinderModel):
	name = models.TextField(max_length=64)
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='zoo_employees')
	hourly_wage = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
	favorite_number = models.IntegerField(null=True, blank=True)
	deleted = models.BooleanField(default=False)  # Softdelete

	def __str__(self):
		return 'zoo employee %d: %s' % (self.pk, self.name)

	class Binder:
		history = True
