from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User

from .testapp.models import Animal

class ModelViewBasicsTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)


	def test_post_new_model(self):
		model_data = {
			'name': 'Scooby Doo',
		}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')

		print(response.content)
		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertIsNotNone(returned_data.get('id'))
		self.assertEqual(returned_data.get('name'), 'Scooby Doo')


	def test_get_model_with_valid_id(self):
		daffy = Animal(name='Daffy Duck')
		daffy.full_clean()
		daffy.save()

		response = self.client.get('/animal/%d/' % (daffy.pk,))

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		data = result['data']
		self.assertEqual(data.get('id'), daffy.pk)
		self.assertEqual(data.get('name'), 'Daffy Duck')
