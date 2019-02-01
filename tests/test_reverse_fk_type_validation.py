import json

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.db.models import Max

from binder.json import jsonloads

from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Animal



class TestReverseFKValidationErrors(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)
		self.animal = Animal(name='Test animal so FKs work')
		self.animal.save()



	def test_post_reverse_fk_correct(self):
		model_data = { 'name': 'foo', 'animals': [self.animal.id] }

		response = self.client.post('/zoo/?with=animals', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'animals': [self.animal.id],
			'id': ANY(int),
			'name': 'foo',
			EXTRA(): None,
		})



	def test_post_reverse_fk_nonexistent(self):
		nonexistent = Animal.objects.all().aggregate(Max('pk'))['pk__max'] + 1
		model_data = { 'name': 'foo', 'animals': [nonexistent] }

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
								'values': [nonexistent],
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
		model_data = { 'name': 'foo', 'animals': [self.animal.id, None] }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})



	def test_multiput_reverse_fk_correct(self):
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [self.animal.id]} ] }

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'idmap': ANY(dict),
		})



	def test_multiput_reverse_fk_nonexistent(self):
		nonexistent = Animal.objects.all().aggregate(Max('pk'))['pk__max'] + 1
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [nonexistent]} ]}

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
								'values': [nonexistent],
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
		model_data = { 'data': [ {'id': -1, 'name': 'foo', 'animals': [self.animal.id, None]} ] }

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 418)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'code': 'RequestError',
			'message': 'Type error for field: {Zoo.animals}.',
			MAYBE('debug'): ANY(),
		})
