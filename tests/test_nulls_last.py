import unittest
from datetime import datetime

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .testapp.models import Caretaker, Animal
import os

class NullsLastTest(TestCase):

	def setUp(self):
		super().setUp()

		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_order_by_nulls_last(self):
		self._load_test_data()

		# MySQL has different defaults when no nulls option is selected...
		if os.environ.get('BINDER_TEST_MYSQL', '0') != '0':
			self._assert_order('last_seen', ['4', '5', '1', '2', '3'])
			self._assert_order('-last_seen', ['3', '2', '1', '4', '5'])
		else:
			self._assert_order('last_seen', ['1', '2', '3', '4', '5'])
			self._assert_order('-last_seen', ['4', '5', '3', '2', '1'])

		self._assert_order('last_seen__nulls_last', ['1', '2', '3', '4', '5'])
		self._assert_order('-last_seen__nulls_last', ['3', '2', '1', '4', '5'])
		self._assert_order('last_seen__nulls_first', ['4', '5', '1', '2', '3'])
		self._assert_order('-last_seen__nulls_first', ['4', '5', '3', '2', '1'])

	@unittest.skipIf(
		'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (2, 1, 0),
		"Only available from DJango >2.1"
	)
	def test_order_by_nulls_last_on_annotation(self):
		self._load_test_data()

		# MySQL has different defaults when no nulls option is selected...
		if os.environ.get('BINDER_TEST_MYSQL', '0') != '0':
			self._assert_order('last_present', ['4', '5', '1', '2', '3'])
			self._assert_order('-last_present', ['3', '2', '1', '4', '5'])
		else:
			self._assert_order('last_present', ['1', '2', '3', '4', '5'])
			self._assert_order('-last_present', ['4', '5', '3', '2', '1'])

		self._assert_order('last_present__nulls_last', ['1', '2', '3', '4', '5'])
		self._assert_order('-last_present__nulls_last', ['3', '2', '1', '4', '5'])
		self._assert_order('last_present__nulls_first', ['4', '5', '1', '2', '3'])
		self._assert_order('-last_present__nulls_first', ['4', '5', '3', '2', '1'])

	@unittest.skipIf(
		'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (2, 1, 0),
		"Only available from DJango >2.1"
	)
	def test_order_by_nulls_last_on_aggregate_annotation(self):
		self._load_test_data_with_animals()

		self._assert_order('best_animal', ['1', '2', '3', '4', '5'])
		self._assert_order('-best_animal', ['5', '4', '3', '2', '1'])
		self._assert_order('best_animal__nulls_last', ['1', '2', '3', '4', '5'])
		self._assert_order('-best_animal__nulls_last', ['5', '4', '3', '2', '1'])
		self._assert_order('best_animal__nulls_first', ['1', '2', '3', '4', '5'])
		self._assert_order('-best_animal__nulls_first', ['5', '4', '3', '2', '1'])

	def _load_test_data(self):
		Caretaker.objects.all().delete()
		for name, last_seen in [
			('1', datetime(2018, 4, 10)),
			('2', datetime(2018, 5, 10)),
			('3', datetime(2018, 6, 10)),
			('4', None),
			('5', None),
		]:
			Caretaker(name=name, last_seen=last_seen).save()

	def _load_test_data_with_animals(self):
		self._load_test_data()
		Animal.objects.all().delete()
		for caretaker in Caretaker.objects.all():
			Animal(name=caretaker.name, caretaker=caretaker).save()

	def _assert_order(self, order_by, expected):
		res = self.client.get('/caretaker/', {'order_by': order_by})
		self.assertEqual(res.status_code, 200)
		data = jsonloads(res.content)['data']
		self.assertEqual([caretaker['name'] for caretaker in data], expected)
