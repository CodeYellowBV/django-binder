from contextlib import contextmanager

from django.test import TestCase
from django.db import connection

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
