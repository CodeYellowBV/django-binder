from django.db import models
from django.db.models.signals import post_save
from binder.models import BinderModel
from binder.websocket import trigger


# Some of our fictitious animals actually wear clothes/costumes...
# Each costume is unique to an animal (one to one mapping)
class Costume(BinderModel):
	nickname = models.TextField(blank=True)
	description = models.TextField(blank=True, null=True)
	animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='costume')

	def __str__(self):
		return 'costume %d: %s (for %s)' % (self.pk or 0, self.description, self.animal)

	def list_rooms(self):
		return [{
			'costume': self.id,
		}]


def trigger_websocket(instance, created, **kwargs):
	costume = instance
	trigger({'id': costume.id}, costume.list_rooms())


post_save.connect(trigger_websocket, sender=Costume)
