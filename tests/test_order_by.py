import unittest
import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Animal, Costume



class CustomOrdering:
	def __init__(self, cls, order):
		self.cls = cls
		self.order = order

	def __enter__(self):
		self.old = self.cls.Meta.ordering[0]
		self.cls.Meta.ordering[0] = self.order

	def __exit__(self, *args, **kwargs):
		self.cls.Meta.ordering[0] = self.old



class TestValidationErrors(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		Animal(id=1, name='a1').save()
		Animal(id=2, name='a2').save()
		Animal(id=3, name='a3').save()
		Animal(id=4, name='a4').save()

		Costume(id=2, animal_id=2, nickname='Foo', description='Bar').save()
		Costume(id=3, animal_id=3, nickname='Bar', description='Bar').save()
		Costume(id=1, animal_id=1, nickname='Foo', description='Foo').save()
		Costume(id=4, animal_id=4, nickname='Bar', description='Foo').save()



	# Order by model default (id)
	def test_order_default(self):
		response = self.client.get('/costume/')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [1, 2, 3, 4])



	# Order by custom model default (nickname)
	def test_order_customdefault(self):
		with CustomOrdering(Costume, 'nickname'):
			response = self.client.get('/costume/')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		# Test for nickname, because id sorting is undefined at this point
		data = [x['nickname'] for x in returned_data['data']]
		self.assertEqual(data, ['Bar', 'Bar', 'Foo', 'Foo'])



	# Order by nickname, description
	def test_order_nickname_description(self):
		response = self.client.get('/costume/?order_by=nickname,description')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [3, 4, 2, 1])



	# Order by description, -nickname
	def test_order_description_revnickname(self):
		response = self.client.get('/costume/?order_by=description,-nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [2, 3, 1, 4])



	# Order by nickname, model default (id)
	def test_order_nickname_default(self):
		response = self.client.get('/costume/?order_by=nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [3, 4, 1, 2])



	# Order by -description, model default (id)
	def test_order_revdescription_default(self):
		response = self.client.get('/costume/?order_by=-description')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [1, 4, 2, 3])



	# Order by nickname, custom model default (-id)
	def test_order_nickname_customdefault(self):
		with CustomOrdering(Costume, '-id'):
			response = self.client.get('/costume/?order_by=nickname')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 3, 2, 1])



	# Order by -description, custom model default (-id)
	def test_order_revdescription_customdefault(self):
		with CustomOrdering(Costume, '-id'):
			response = self.client.get('/costume/?order_by=-description')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 1, 3, 2])



	# Order by nickname, -id (overriding default model order)
	def test_order_nickname(self):
		response = self.client.get('/costume/?order_by=nickname,-id')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 3, 2, 1])
