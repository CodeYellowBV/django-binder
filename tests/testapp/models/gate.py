from django.db import models

import binder.models
from binder.models import BinderModel

class Gate(BinderModel):
	class Meta:
		ordering = ['zoo_id']

	zoo=models.OneToOneField('Zoo', on_delete=models.CASCADE, primary_key=True, related_name='gate')
	keeper=models.ForeignKey('Caretaker', on_delete=models.CASCADE, related_name='gate', blank=True, null=True)

	def __str__(self):
		return 'gate %d: of %s)' % (self.pk or 0, self.zoo)
