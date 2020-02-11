import json
from unittest.mock import patch

from django.contrib.auth.models import User, Group
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, Client, override_settings

from binder.json import JsonResponse, jsonloads


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
		self.user2 = User.objects.create_user(id=7, username='test', password='user')
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

	def test_user_activation_correct(self):
		self.client = Client()

		data = {
			'activation_code': (str(self.token))
		}

		r = self.client.put('/user/' + str(self.user2.id) + '/activate/', data=json.dumps(data),
							content_type='application/json')

		self.assertEqual(200, r.status_code)
		self.assertTrue(self.user2.is_active)

	def test_user_activation_incorrect(self):
		# Reset setup for new test
		self.user2.is_active = False
		self.user2.save()

		self.client = Client()

		data = {
			'activation_code': "OH NO WRONG TOKEN SENT TO BACKEND"
		}

		r = self.client.put('/user/' + str(self.user2.id) + '/activate/', data=json.dumps(data),
							content_type='application/json')

		self.assertEqual(404, r.status_code)
		self.assertFalse(self.user2.is_active)


class UserFilterParseTest(TestCase):

	def setUp(self):
		super().setUp()
		self.user = User.objects.create_user(username='foo', password='bar', is_active=True, is_superuser=False)
		self.user2 = User.objects.create_user(username='bar', password='foo', is_active=True, is_superuser=True)
		self.user3 = User.objects.create_user(username='test', password='bar', is_active=True, is_superuser=True)
		group = Group.objects.get()
		self.user.groups.add(group)
		self.user.save()
		self.user2.save()
		self.user3.save()
		self.client = Client()
		r = self.client.login(username='foo', password='bar')
		self.assertTrue(r)

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('auth.view_user', 'all'),
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_incorrect_permission_is_ignored(self):
		result = self.client.get('/user/?has_permission=incorrect.perm')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(result_json['data'][0]['username'], 'foo')

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('auth.view_user', 'all'),
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_only_correct_has_permission(self):
		result = self.client.get('/user/?has_permission=testapp.view_animal')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(result_json['data'][0]['username'], 'foo')

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('auth.view_user', 'all'),
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_has_permission_and_partial(self):
		result = self.client.get('/user/?has_permission=testapp.view_zoo&.username:icontains=tes')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(result_json['data'][0]['username'], 'test')

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('auth.view_user', 'all'),
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_without_has_permission(self):
		result = self.client.get('/user/?.username=test')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(result_json['data'][0]['username'], 'test')
