from django.contrib.auth.models import User
from django.test import TestCase, Client

import json
from binder.json import jsonloads

from django.test import TestCase


class M2MStoreErrorsTest(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	# When a model can not be saved due to validation errors its corresponding m2m models should also not be saved
	# and correctly return a 400 validation error instead of a 500 error after still trying to save the m2m model
	def test_saving_m2m_models_return_correct_400(self):
		model_data = {"data": [
			{
				"id": -4,
				'name': '',
				'most_popular_animals': [],
				"contacts": [],
				'opening_time': 'invalid opening time`'
			}
		],
			"with": {}
		}
		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		print(response.body)
