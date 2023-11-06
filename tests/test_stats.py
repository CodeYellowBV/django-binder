import json

from django.test import TestCase
from django.contrib.auth.models import User

from .testapp.models import Animal, Caretaker, Zoo


class StatsTest(TestCase):

	def setUp(self):
		zoo_1 = Zoo.objects.create(name='Zoo 1')
		zoo_2 = Zoo.objects.create(name='Zoo 2')

		caretaker = Caretaker.objects.create(name='Caretaker')

		Animal.objects.create(name='Animal 1', zoo=zoo_1, caretaker=caretaker)
		Animal.objects.create(name='Animal 2', zoo=zoo_2, caretaker=caretaker)
		Animal.objects.create(name='Animal 3', zoo=zoo_2, caretaker=None)

		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()

		self.assertTrue(self.client.login(username='testuser', password='test'))

	def get_stats(self, params={}, **stats):
		res = self.client.get('/animal/stats/', {
			'stats': json.dumps(stats),
			**params,
		})
		if res.status_code != 200:
			print(res.content.decode())
		self.assertEqual(res.status_code, 200)
		return json.loads(res.content)

	def test_animals_without_caretaker(self):
		res = self.get_stats(
			animals_without_caretaker={
				'filters': {'caretaker:isnull': 'true'},
			},
		)
		self.assertEqual(res, {
			'animals_without_caretaker': 1,
		})

	def test_animals_by_zoo(self):
		res = self.get_stats(
			animals_by_zoo={
				'group_by': 'zoo.name',
			},
		)
		self.assertEqual(res, {
			'animals_by_zoo': {
				'Zoo 1': 1,
				'Zoo 2': 2,
			},
		})

	def test_stats_filtered(self):
		res = self.get_stats(
			total={},
			animals_without_caretaker={
				'filters': {'caretaker:isnull': 'true'},
			},
			animals_by_zoo={
				'group_by': 'zoo.name',
			},
			params={'.zoo.name': 'Zoo 1'},
		)
		self.assertEqual(res, {
			'total': 1,
			'animals_without_caretaker': 0,
			'animals_by_zoo': {'Zoo 1': 1},
		})
