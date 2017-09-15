import unittest
import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Zoo, Animal, ContactPerson



class TestValidationErrors(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		ContactPerson(id=1, name='contact1').save()
		z = Zoo(id=1, name='zoo')
		z.save()
		z.contacts.set([1])
		Animal(id=1, name='animal', zoo_id=1).save()



	def test_filter_fk_forward(self):
		response = self.client.get('/animal/?.zoo=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'zoo': 1,
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_fk_backward(self):
		response = self.client.get('/zoo/?.animals=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'animals': [1],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_m2m_forward(self):
		response = self.client.get('/zoo/?.contacts=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'contacts': [1],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_m2m_backward(self):
		response = self.client.get('/contact_person/?.zoos=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'zoos': [1],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})
