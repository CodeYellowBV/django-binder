from datetime import timedelta

from django.contrib.auth.models import User
from django.test import Client, TestCase

from binder.json import jsonloads

from ..testapp.models import Truck


class DurationFiltersTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		self.assertTrue(self.client.login(username='testuser', password='test'))

		Truck(name='Slow', truck_loading_time=timedelta(hours=2)).save()
		Truck(name='Fast', truck_loading_time=timedelta(minutes=30)).save()

	def test_exact_match(self):
		response = self.client.get('/truck/', data={'.truck_loading_time': '00:30:00'})
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Fast', result['data'][0]['name'])

	def test_gte(self):
		response = self.client.get('/truck/', data={'.truck_loading_time:gte': '01:00:00', 'order_by': 'truck_loading_time'})
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Slow', result['data'][0]['name'])

	def test_range(self):
		response = self.client.get('/truck/', data={'.truck_loading_time:range': '00:20:00,01:00:00'})
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Fast', result['data'][0]['name'])

	def test_invalid_value(self):
		response = self.client.get('/truck/', data={'.truck_loading_time': 'banana'})
		self.assertEqual(response.status_code, 418)
		self.assertEqual('RequestError', jsonloads(response.content)['code'])
