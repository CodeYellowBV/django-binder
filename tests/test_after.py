import os

from django.contrib.auth.models import User
from django.test import TestCase

from binder.json import jsonloads

from .testapp.models import Animal, Zoo


class TestAfter(TestCase):

	def setUp(self):
		self.mapping = {}

		zoo1 = Zoo.objects.create(name='Zoo 2')
		self.mapping[Animal.objects.create(name='Animal F', zoo=zoo1, birth_date='1997-03-19').id] = 'f'
		self.mapping[Animal.objects.create(name='Animal E', zoo=zoo1).id] = 'e'
		self.mapping[Animal.objects.create(name='Animal D', zoo=zoo1).id] = 'd'

		zoo2 = Zoo.objects.create(name='Zoo 1')
		self.mapping[Animal.objects.create(name='Animal C', zoo=zoo2, birth_date='2000-08-05').id] = 'c'
		self.mapping[Animal.objects.create(name='Animal B', zoo=zoo2).id] = 'b'
		self.mapping[Animal.objects.create(name='Animal A', zoo=zoo2).id] = 'a'

		user = User(username='testuser', is_active=True, is_superuser=True)
		user.set_password('test')
		user.save()
		self.assertTrue(self.client.login(username='testuser', password='test'))

	def get(self, *ordering, after=None):
		params = {}
		if ordering:
			params['order_by'] = ','.join(ordering)
		if after is not None:
			params['after'] = next(
				pk
				for pk, char in self.mapping.items()
				if char == after
			)

		res = self.client.get('/animal/', params)
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		return ''.join(self.mapping[obj['id']] for obj in res['data'])

	def test_default(self):
		self.assertEqual(self.get(), 'fedcba')
		self.assertEqual(self.get(after='d'), 'cba')

	def test_ordered(self):
		self.assertEqual(self.get('name'), 'abcdef')
		self.assertEqual(self.get('name', after='c'), 'def')

	def test_ordered_relation(self):
		self.assertEqual(self.get('zoo,name'), 'defabc')
		self.assertEqual(self.get('zoo,name', after='f'), 'abc')

	def test_ordered_reverse(self):
		self.assertEqual(self.get('-name'), 'fedcba')
		self.assertEqual(self.get('-name', after='d'), 'cba')

	def test_ordered_relation_field(self):
		self.assertEqual(self.get('zoo.name'), 'cbafed')
		self.assertEqual(self.get('zoo.name', after='a'), 'fed')

	def test_ordered_with_null(self):
		if os.environ.get('BINDER_TEST_MYSQL', '0') != '0':
			# In MySQL null is considered to be the lowest possible value for ordering
			self.assertEqual(self.get('birth_date'), 'edbafc')
			self.assertEqual(self.get('birth_date', after='f'), 'c')
			self.assertEqual(self.get('birth_date', after='e'), 'dbafc')
		else:
			# In other databases null is considered to be the highest possible value for ordering
			self.assertEqual(self.get('birth_date'), 'fcedba')
			self.assertEqual(self.get('birth_date', after='f'), 'cedba')
			self.assertEqual(self.get('birth_date', after='e'), 'dba')

	def test_ordered_with_null_reversed(self):
		if os.environ.get('BINDER_TEST_MYSQL', '0') != '0':
			# In MySQL null is considered to be the lowest possible value for ordering
			self.assertEqual(self.get('-birth_date'), 'cfedba')
			self.assertEqual(self.get('-birth_date', after='c'), 'fedba')
			self.assertEqual(self.get('-birth_date', after='b'), 'a')
		else:
			# In other databases null is considered to be the highest possible value for ordering
			self.assertEqual(self.get('-birth_date'), 'edbacf')
			self.assertEqual(self.get('-birth_date', after='c'), 'f')
			self.assertEqual(self.get('-birth_date', after='b'), 'acf')
