from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User

from .testapp.models import Animal, Zoo

class TestValidationErrors(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_validate_blank(self):
		model_data = {}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data['code'], 'ValidationError')
		self.assertEqual(len(returned_data['errors']), 1)
		self.assertEqual(len(returned_data['errors']['animal']), 1)
		obj_id = list(returned_data['errors']['animal'])[0]
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]), 1)
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]['name']), 1)
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['code'], 'blank')
		self.assertIn('message', returned_data['errors']['animal'][obj_id]['name'][0])
