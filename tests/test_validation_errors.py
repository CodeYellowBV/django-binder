import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, MAYBE, ANY
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
		a = Animal(name='Test animal so FKs work')
		a.save()
		self.animal_id = a.id



	def test_post_validate_blank(self):
		model_data = {}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data['code'], 'ValidationError')
		self.assertEqual(len(returned_data['errors']), 1)
		self.assertEqual(len(returned_data['errors']['animal']), 1)
		obj_id = list(returned_data['errors']['animal'])[0]
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]), 1)
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]['name']), 1)
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['code'], 'blank')
		self.assertIn('message', returned_data['errors']['animal'][obj_id]['name'][0])



	def test_post_validate_notblank_notnull_getsblank(self):
		model_data = { 'name': '' }

		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'animal': {
					'null': {
						'name': [
							{'code': 'blank', MAYBE('message'): ANY(str)}
						]
					}
				}
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})



	def test_post_validate_notblank_notnull_getsnull(self):
		model_data = { 'name': None }

		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'animal': {
					'null': {
						'name': [
							{'code': 'null', MAYBE('message'): ANY(str)}
						]
					}
				}
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})



	def test_post_validate_blank_null_getsblank(self):
		model_data = { 'animal': self.animal_id, 'description': '' }

		response = self.client.post('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)


	def test_post_validate_blank_null_getsnull(self):
		model_data = { 'animal': self.animal_id, 'description': None }

		response = self.client.post('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)



	def test_post_validate_blank_notnull_getsblank(self):
		model_data = { 'animal': self.animal_id, 'nickname': '' }

		response = self.client.post('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)



	def test_post_validate_blank_notnull_getsnull(self):
		model_data = { 'animal': self.animal_id, 'nickname': None }

		response = self.client.post('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'costume': {
					list(returned_data['errors']['costume'].keys())[0]: {
						'nickname': [
							{'code': 'null', MAYBE('message'): ANY(str)}
						]
					}
				}
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})



	def test_post_validate_field_gets_invalid_string_representation_for_data_type(self):
		model_data = { 'name': 'Gettysburg', 'founding_date': 'Four score and seven years ago' }

		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'errors': {
				'zoo': {
					'null': {
						'founding_date': [
							{'code': 'invalid', MAYBE('message'): ANY(str)}
						]
					},
				},
			},
			'code': 'ValidationError',
			MAYBE('debug'): ANY(),
		})


	def test_put_validate_max_length(self):
		model = Animal(name='Harambe')
		model.full_clean()
		model.save()
		model_data = {
			'name': 'HarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambe'
		}
		response = self.client.put('/animal/{}/'.format(model.id), data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data['code'], 'ValidationError')
		self.assertEqual(len(returned_data['errors']), 1)
		self.assertEqual(len(returned_data['errors']['animal']), 1)
		obj_id = list(returned_data['errors']['animal'])[0]
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]), 1)
		self.assertEqual(len(returned_data['errors']['animal'][obj_id]['name']), 1)
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['code'], 'max_length')
		self.assertIn('message', returned_data['errors']['animal'][obj_id]['name'][0])
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['limit_value'], 64)
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['show_value'], 70)
		self.assertEqual(returned_data['errors']['animal'][obj_id]['name'][0]['value'], 'HarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambe')



	def test_multiput_validate(self):
		model_data = {
			'data': [{
				'id': -1,
				'animals': [-2, -3]
			}],
			'with': {
				'animal': [{
					'id': -2,
					'name': 'HarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambe'
				}, {
					'id': -3,
				}]
			}
		}

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data['code'], 'ValidationError')
		self.assertEqual(len(returned_data['errors']), 2)
		self.assertEqual(len(returned_data['errors']['zoo']), 1)
		self.assertEqual(len(returned_data['errors']['animal']), 2)
		self.assertEqual(len(returned_data['errors']['zoo']['-1']), 1)
		self.assertEqual(len(returned_data['errors']['animal']['-2']), 1)
		self.assertEqual(len(returned_data['errors']['animal']['-3']), 1)
		self.assertEqual(len(returned_data['errors']['zoo']['-1']['name']), 1)
		self.assertEqual(len(returned_data['errors']['animal']['-2']['name']), 1)
		self.assertEqual(len(returned_data['errors']['animal']['-3']['name']), 1)
		self.assertEqual(returned_data['errors']['zoo']['-1']['name'][0]['code'], 'blank')
		self.assertEqual(returned_data['errors']['animal']['-2']['name'][0]['code'], 'max_length')
		self.assertIn('message', returned_data['errors']['animal']['-2']['name'][0])
		self.assertEqual(returned_data['errors']['animal']['-2']['name'][0]['limit_value'], 64)
		self.assertEqual(returned_data['errors']['animal']['-2']['name'][0]['show_value'], 70)
		self.assertEqual(returned_data['errors']['animal']['-2']['name'][0]['value'], 'HarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambeHarambe')
		self.assertEqual(returned_data['errors']['animal']['-3']['name'][0]['code'], 'blank')



	def test_multiput_validate_snake_cased_model(self):
		model_data = {
			'id': None,
		}

		response = self.client.post('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertEqual(len(returned_data['errors']), 1)
		# Important detail: we expect the name of the model to be `contact_person` (snake-cased), NOT `contactperson`
		self.assertEqual(len(returned_data['errors']['contact_person']), 1)

	def test_multiput_auto_now(self):
		model_data = {
			'data': [{
				'id': -1,
				'name': 'Henk',
			}],
			'with': {}
		}

		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

	def test_multiput_validate_unique_constraint_fail(self):
		model_data = {
			'data': [{
				'id': -1,
				'name': 'Henk',
			}],
			'with': {}
		}

		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		returned_data = jsonloads(response.content)

		self.assertEqual(len(returned_data['errors']), 1)
		self.assertEqual(len(returned_data['errors']['contact_person']), 1)
		self.assertIn('name', returned_data['errors']['contact_person']['-1'])
		self.assertEqual('unique', returned_data['errors']['contact_person']['-1']['name'][0]['code'])
