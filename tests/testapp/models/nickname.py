from django.db import models
from binder.models import BinderModel

# Some animals may have a nickname
class Nickname(BinderModel):
	class Meta(BinderModel.Meta):
		ordering = ['animal_id']

	nickname = models.TextField(blank=True)
	animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='nickname')

	def __str__(self):
		return '%s is sometimes referred to as %s' % (self.animal, self.nickname)

class NullableNickname(BinderModel):
	class Meta(BinderModel.Meta):
		ordering = ['animal_id']

	nickname = models.TextField(blank=True)
	animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='optional_nickname', null=True)

	def __str__(self):
		return '%s is sometimes referred to as %s' % (self.animal, self.nickname)
