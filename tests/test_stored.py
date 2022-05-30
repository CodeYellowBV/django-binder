from django.test import TestCase

from .testapp.models import Zoo, Animal


class StoredTest(TestCase):

	def test_deps(self):
		zoo = Zoo.objects.create(name='Zoo')

		zoo.refresh_from_db()
		self.assertEqual(zoo.stored_animal_count, 0)

		for n in range(1, 11):
			Animal.objects.create(zoo=zoo, name=f'Animal {n}')
			zoo.refresh_from_db()
			self.assertEqual(zoo.stored_animal_count, n)
