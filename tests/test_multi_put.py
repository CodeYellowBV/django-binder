from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User

from .testapp.models import Animal, Zoo

class MultiPutTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)


	def test_put_several_simple_items(self):
		model_data = {
			'data': [{
				'id': -1,
				'name': 'Scooby Doo',
			}, {
				'id': -2,
				'name': 'Scrappy Doo',
			}]
		}
		response = self.client.put('/animal/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertEqual(2, len(returned_data['idmap']['animal']))
		self.assertIsNotNone(returned_data['idmap']['animal'][0])
		self.assertIsNotNone(returned_data['idmap']['animal'][1])

		idmap=dict(returned_data['idmap']['animal'])

		scooby = Animal.objects.get(pk=idmap[-1])
		self.assertEqual(scooby.name, 'Scooby Doo')
		scrappy = Animal.objects.get(pk=idmap[-2])
		self.assertEqual(scrappy.name, 'Scrappy Doo')


	def test_put_with_mixed_ids_updates_existing_items(self):
		scooby = Animal(name='Scoooooby Dooooo')
		scooby.save()

		model_data = {
			'data': [{
				'id': scooby.pk,
				'name': 'Scooby Doo',
			}, {
				'id': -1,
				'name': 'Scrappy Doo',
			}]
		}
		response = self.client.put('/animal/', data=json.dumps(model_data), content_type='application/json')

		returned_data = jsonloads(response.content)
		self.assertEqual(1, len(returned_data['idmap']['animal']))
		self.assertIsNotNone(returned_data['idmap']['animal'][0])

		self.assertNotEqual(scooby.pk, returned_data['idmap']['animal'][0][1])

		idmap=dict(returned_data['idmap']['animal'])

		scooby = Animal.objects.get(pk=scooby.pk)
		self.assertEqual(scooby.name, 'Scooby Doo')
		scrappy = Animal.objects.get(pk=idmap[-1])
		self.assertEqual(scrappy.name, 'Scrappy Doo')


	def test_put_relations_from_referencing_side(self):
		with_model_data = {
			'data': [{
				'id': -2,
				'zoo': -1,
				'name': 'Daffy Duck',
			}, {
				'id': -3,
				'zoo': -2,
				'name': 'Pluto',
			}, {
				# Mix up the order, this should not matter
				'id': -1,
				'zoo': -1,
				'name': 'Scooby Doo',
			}, {
				'id': -4,
				'zoo': -2,
				'name': 'Stimpson J Cat',
			}],
			'with': {
				'zoo': [{
					'id': -1,
					'name': 'Slagharen',
				}, {
					# Unreferenced from main entity, but should still be created
					'id': -3,
					'name': 'Apenheul',
				}, {
					'id': -2,
					'name': 'Burgers\' Zoo',
				}],
			},
		}
		response = self.client.put('/animal/', data=json.dumps(with_model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)

		animal_idmap=dict(returned_data['idmap']['animal'])
		zoo_idmap=dict(returned_data['idmap']['zoo'])

		self.assertEqual(4, len(animal_idmap))
		self.assertEqual(3, len(zoo_idmap))

		# Check zoos
		slagharen=Zoo.objects.get(pk=zoo_idmap[-1])
		self.assertEqual('Slagharen', slagharen.name)
		burgers=Zoo.objects.get(pk=zoo_idmap[-2])
		self.assertEqual("Burgers' Zoo", burgers.name)
		apenheul=Zoo.objects.get(pk=zoo_idmap[-3])
		self.assertEqual('Apenheul', apenheul.name)

		# Check animals
		scooby=Animal.objects.get(pk=animal_idmap[-1])
		self.assertEqual('Scooby Doo', scooby.name)
		self.assertEqual(slagharen, scooby.zoo)

		daffy=Animal.objects.get(pk=animal_idmap[-2])
		self.assertEqual('Daffy Duck', daffy.name)
		self.assertEqual(slagharen, daffy.zoo)

		pluto=Animal.objects.get(pk=animal_idmap[-3])
		self.assertEqual('Pluto', pluto.name)
		self.assertEqual(burgers, pluto.zoo)

		stimpy=Animal.objects.get(pk=animal_idmap[-4])
		self.assertEqual('Stimpson J Cat', stimpy.name)
		self.assertEqual(burgers, stimpy.zoo)


	def test_put_relations_from_referenced_side(self):
		with_model_data = {
			'data': [{
				'id': -1,
				'name': 'Central Park Zoo',
				# TODO
				#'animals': [-1, -2],
			}, {
				# A gap in IDs, should not matter either
				'id': -3,
				'name': 'Artis',
				#'animals': [-4],
			}],
			'with': {
				'animal': [{
					'id': -1,
					'name': 'Alex the lion',
					'zoo': -1,
				}, {
					'id': -2,
					'name': 'Ren Höek',
					'zoo': -1,
				}, {
					'id': -3,
					'name': 'Tom',
				}, {
					'id': -4,
					'name': 'Jerry',
					'zoo': -3,
				}],
			},
		}
		response = self.client.put('/zoo/', data=json.dumps(with_model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)

		zoo_idmap=dict(returned_data['idmap']['zoo'])
		animal_idmap=dict(returned_data['idmap']['animal'])

		self.assertEqual(2, len(zoo_idmap))
		self.assertEqual(4, len(animal_idmap))

		# Check zoos
		central_park=Zoo.objects.get(pk=zoo_idmap[-1])
		self.assertEqual('Central Park Zoo', central_park.name)
		artis=Zoo.objects.get(pk=zoo_idmap[-3])
		self.assertEqual('Artis', artis.name)

		# Check animals
		alex=Animal.objects.get(pk=animal_idmap[-1])
		self.assertEqual('Alex the lion', alex.name)
		self.assertEqual(central_park, alex.zoo)

		ren=Animal.objects.get(pk=animal_idmap[-2])
		self.assertEqual('Ren Höek', ren.name)
		self.assertEqual(central_park, ren.zoo)

		tom=Animal.objects.get(pk=animal_idmap[-3])
		self.assertEqual('Tom', tom.name)
		self.assertIsNone(tom.zoo)

		jerry=Animal.objects.get(pk=animal_idmap[-4])
		self.assertEqual('Jerry', jerry.name)
		self.assertEqual(artis, jerry.zoo)


	def test_put_remove_item(self):
		with_model_data = {
			'data': [{
				'id': -1,
				'name': 'Scooby Doo',
				'zoo': -1,
			}],
			'with': {
				'zoo': [{
					'id': -1,
					'name': 'Artis',
				}],
			},
		}
		response = self.client.put('/animal/', data=json.dumps(with_model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)

		animal_idmap=dict(returned_data['idmap']['animal'])
		scooby_pk = animal_idmap[-1]

		scooby = Animal.objects.get(pk=scooby_pk)
		self.assertEqual('Artis', scooby.zoo.name)

		with_model_data = {
			'data': [{
				'id': scooby_pk,
				'zoo': None,
			}],
			'with': {},
		}
		response = self.client.put('/animal/', data=json.dumps(with_model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		scooby = Animal.objects.get(pk=scooby_pk)
		self.assertEqual(None, scooby.zoo)

	def test_put_nested_validation_errors(self):
		model_data = {
			'data': [{
				'id': -1,
				'name': 'Apenheul'
			}],
			'with': {
				'animal': [{
					'id': -2,
					'name': 'Harambe',
					'zoo': -1
				}, {
					'id': -3,
					'zoo': -1
				}]
			}
		}

		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)
		self.assertIn('animal[1].name', returned_data['error']['validation_errors'])
