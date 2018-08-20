from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User

from binder.plugins.token_auth.models import Token
from binder.json import jsonloads, jsondumps

from binder.tests.compare import assert_json, ANY, EXTRA


@override_settings(
	BINDER_TOKEN_EXPIRE_TIME=timedelta(days=1),
	BINDER_TOKEN_EXPIRE_BASE='last_used_at',
)
class TokenAuthTest(TestCase):

	def setUp(self):
		self.user = User.objects.create_user(username='foo', password='bar')
		self.user.save()
		self.token = Token(user=self.user)
		self.token.save()
		self.client = Client(HTTP_AUTHORIZATION='Token ' + self.token.token)

	def test_token_auth(self):
		res = self.client.get('/user/')
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		self.assertEqual(res, {'username': 'foo', 'email': ''})

	def test_no_token_auth(self):
		res = Client().get('/user/')
		self.assertEqual(res.status_code, 403)

	def test_session_auth(self):
		client = Client()
		self.assertTrue(client.login(username='foo', password='bar'))
		res = client.get('/user/')
		self.assertEqual(res.status_code, 200)

	@override_settings(
		BINDER_TOKEN_EXPIRE_TIME=timedelta(days=-1),
	)
	def test_token_expired(self):
		res = self.client.get('/user/')
		self.assertEqual(res.status_code, 400)
		res = jsonloads(res.content)
		assert_json(res, {
			'code': 'TokenExpired',
			'message': ANY(str),
			'token': self.token.token,
			'expired_at': ANY(),
			EXTRA(): None,
		})

	def test_token_not_found(self):
		old_token = self.token.token
		self.token.token = 'foo'
		self.token.save()

		res = self.client.get('/user/')
		self.assertEqual(res.status_code, 404)
		res = jsonloads(res.content)
		assert_json(res, {
			'code': 'TokenNotFound',
			'message': ANY(str),
			'token': old_token,
			EXTRA(): None,
		})

	def test_other_auth_type(self):
		client = Client(HTTP_AUTHORIZATION='Foo ' + self.token.token)
		res = client.get('/user/')
		self.assertEqual(res.status_code, 403)


@override_settings(
	BINDER_PERMISSION={
		'default': [
			('auth.login_user', None),
			('token_auth.add_token', 'own'),
			('token_auth.view_token', 'own'),
			('token_auth.change_token', 'own'),
			('token_auth.delete_token', 'own'),
		],
	},
	BINDER_TOKEN_EXPIRE_TIME=timedelta(days=1),
	BINDER_TOKEN_EXPIRE_BASE='last_used_at',
)
class TokenLoginTest(TestCase):

	def setUp(self):
		self.user = User.objects.create_user(username='foo', password='bar')
		self.user.save()

	def test_login(self):
		client = Client()
		res = client.post('/token/login/', {
			'username': 'foo',
			'password': 'bar',
		})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		self.assertEqual(res['user'], self.user.pk)

		client = Client(HTTP_AUTHORIZATION='Token ' + res['token'])
		res = client.get('/user/')
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		self.assertEqual(res['username'], 'foo')

	def test_login_fail(self):
		client = Client()
		res = client.post('/token/login/', {
			'username': 'foo',
			'password': 'baz',
		})
		self.assertEqual(res.status_code, 403)
		res = jsonloads(res.content)
		self.assertEqual(res['code'], 'NotAuthenticated')
