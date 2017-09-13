import unittest
import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Animal



class TestValidationErrors(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)
		a = Animal(id=1, name='Test animal so FKs work').save()



	def test_post_reverse_fk_correct(self):
		model_data = { 'name': 'foo', 'animals': [1] }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'animals': [1],
			'id': 1,
			'name': 'foo',
			EXTRA(): None,
		})



	def test_post_reverse_fk_nonexistent(self):
		model_data = { 'name': 'foo', 'animals': [555] }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'zoo': {
					'null': {
						'animals': [
							{
								'code': 'does_not_exist',
								'model': 'Animal',
								'values': [555],
								MAYBE('message'): ANY(str),
							}
						]
					}
				}
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})



	def test_post_reverse_fk_notlist(self):
		model_data = { 'name': 'foo', 'animals': 555 }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})




	def test_post_reverse_fk_containsnull(self):
		model_data = { 'name': 'foo', 'animals': [1, None] }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})



	def test_multiput_reverse_fk_correct(self):
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [1]} ] }

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'idmap': ANY(dict),
		})



	def test_multiput_reverse_fk_nonexistent(self):
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [555]} ]}

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'zoo': {
					'null': {
						'animals': [
							{
								'code': 'does_not_exist',
								'model': 'Animal',
								'values': [555],
								MAYBE('message'): ANY(str),
							}
						]
					}
				}
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})



	def test_multiput_reverse_fk_notlist(self):
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': 555} ] }

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})




	def test_multiput_reverse_fk_containsnull(self):
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [1, None]} ] }

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})
