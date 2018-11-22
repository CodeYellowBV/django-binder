from unittest.mock import patch

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, Client

import json
from binder.json import JsonResponse


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
