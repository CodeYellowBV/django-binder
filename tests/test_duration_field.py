import json

from django.contrib.auth.models import User
from django.test import Client, TestCase

from binder.json import jsonloads

from .testapp.models import Truck


class DurationFieldTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		self.assertTrue(self.client.login(username='testuser', password='test'))

	def _post(self, data):
		return self.client.post('/truck/', data=json.dumps(data), content_type='application/json')

	def test_post_uses_default(self):
		response = self._post({'name': 'Truck 1'})
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual('00:30:00', result['truck_loading_time'])
		self.assertIsNone(result['maintenance_time'])

	def test_post_get_roundtrip(self):
		response = self._post({
			'name': 'Truck 2',
			'truck_loading_time': '01:30:00',
			'maintenance_time': '2 03:04:05',
		})
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual('01:30:00', result['truck_loading_time'])
		self.assertEqual('2 03:04:05', result['maintenance_time'])
		truck_id = result['id']

		# GET again to prove the stored value round-trips
		# NOTE: detail GET responses nest the object under 'data'
		response = self.client.get('/truck/{}/'.format(truck_id))
		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)['data']
		self.assertEqual('01:30:00', result['truck_loading_time'])
		self.assertEqual('2 03:04:05', result['maintenance_time'])

	def test_put_updates_duration_and_accepts_iso8601(self):
		truck_id = jsonloads(self._post({'name': 'Truck 3'}).content)['id']
		response = self.client.put('/truck/{}/'.format(truck_id),
			data=json.dumps({'truck_loading_time': 'PT2H'}), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual('02:00:00', jsonloads(response.content)['truck_loading_time'])

	def test_put_null_on_nullable_field(self):
		truck_id = jsonloads(self._post({'name': 'Truck 4', 'maintenance_time': '01:00:00'}).content)['id']
		response = self.client.put('/truck/{}/'.format(truck_id),
			data=json.dumps({'maintenance_time': None}), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		self.assertIsNone(jsonloads(response.content)['maintenance_time'])

	def test_post_invalid_string_returns_validation_error(self):
		response = self._post({'name': 'Truck 5', 'truck_loading_time': 'banana'})
		self.assertEqual(response.status_code, 400)
		self.assertEqual('ValidationError', jsonloads(response.content)['code'])

	def test_post_non_string_returns_type_error(self):
		response = self._post({'name': 'Truck 6', 'truck_loading_time': 1800})
		self.assertEqual(response.status_code, 418)
		self.assertEqual('RequestError', jsonloads(response.content)['code'])

	def test_put_null_on_non_nullable_field_returns_validation_error(self):
		truck_id = jsonloads(self._post({'name': 'Truck 7'}).content)['id']
		response = self.client.put('/truck/{}/'.format(truck_id),
			data=json.dumps({'truck_loading_time': None}), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		self.assertEqual('ValidationError', jsonloads(response.content)['code'])
