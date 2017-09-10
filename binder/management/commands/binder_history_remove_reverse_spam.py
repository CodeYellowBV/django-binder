import logging
import json

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.apps import apps
from django.db import connection

from binder.history import Change



logger = logging.getLogger(__name__)



class Command(BaseCommand):
	help = 'Remove redundant FK/M2M binder history changes. See https://github.com/CodeYellowBV/django-binder/issues/76'

	def add_arguments(self, parser):
		parser.add_argument('app_name', type=str, metavar='<app name>', nargs=1, help='Django app to prune.')



	def handle(self, *args, **options):
		app_name = options['app_name'][0]
		app = apps.get_app_config(app_name)

		with transaction.atomic():
			print('Reverse FKs')
			for model in app.models.values():
				for field in model._meta.get_fields():
					if not isinstance(field, models.fields.reverse_related.ManyToOneRel):
						continue

					ct = Change.objects.filter(model=model.__name__, field=field.name).delete()[0]
					print('  cleaned {:>7} {}.{}'.format(ct, model.__name__, field.name))
			print()

			print('Reverse M2Ms')
			for model in app.models.values():
				for field in model._meta.get_fields():
					if not isinstance(field, models.fields.reverse_related.ManyToManyRel):
						continue

					ct = Change.objects.filter(model=model.__name__, field=field.name).delete()[0]
					print('  cleaned {:>7} {}.{}'.format(ct, model.__name__, field.name))
			print()

			print('Forward M2Ms')
			for model in app.models.values():
				for field in model._meta.get_fields():
					if not isinstance(field, models.fields.related.ManyToManyField):
						continue

					ct = 0
					for change in Change.objects.filter(model=model.__name__, field=field.name):
						ct += 1
						before = set(json.loads(change.before))
						after = set(json.loads(change.after))
						change.before = json.dumps(sorted(before - after))
						change.after = json.dumps(sorted(after - before))
						change.save()

					print('  cleaned {:>7} {}.{}'.format(ct, model.__name__, field.name))
			print()

		print('Running VACUUM FULL ANALYZE...')
		with connection.cursor() as cursor:
			cursor.execute('VACUUM FULL ANALYZE binder_change;')
