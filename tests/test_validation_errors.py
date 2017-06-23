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
		for model, model_errors in returned_data['errors'].items():
			self.assertEqual(model, 'animal')
			for obj_id, obj_errors in model_errors.items():
				for field, field_errors in obj_errors.items():
					self.assertEqual(field, 'name')
					for error in field_errors:
						self.assertIn('code', error)
						self.assertIn('message', error)
						self.assertEqual('code', 'blank')
