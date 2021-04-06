from django.contrib.auth.models import User
from django.test import TestCase, Client

import json
from binder.json import jsonloads

from django.test import TestCase

from .testapp.models import Animal, ContactPerson, Zoo


class M2MStoreErrorsTest(TestCase):
	"""
	(T30296) When model saving fails due to model validation errors (from `clean()` for example), related field
	saving should not crash.
	This involves:
	- m2m fields
	- reverse m2m fields
	- reverse o2o fields
	- reverse fk fields

	This test depends on some validation rule added to `ContactPerson` and `Zoo`.
	"""

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
	# validation error is caused by a field in this test
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

	def assert_validation_error_as_response(self, response):
		"""Assert that the backend sends us the validation error."""
		self.assertEqual(jsonloads(response.content)['code'], 'ValidationError')
		self.assertIn('Very special validation check that we need in `tests.M2MStoreErrorsTest`.', str(response.content))
		self.assertEqual(response.status_code, 400)

	def test_saving_m2m_with_model_validation_error(self):
		"""Forward m2m field saving should not crash when there are model validation errors."""
		model_data = {"data": [
			{
				'id': -4,
				'name': 'very_special_forbidden_zoo_name', # trigger model validation error
				'opening_time': '08:00',
				'contacts': [], # m2m field on Zoo
			}
		],
			"with": {}
		}

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assert_validation_error_as_response(response)

	def test_saving_reverse_m2m_with_model_validation_error(self):
		"""Reverse m2m field saving should not crash when there are model validation errors."""
		model_data = {"data": [
			{
				'id': -4,
				'name': 'very_special_forbidden_contact_person_name', # trigger model validation error
				'zoos': [], # this is the related_name, actual m2m field is on Zoo
			}
		],
			"with": {}
		}

		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assert_validation_error_as_response(response)

	def test_saving_reverse_fk_with_validation_error(self):
		"""Reverse foreign key field saving should not crash when there are model validation errors."""
		animal = Animal(name='Paard')
		animal.save()

		model_data = {"data": [
			{
				'id': -4,
				'name': 'very_special_forbidden_zoo_name', # trigger model validation error
				'animals': [animal.pk], # animals have a fk to zoo
			}
		],
			"with": {}
		}

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assert_validation_error_as_response(response)

	def test_saving_o2o_with_validation_error(self):
		"""Reverse o2o field saving should not crash when there are model validation errors."""
		zoo = Zoo(name='Awesome zoo')
		zoo.save()

		model_data = {"data": [
			{
				'id': -4,
				'name': 'very_special_forbidden_contact_person_name', # trigger model validation error
				'managing_zoo': zoo.pk,
			}
		],
			"with": {}
		}

		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assert_validation_error_as_response(response)
