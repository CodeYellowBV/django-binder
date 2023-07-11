from django.apps import AppConfig

from .signal import apps_ready


class StoredAppConfig(AppConfig):

	name = 'binder.stored'

	def ready(self):
		apps_ready.send(sender=None)
