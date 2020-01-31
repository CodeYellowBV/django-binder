from datetime import datetime, timedelta, date
from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, Client, override_settings
from binder.plugins.token_auth.models import Token

import json

from django.contrib.auth.tokens import default_token_generator
from django.utils.http import base36_to_int, int_to_base36
from binder.json import JsonResponse, jsonloads
from tests.testapp.models import ContactPerson, Zoo, Animal


@patch(
	'binder.plugins.views.UserViewMixIn._reset_pass_for_user',
	side_effect=lambda *args: JsonResponse({}),
)
class UserPasswordResetTestCase(TestCase):

	def setUp(self):
		self.user = User.objects.create_user(username='foo', password='bar')
		self.user.save()
		self.token = default_token_generator.make_token(self.user)

	def test_reset_call(self, reset_mock):
		client = Client()
		res = client.put('/user/{}/reset_password/'.format(self.user.pk), json.dumps({
			'reset_code': self.token,
			'password': 'foobar',
		}))

		self.assertEqual(200, res.status_code)

		reset_mock.assert_called_once_with(res.wsgi_request, self.user.pk, self.token, 'foobar')


class UserLogic(TestCase):

	def setUp(self):
		super().setUp()
		self.user = User.objects.create_user(username='foo', password='bar', is_active=True, is_superuser=True)
		self.user.save()
		self.user2 = User.objects.create_user(id=7, username='test', password='user', is_active=False)
		self.user2.save()
		self.token = default_token_generator.make_token(self.user2)

	def test_user_login(self):
		self.client = Client()
		r = self.client.login(username='foo', password='bar')
		self.assertTrue(r)

	def test_user_login_wrong_password(self):
		self.client = Client()
		r = self.client.login(username='foo', password='wrong_pass')
		self.assertFalse(r)

	def test_user_activation(self):
		self.client = Client()

		data = {
			"activation_code": (str(self.token))
		}

		r = self.client.put('/user/7/activate/', data=json.dumps(data),
							content_type='application/json')
		result = jsonloads(r.content)
		print(result)

		self.assertEqual(200, r.status_code)


class UserFilterParseTest(TestCase):

	def setUp(self):
		super().setUp()
		self.user = User.objects.create_user(username='foo', password='bar', is_active=True, is_superuser=True)
		self.user.save()
		self.token = default_token_generator.make_token(self.user)
		self.client = Client()
		r = self.client.login(username='foo', password='bar')
		self.assertTrue(r)
		z = Zoo(id=1, name='zoo')
		z2 = Zoo(id=2, name='zoo2')
		z.save()
		z2.save()
		Animal(id=1, name='animal', zoo_id=1).save()
		Animal(id=2, name='animal2', zoo_id=1).save()
		Animal(id=3, name='animal2', zoo_id=2).save()

	def test_parse_filter(self):
		response = self.client.get('/animal/?with=zoo&limit=25&order_by=-name&.name=animal2&.zoo.name=zoo')
		self.assertEqual(200, response.status_code)
		result = jsonloads(response.content)
		expected_result = [{'name': 'animal2', 'zoo': 1, 'zoo_of_birth': None, 'caretaker': None, 'deleted': False,
							'id': 2, 'costume': None}]
		self.assertEqual(expected_result, result['data'])

	def test_parse_filter_should_be_empty(self):
		response = self.client.get('/animal/?with=zoo&limit=25&order_by=-name&.name=non_existent_animal&.zoo.name=zoo')
		self.assertEqual(200, response.status_code)
		result = jsonloads(response.content)
		self.assertEqual([], result['data'])
