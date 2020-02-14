import json
import unittest
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

	def test_user_activation_correct(self):
		self.assertFalse(self.user2.is_active)

		self.client = Client()

		data = {
			'activation_code': (str(self.token))
		}

		r = self.client.put('/user/' + str(self.user2.id) + '/activate/', data=json.dumps(data),
							content_type='application/json')

		self.assertEqual(200, r.status_code)
		self.user2.refresh_from_db()
		self.assertTrue(self.user2.is_active)

	def test_user_activation_incorrect(self):
		# Reset setup for new test
		self.user2.is_active = False
		self.user2.save()
		self.assertFalse(self.user2.is_active)

		self.client = Client()

		data = {
			'activation_code': "OH NO WRONG TOKEN SENT TO BACKEND"
		}

		r = self.client.put('/user/' + str(self.user2.id) + '/activate/', data=json.dumps(data),
							content_type='application/json')

		self.assertEqual(404, r.status_code)
		self.assertFalse(self.user2.is_active)


@unittest.skip("Feature has_permission filter currently not built in to binder, was wrongly implemented in T10963. "
			   "Can be enabled again once the functionallity is properly added")
class UserFilterParseTest(TestCase):

	def setUp(self):
		super().setUp()
		self.super_user = User.objects.create_user(username='foo', password='bar', is_active=True, is_superuser=True)
		self.user2 = User.objects.create_user(username='bar', password='foo', is_active=True, is_superuser=False)
		self.user_without_group = User.objects.create_user(username='teszts', password='user_4', is_active=True,
														   is_superuser=False)
		self.user3 = User.objects.create_user(username='test', password='bar', is_active=True, is_superuser=False)
		group = Group.objects.get()
		print(group.permissions.get().codename)
		# add users 2 and 3 to the group, giving them the high level testapp.view_country permission
		self.user2.groups.add(group)
		self.user3.groups.add(group)

		self.super_user.save()
		self.user2.save()
		self.user_without_group.save()
		self.user3.save()
		self.client = Client()
		# login as a non superuser
		r = self.client.login(username='foo', password='bar')
		self.assertTrue(r)

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_incorrect_permission_only_returns_superuser(self):
		# this test should only returnd the superuser, since there is no group (and no users belonging to that group)
		# that has this permission
		result = self.client.get('/user/?.has_permission=foo.bar.permissions')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(self.super_user.username, result_json['data'][0]['username'])
		self.assertEqual(1, len(result_json['data']))

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_only_correct_has_permission(self):
		# this should result in both the superuser and the two users that belong to this permission group, the third
		# that does not should not be returned
		result = self.client.get('/user/?.has_permission=testapp.view_country')
		print(self.user2.groups.get().permissions)
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		print(result_json)
		# bar is the first user that belongs to the group that has this permission
		self.assertEqual(self.super_user.username, result_json['data'][0]['username'])

		self.assertEqual(3, len(result_json['data']))

	@override_settings(BINDER_PERMISSION={
		# The only high level permission available in test is testapp.view_country (see general __init__)
		# in here you have to define any low level permissions you wish to use on models
		'testapp.view_country': [
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_with_has_permission_and_partial(self):
		# here we select the users of the group which has the testapp.view_country permission. then withing that
		# group we search for a user whos name contains tes
		result = self.client.get('/user/?.has_permission=testapp.view_country&.username:icontains=tes')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		print(result_json)
		# there is also a user teszts which would appear if we did not filter on permission group (test is member of group)
		# teszts is not, so that is why this test makes sense
		self.assertEqual(self.user3.username, result_json['data'][0]['username'])
		self.assertEqual(1, len(result_json['data']))

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_zoo', 'all'),
			('testapp.view_animal', 'all')
		],
	})
	def test_parse_filter_userview_without_has_permission(self):
		result = self.client.get('/user/?.username=test')
		self.assertEqual(200, result.status_code)
		result_json = json.loads(result.content.decode('utf-8'))
		self.assertEqual(self.user3.username, result_json['data'][0]['username'])
		self.assertEqual(1, len(result_json['data']))
