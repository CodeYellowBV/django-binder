from django.db import models
from binder.models import BinderModel

class ZooEmployee(BinderModel):
	name = models.TextField(max_length=64)
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='zoo_employees')
	deleted = models.BooleanField(default=False)  # Softdelete

	def __str__(self):
		return 'zoo employee %d: %s' % (self.pk, self.name)

	class Binder:
		history = True
