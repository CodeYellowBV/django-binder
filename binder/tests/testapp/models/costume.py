from django.db import models
from binder.models import BinderModel
from binder.websocket import trigger
from django.db.models.signals import post_save


# Some of our fictitious animals actually wear clothes/costumes...
# Each costume is unique to an animal (one to one mapping)
class Costume(BinderModel):
	class Meta:
		ordering = ['animal_id']

	nickname = models.TextField(blank=True)
	description = models.TextField(blank=True, null=True)
	animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='costume', primary_key=True)

	def __str__(self):
		return 'costume %d: %s (for %s)' % (self.pk, self.description, self.animal)

	def list_rooms(self):
		return [{
			'costume': self.animal.id,
		}]


def trigger_websocket(instance, created, **kwargs):
	if created:
		costume = instance
		trigger({'id': costume.animal.id}, costume.list_rooms())

post_save.connect(trigger_websocket, sender=Costume)
