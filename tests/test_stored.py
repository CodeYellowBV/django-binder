from contextlib import contextmanager
import json

from django.db import connection
from django.test import TestCase
from django.contrib.auth.models import User

from .testapp.models import Zoo, Animal


@contextmanager
def collect_queries():
	init_count = len(connection.queries)
	queries = []
	try:
		yield queries
	finally:
		queries[:] = connection.queries[init_count:]


class StoredTest(TestCase):

	def test_base(self):
		zoo = Zoo.objects.create(name='Zoo')

		zoo.refresh_from_db()
		self.assertEqual(zoo.stored_animal_count, 0)

		for n in range(1, 11):
			Animal.objects.create(zoo=zoo, name=f'Animal {n}')
			zoo.refresh_from_db()
			self.assertEqual(zoo.stored_animal_count, n)

	def test_id_switch(self):
		zoo1 = Zoo.objects.create(name='Zoo 1')
		zoo2 = Zoo.objects.create(name='Zoo 2')

		animals = [
			Animal.objects.create(
				zoo=zoo1 if n <= 4 else zoo2,
				name=f'Animal {n}',
			)
			for n in range(1, 7)
		]

		zoo1.refresh_from_db()
		self.assertEqual(zoo1.stored_animal_count, 4)
		zoo2.refresh_from_db()
		self.assertEqual(zoo2.stored_animal_count, 2)

		animals[3].zoo = zoo2
		animals[3].save()

		zoo1.refresh_from_db()
		self.assertEqual(zoo1.stored_animal_count, 3)
		zoo2.refresh_from_db()
		self.assertEqual(zoo2.stored_animal_count, 3)

	def test_only_update_when_needed(self):
		zoo = Zoo.objects.create(name='Zoo')
		animal = Animal.objects.create(zoo=zoo, name='Animal')

		animal.name = 'Other'
		with collect_queries() as queries:
			animal.save()
		self.assertEqual(len(queries), 1)

		zoo2 = Zoo.objects.create(name='Zoo 2')
		animal.zoo = zoo2
		with collect_queries() as queries:
			animal.save()
		self.assertGreater(len(queries), 1)

	def test_cannot_update_through_api(self):
		user = User(username='test', is_superuser=True)
		user.set_password('test')
		user.save()

		zoo = Zoo.objects.create(name='Zoo')

		zoo.refresh_from_db()
		self.assertEqual(zoo.stored_animal_count, 0)

		self.assertTrue(self.client.login(username='test', password='test'))
		res = self.client.put(
			f'/zoo/{zoo.pk}/',
			data={'stored_animal_count': 1337},
			content_type='application/json',
		)
		self.assertEqual(res.status_code, 200)
		res = json.loads(res.content)
		self.assertEqual(res['stored_animal_count'], 0)
		self.assertIn('stored_animal_count', res['_meta']['ignored_fields'])

		zoo.refresh_from_db()
		self.assertEqual(zoo.stored_animal_count, 0)
