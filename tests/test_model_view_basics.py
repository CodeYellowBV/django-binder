from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User

from .testapp.models import Animal, Zoo

class ModelViewBasicsTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)


	def test_post_new_model(self):
		model_data = {
			'name': 'Scooby Doo',
		}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertIsNotNone(returned_data.get('id'))
		self.assertEqual(returned_data.get('name'), 'Scooby Doo')


	def test_get_model_with_valid_id(self):
		daffy = Animal(name='Daffy Duck')
		daffy.full_clean()
		daffy.save()

		response = self.client.get('/animal/%d/' % (daffy.pk,))

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		data = result['data']
		self.assertEqual(data.get('id'), daffy.pk)
		self.assertEqual(data.get('name'), 'Daffy Duck')


	def test_get_model_with_invalid_id_sets_correct_code(self):
		response = self.client.get('/animal/1234/')

		self.assertEqual(response.status_code, 404)

		result = jsonloads(response.content)
		self.assertEqual('NotFound', result['code'])


	def test_get_collection_with_no_models_returns_empty_array(self):
		response = self.client.get('/animal/')

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual([], result['data'])


	def test_get_collection_sorting(self):
		gaia = Zoo(name='GaiaZOO')
		gaia.full_clean()
		gaia.save()

		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.full_clean()
		emmen.save()

		coyote = Animal(name='Wile E. Coyote', zoo=gaia)
		coyote.full_clean()
		coyote.save()

		roadrunner = Animal(name='Roadrunner', zoo=gaia)
		roadrunner.full_clean()
		roadrunner.save()

		woody = Animal(name='Woody Woodpecker', zoo=emmen)
		woody.full_clean()
		woody.save()

		response = self.client.get('/animal/', data={'order_by': 'name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual('Roadrunner', result['data'][0]['name'])
		self.assertEqual('Wile E. Coyote', result['data'][1]['name'])
		self.assertEqual('Woody Woodpecker', result['data'][2]['name'])

		# Reverse sorting
		response = self.client.get('/animal/', data={'order_by': '-name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual('Woody Woodpecker', result['data'][0]['name'])
		self.assertEqual('Wile E. Coyote', result['data'][1]['name'])
		self.assertEqual('Roadrunner', result['data'][2]['name'])


		# Sorting by related field and then the main field
		response = self.client.get('/animal/', data={'order_by': 'zoo.name,name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual('Roadrunner', result['data'][0]['name'])
		self.assertEqual('Wile E. Coyote', result['data'][1]['name'])
		self.assertEqual('Woody Woodpecker', result['data'][2]['name'])


		response = self.client.get('/animal/', data={'order_by': '-zoo.name,name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual('Woody Woodpecker', result['data'][0]['name'])
		self.assertEqual('Roadrunner', result['data'][1]['name'])
		self.assertEqual('Wile E. Coyote', result['data'][2]['name'])

		# Sorting by nonexistent field errors
		response = self.client.get('/animal/', data={'order_by': 'zoo__name'})

		self.assertEqual(response.status_code, 418)
		result = jsonloads(response.content)
		self.assertEqual('RequestError', result['code'])


	def test_get_collection_with_relations(self):
		gaia = Zoo(name='GaiaZOO')
		gaia.full_clean()
		gaia.save()

		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.full_clean()
		emmen.save()

		coyote = Animal(name='Wile E. Coyote', zoo=gaia)
		coyote.full_clean()
		coyote.save()

		roadrunner = Animal(name='Roadrunner', zoo=gaia)
		roadrunner.full_clean()
		roadrunner.save()

		woody = Animal(name='Woody Woodpecker', zoo=emmen)
		woody.full_clean()
		woody.save()

		# Quick check that relations are excluded unless we ask for them
		response = self.client.get('/animal/', data={'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		self.assertIsNone(response.get('with_mapping'))
		self.assertIsNone(response.get('with'))


		response = self.client.get('/animal/', data={'order_by': 'name', 'with': 'zoo'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual(3, len(result['with_mapping']['zoo']))
		self.assertEqual(2, len(result['with']['zoo']))
		# TODO: Add test for relations with different name than models
		self.assertEqual('zoo', result['with_mapping']['zoo'])

		self.assertEqual(gaia.pk, result['data'][0]['zoo'])
		zoo_by_id = {zoo['id']: zoo for zoo in result['with']['zoo']}
		self.assertEqual('GaiaZOO', zoo_by_id[gaia.pk]['name'])
		self.assertEqual('Wildlands Adventure Zoo Emmen', zoo_by_id[emmen.pk]['name'])
		self.assertSetEqual(set([coyote.pk, roadrunner.pk]),
				    set(zoo_by_id[gaia.pk]['animals']))
		self.assertSetEqual(set([woody.pk]), set(zoo_by_id[emmen.pk]['animals']))
