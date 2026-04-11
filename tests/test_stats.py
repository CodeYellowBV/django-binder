import json

from django.test import TestCase
from django.contrib.auth.models import User

from .testapp.models import Animal, Caretaker, Zoo

from .compare import assert_json, ANY


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

	def get_stats(self, *stats, status=200, params={}):
		res = self.client.get('/animal/stats/', {
			'stats': ','.join(stats),
			**params,
		})
		self.assertEqual(res.status_code, status)
		return json.loads(res.content)

	def test_animals_without_caretaker(self):
		res = self.get_stats('without_caretaker')
		self.assertEqual(res, {
			'without_caretaker': {
				'value': 1,
				'filters': {'caretaker:isnull': 'true'},
			},
		})

	def test_animals_by_zoo(self):
		res = self.get_stats('by_zoo')
		self.assertEqual(res, {
			'by_zoo': {
				'value': {'Zoo 1': 1, 'Zoo 2': 2},
				'other': 0,
				'filters': {},
				'group_by': 'zoo.name',
			},
		})

	def test_stats_filtered(self):
		res = self.get_stats(
			'total_records',
			'without_caretaker',
			'by_zoo',
			params={'.zoo.name': 'Zoo 1'},
		)
		self.assertEqual(res, {
			'total_records': {
				'value': 1,
				'filters': {},
			},
			'without_caretaker': {
				'value': 0,
				'filters': {'caretaker:isnull': 'true'},
			},
			'by_zoo': {
				'value': {'Zoo 1': 1},
				'other': 0,
				'filters': {},
				'group_by': 'zoo.name',
			},
		})

	def test_stat_not_found(self):
		res = self.get_stats('does_not_exist', status=418)
		assert_json(res, {
			'code': 'RequestError',
			'message': 'unknown stat: does_not_exist',
			'debug': ANY(),
		})

	# annotations
	def test_animals_annotation(self):
		res = self.get_stats('stat_total_magic_number')
		self.assertEqual(res, {
			'stat_total_magic_number': {
				'value': 6,
				'filters': {},
			},
		})

	def test_animals_annotation_duplicates(self):
		res = self.get_stats('stat_total_magic_number,stat_total_magic_number_times_hunderd')
		self.assertEqual(res, {
			'stat_total_magic_number': {
				'value': 6,
				'filters': {},
			},
			'stat_total_magic_number_times_hunderd': {
				'value': 600,
				'filters': {},
			}
		})
