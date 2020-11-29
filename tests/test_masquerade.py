from django.contrib.auth.models import User
from django.test import TestCase, Client

from binder.json import jsonloads


class MasqueradeTest(TestCase):

	def setUp(self):
		user1 = User(
			username='user1',
			is_active=True,
			is_superuser=True,
		)
		user1.set_password('test')
		user1.save()

		user2 = User(
			username='user2',
			is_active=True,
			is_superuser=True,
		)
		user2.set_password('test')
		user2.save()

		user3 = User(
			username='user3',
			is_active=True,
			is_superuser=False,
		)
		user3.set_password('test')
		user3.save()

		self.client = Client()

	# Helpers
	def login(self, username):
		res = self.client.post('/user/login/', data={
			'username': username,
			'password': 'test',
		})
		self.assertEqual(res.status_code, 200)

	def masquerade(self, username, allowed=True):
		user_pk = User.objects.get(username=username).pk
		res = self.client.post('/user/{}/masquerade/'.format(user_pk))
		self.assertEqual(res.status_code, 200 if allowed else 403)

	def logout(self):
		res = self.client.post('/user/logout/')
		self.assertEqual(res.status_code, 204)

	# Asserts
	def assertLoggedIn(self, username=None):
		res = self.client.get('/user/identify/')
		self.assertEqual(res.status_code, 200)
		if username is not None:
			data = jsonloads(res.content)
			self.assertEqual(data['username'], username)

	def assertLoggedOut(self):
		res = self.client.get('/user/identify/')
		self.assertEqual(res.status_code, 403)

	# Tests
	def test_masquerade(self):
		self.assertLoggedOut()
		self.login('user1')
		self.assertLoggedIn('user1')
		self.masquerade('user2')
		self.assertLoggedIn('user2')
		self.logout()
		self.assertLoggedIn('user1')
		self.logout()
		self.assertLoggedOut()

	def test_multi_masquerade(self):
		self.assertLoggedOut()
		self.login('user1')
		self.assertLoggedIn('user1')
		self.masquerade('user2')
		self.assertLoggedIn('user2')
		self.masquerade('user3')
		self.assertLoggedIn('user3')
		self.logout()
		self.assertLoggedIn('user2')
		self.logout()
		self.assertLoggedIn('user1')
		self.logout()
		self.assertLoggedOut()

	def test_masquerade_non_superuser(self):
		self.assertLoggedOut()
		self.login('user3')
		self.assertLoggedIn('user3')
		self.masquerade('user1', allowed=False)
		self.assertLoggedIn('user3')
		self.logout()
		self.assertLoggedOut()
