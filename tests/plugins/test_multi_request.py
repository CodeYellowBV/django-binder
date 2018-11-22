from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads, jsondumps

from ..testapp.models import Animal


class MultiRequestTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_create_and_update(self):
		requests = [
			{
				'method': 'POST',
				'path': '/zoo/',
				'body': {
					'name': 'Zoo',
				},
			},
			{
				'method': 'POST',
				'path': '/animal/',
				'body': {
					'name': 'Foo',
				},
				'transforms': [{
					'source': [0, 'body', 'id'],
					'target': ['body', 'zoo'],
				}],
			},
			{
				'method': 'PUT',
				'path': '/animal/{id}/',
				'body': {
					'name': 'Bar',
				},
				'transforms': [{
					'source': [1, 'body', 'id'],
					'target': ['path', 'id'],
				}],
			},
		]

		response = self.client.post(
			'/multi/',
			data=jsondumps(requests),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 200)

	def test_transaction(self):
		requests = [
			# This request should work fine
			{
				'method': 'POST',
				'path': '/animal/',
				'body': {
					'name': 'Foo',
				},
			},
			# This one should error
			{
				'method': 'POST',
				'path': '/animal/',
				'body': {
					'NONEXISTINGFIELD': 'Bar',
				},
			},
		]

		response = self.client.post(
			'/multi/',
			data=jsondumps(requests),
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 418)
		response = jsonloads(response.content)

		with self.assertRaises(Animal.DoesNotExist):
			Animal.objects.get(pk=response[0]['body']['id'])

	def test_invalid_method(self):
		response = self.client.put(
			'/multi/', data=b'[]',
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 405)
