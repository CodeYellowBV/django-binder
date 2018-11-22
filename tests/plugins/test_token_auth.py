from io import StringIO
from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError

from binder.plugins.token_auth.models import Token
from binder.json import jsonloads

from ..compare import assert_json, ANY, EXTRA


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
		res = self.client.get('/user/identify/')
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		self.assertEqual(res, {'username': 'foo', 'email': ''})

	def test_no_token_auth(self):
		res = Client().get('/user/identify/')
		self.assertEqual(res.status_code, 403)

	def test_session_auth(self):
		client = Client()
		self.assertTrue(client.login(username='foo', password='bar'))
		res = client.get('/user/identify/')
		self.assertEqual(res.status_code, 200)

	@override_settings(
		BINDER_TOKEN_EXPIRE_TIME=timedelta(days=-1),
	)
	def test_token_expired(self):
		res = self.client.get('/user/identify/')
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

		res = self.client.get('/user/identify/')
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
		res = client.get('/user/identify/')
		self.assertEqual(res.status_code, 403)


@override_settings(
	BINDER_PERMISSION={
		'default': [
			('auth.login_user', None),
			('token_auth.add_token', 'own'),
			('token_auth.view_token', 'own'),
			('auth.view_user', 'own'),
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

		res = client.get('/user/identify/')

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



class CreateUserTokenTest(TestCase):
	def test_create_user_token_fails_cleanly_when_user_does_not_exist(self):
		with self.assertRaises(CommandError) as cm:
			call_command('create_user_token', 'testuser@example.com')

		self.assertEqual('User with username "testuser@example.com" does not exist', str(cm.exception))
		self.assertFalse(Token.objects.exists())


	def test_create_user_token_creates_token_when_user_exists(self):
		user = User(username='testuser@example.com')
		user.save()

		out = StringIO()
		call_command('create_user_token', 'testuser@example.com', stdout=out)

		self.assertEqual(1, Token.objects.count())
		self.assertEqual(1, Token.objects.filter(user=user).count())

		self.assertIn("Generated token for user testuser@example.com: %s." % Token.objects.get().token, out.getvalue())
		self.assertIn("User now has 1 token(s).", out.getvalue())


	def test_create_user_token_replaces_existing_tokens_for_passed_user_when_keep_is_omitted(self):
		user1 = User(username='someone@example.com') # Ensure we don't destroy other users tokens
		user1.save()
		token1 = Token(user=user1)
		token1.save()

		user2 = User(username='testuser@example.com')
		user2.save()
		token2 = Token(user=user2)
		token2.save()
		token3 = Token(user=user2)
		token3.save()

		self.assertEqual(3, Token.objects.count())

		out = StringIO()
		call_command('create_user_token', 'testuser@example.com', stdout=out)

		self.assertEqual(2, Token.objects.count())
		self.assertEqual(1, Token.objects.filter(user=user2).count())

		self.assertTrue(Token.objects.filter(id=token1.id).exists())
		self.assertFalse(Token.objects.filter(id=token2.id).exists())
		self.assertFalse(Token.objects.filter(id=token3.id).exists())

		token4 = Token.objects.exclude(id__in=[token1.id, token2.id, token3.id]).get()
		self.assertNotEqual(token1.token, token4.token)
		self.assertNotEqual(token2.token, token4.token)
		self.assertNotEqual(token3.token, token4.token)

		self.assertIn("Generated token for user testuser@example.com: %s." % Token.objects.filter(user=user2).exclude(id__in=[token2.id, token3.id]).get().token, out.getvalue())
		self.assertIn("User now has 1 token(s).", out.getvalue())


	def test_create_user_token_keeps_existing_tokens_when_keep_is_passed(self):
		user = User(username='testuser@example.com')
		user.save()
		token1 = Token(user=user)
		token1.save()
		token2 = Token(user=user)
		token2.save()

		self.assertEqual(2, Token.objects.count())

		out = StringIO()
		call_command('create_user_token', '-k', 'testuser@example.com', stdout=out)

		self.assertEqual(3, Token.objects.count())
		self.assertEqual(3, Token.objects.filter(user=user).count())

		self.assertTrue(Token.objects.filter(id=token1.id).exists())
		self.assertTrue(Token.objects.filter(id=token2.id).exists())

		token3 = Token.objects.exclude(id__in=[token1.id, token2.id]).get()

		self.assertIn("Generated token for user testuser@example.com: %s." % Token.objects.filter(user=user).exclude(id__in=[token1.id, token2.id]).get().token, out.getvalue())
		self.assertIn("User now has 3 token(s).", out.getvalue())

		out = StringIO()
		call_command('create_user_token', '--keep-existing', 'testuser@example.com', stdout=out)

		self.assertEqual(4, Token.objects.count())
		self.assertEqual(4, Token.objects.filter(user=user).count())

		token4 = Token.objects.exclude(id__in=[token1.id, token2.id, token3.id]).get()

		self.assertNotEqual(token1.token, token4.token)
		self.assertNotEqual(token2.token, token4.token)
		self.assertNotEqual(token3.token, token4.token)

		self.assertIn("Generated token for user testuser@example.com: %s." % Token.objects.filter(user=user).exclude(id__in=[token1.id, token2.id, token3.id]).get().token, out.getvalue())
		self.assertIn("User now has 4 token(s).", out.getvalue())


class DeleteUserTokenTest(TestCase):
	def test_delete_user_token_fails_cleanly_when_user_does_not_exist(self):
		with self.assertRaises(CommandError) as cm:
			call_command('delete_user_token', 'testuser@example.com')

		self.assertEqual('User with username "testuser@example.com" does not exist', str(cm.exception))
		self.assertFalse(Token.objects.exists())


	def test_delete_user_token_deletes_existing_tokens_but_only_for_passed_user(self):
		user1 = User(username='someone@example.com') # Ensure we don't destroy other users tokens
		user1.save()
		token1 = Token(user=user1)
		token1.save()

		user2 = User(username='testuser@example.com')
		user2.save()
		token2 = Token(user=user2)
		token2.save()
		token3 = Token(user=user2)
		token3.save()

		self.assertEqual(3, Token.objects.count())

		out = StringIO()
		call_command('delete_user_token', 'testuser@example.com', stdout=out)

		self.assertEqual(1, Token.objects.count())
		self.assertEqual(0, Token.objects.filter(user=user2).count())

		self.assertTrue(Token.objects.filter(id=token1.id).exists())
		self.assertFalse(Token.objects.filter(id=token2.id).exists())
		self.assertFalse(Token.objects.filter(id=token3.id).exists())

		self.assertIn("Deleted 2 token(s) for user testuser@example.com.", out.getvalue())
