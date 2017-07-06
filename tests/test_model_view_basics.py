from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User

from .testapp.models import Animal, Costume, Zoo, Caretaker, Gate

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


	def test_get_collection_filtering(self):
		gaia = Zoo(name='GaiaZOO')
		gaia.full_clean()
		gaia.save()

		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.full_clean()
		emmen.save()

		artis = Zoo(name='Artis')
		artis.full_clean()
		artis.save()

		coyote = Animal(name='Wile E. Coyote', zoo=gaia)
		coyote.full_clean()
		coyote.save()

		roadrunner = Animal(name='Roadrunner', zoo=gaia)
		roadrunner.full_clean()
		roadrunner.save()

		woody = Animal(name='Woody Woodpecker', zoo=emmen)
		woody.full_clean()
		woody.save()

		donald = Animal(name='Donald Duck', zoo=artis)
		donald.full_clean()
		donald.save()

		response = self.client.get('/animal/', data={'.name': 'Wile E. Coyote'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Wile E. Coyote', result['data'][0]['name'])


		response = self.client.get('/animal/', data={'.name:startswith': 'W', 'order_by': 'name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Wile E. Coyote', result['data'][0]['name'])
		self.assertEqual('Woody Woodpecker', result['data'][1]['name'])


		# Filtering by relation
		response = self.client.get('/animal/', data={'.zoo.name:in': 'Artis,Wildlands Adventure Zoo Emmen', 'order_by': 'name'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Donald Duck', result['data'][0]['name'])
		self.assertEqual('Woody Woodpecker', result['data'][1]['name'])



	def test_get_collection_with_foreignkey(self):
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

		# Quick check that foreign key relations are excluded unless we ask for them
		response = self.client.get('/animal/', data={'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		self.assertIsNone(response.get('with_mapping'))
		self.assertIsNone(response.get('with'))


		response = self.client.get('/animal/', data={'order_by': 'name', 'with': 'zoo'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
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


	def test_get_collection_with_reverse_foreignkey(self):
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

		# Quick check that foreign key relations are excluded unless we ask for them
		response = self.client.get('/zoo/', data={'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		self.assertIsNone(response.get('with_mapping'))
		self.assertIsNone(response.get('with'))

		# Ordering on an attribute of the relation should not mess with result set size!
		response = self.client.get('/zoo/', data={'order_by': 'name', 'with': 'animals'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual(3, len(result['with']['animal']))
		self.assertEqual('animal', result['with_mapping']['animals'])

		self.assertSetEqual(set([roadrunner.pk, coyote.pk]), set(result['data'][0]['animals']))
		animal_by_id = {animal['id']: animal for animal in result['with']['animal']}
		self.assertEqual('Wile E. Coyote', animal_by_id[coyote.pk]['name'])
		self.assertEqual('Roadrunner', animal_by_id[roadrunner.pk]['name'])
		self.assertEqual('Woody Woodpecker', animal_by_id[woody.pk]['name'])
		self.assertEqual(emmen.pk, animal_by_id[woody.pk]['zoo'])
		self.assertEqual(gaia.pk, animal_by_id[roadrunner.pk]['zoo'])
		self.assertEqual(gaia.pk, animal_by_id[coyote.pk]['zoo'])


	def test_get_collection_with_one_to_one(self):
		scrooge = Animal(name='Scrooge McDuck')
		scrooge.full_clean()
		scrooge.save()

		frock = Costume(description="Gentleman's frock coat", animal=scrooge)
		frock.full_clean()
		frock.save()

		donald = Animal(name='Donald Duck')
		donald.full_clean()
		donald.save()

		sailor = Costume(description='Weird sailor costume', animal=donald)
		sailor.full_clean()
		sailor.save()

		# This animal goes naked
		pluto = Animal(name='Pluto')
		pluto.full_clean()
		pluto.save()


		# Quick check that one to one relations are also excluded unless we ask for them
		response = self.client.get('/animal/', data={'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		self.assertIsNone(response.get('with_mapping'))
		self.assertIsNone(response.get('with'))


		response = self.client.get('/animal/', data={'order_by': 'name', 'with': 'costume'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(3, len(result['data']))
		self.assertEqual(2, len(result['with']['costume']))
		# TODO: Add test for relations with different name than models
		self.assertEqual('costume', result['with_mapping']['costume'])

		self.assertEqual(sailor.pk, result['data'][0]['costume'])
		self.assertIsNone(result['data'][1]['costume'])
		self.assertEqual(frock.pk, result['data'][2]['costume'])
		costume_by_id = {costume['id']: costume for costume in result['with']['costume']}
		self.assertEqual('Weird sailor costume', costume_by_id[sailor.pk]['description'])
		self.assertEqual("Gentleman's frock coat", costume_by_id[frock.pk]['description'])
		self.assertEqual(scrooge.pk, costume_by_id[frock.pk]['animal'])
		self.assertEqual(donald.pk, costume_by_id[sailor.pk]['animal'])

	def test_get_model_with_relation_without_id(self):
		gaia = Zoo(name='GaiaZOO')
		gaia.full_clean()
		gaia.save()

		fabbby = Caretaker(name='fabbby')
		fabbby.full_clean()
		fabbby.save()

		door = Gate(zoo=gaia, keeper=fabbby)
		door.full_clean()
		door.save()

		response = self.client.get('/zoo/{}/'.format(gaia.id), data={'with': 'gate.keeper'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual('GaiaZOO', result['data']['name'])
		self.assertEqual(1, len(result['with']['gate']))
		self.assertEqual(1, len(result['with']['caretaker']))
		self.assertEqual('gate', result['with_mapping']['gate'])
		self.assertEqual('caretaker', result['with_mapping']['gate.keeper'])
		self.assertEqual('fabbby', result['with']['caretaker'][0]['name'])

	def test_get_collection_filtering_following_nested_references(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.full_clean()
		emmen.save()

		gaia = Zoo(name='GaiaZOO')
		gaia.full_clean()
		gaia.save()

		scrooge = Animal(name='Scrooge McDuck', zoo=gaia)
		scrooge.full_clean()
		scrooge.save()

		frock = Costume(description="Gentleman's frock coat", animal=scrooge)
		frock.full_clean()
		frock.save()

		donald = Animal(name='Donald Duck', zoo=emmen)
		donald.full_clean()
		donald.save()

		sailor = Costume(description='Weird sailor costume', animal=donald)
		sailor.full_clean()
		sailor.save()


		response = self.client.get('/costume/', data={'order_by': 'animal.zoo.name'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

		self.assertEqual(frock.pk, result['data'][0]['id']) # G
		self.assertEqual(sailor.pk, result['data'][1]['id']) # W

		# Another regression due to the same bug we test
		# above: the with would also break.
		response = self.client.get('/costume/', data={'order_by': 'animal.zoo.name', 'with': 'animal.zoo'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual(frock.pk, result['data'][0]['id']) # G
		self.assertEqual(sailor.pk, result['data'][1]['id']) # W
		animal_by_id = {animal['id']: animal for animal in result['with']['animal']}
		self.assertEqual('Scrooge McDuck', animal_by_id[frock.pk]['name'])
		self.assertEqual("Donald Duck", animal_by_id[sailor.pk]['name'])

		# Another regression due to the same bug we test
		# above: the related filter would also break.
		response = self.client.get('/costume/', data={'order_by': 'animal.zoo.name', '.animal.zoo.name': 'GaiaZOO'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(frock.pk, result['data'][0]['id'])


	def test_post_new_model_with_foreign_key_value(self):
		artis = Zoo(name='Artis')
		artis.full_clean()
		artis.save()

		model_data = {
			'name': 'Scooby Doo',
			'zoo': artis.pk,
		}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertIsNotNone(returned_data.get('id'))
		self.assertEqual('Scooby Doo', returned_data.get('name'))
		self.assertEqual(artis.pk, returned_data.get('zoo'))

		scooby = Animal.objects.get(id=returned_data.get('id'))
		self.assertEqual(artis, scooby.zoo) # haha, Scooby Zoo!
		self.assertEqual('Scooby Doo', scooby.name)


	def test_post_new_model_with_one_to_one_value(self):
		donald = Animal(name='Donald Duck')
		donald.full_clean()
		donald.save()

		model_data = {
			'description': 'Weird sailor costume',
			'animal': donald.pk,
		}
		response = self.client.post('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertIsNotNone(returned_data.get('id'))
		self.assertEqual('Weird sailor costume', returned_data.get('description'))
		self.assertEqual(donald.pk, returned_data.get('animal'))

		sailor = Costume.objects.get(id=returned_data.get('id'))
		self.assertEqual(donald, sailor.animal)
		self.assertEqual('Weird sailor costume', sailor.description)


	def test_post_new_model_with_reverse_foreign_key_multi_value(self):
		scooby = Animal(name='Scooby Doo')
		scooby.full_clean()
		scooby.save()

		scrappy = Animal(name='Scrappy Doo')
		scrappy.full_clean()
		scrappy.save()

		woody = Animal(name='Woody Woodpecker')
		woody.full_clean()
		woody.save()

		model_data = {
			'name': 'Artis',
			'animals': [scooby.pk, scrappy.pk],
		}
		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		self.assertIsNotNone(returned_data.get('id'))
		self.assertEqual('Artis', returned_data.get('name'))
		self.assertSetEqual(set([scooby.id, scrappy.id]),
				    set(returned_data.get('animals')))

		artis = Zoo.objects.get(id=returned_data.get('id'))
		self.assertEqual('Artis', artis.name)
		self.assertSetEqual(set([scooby.id, scrappy.id]), set([a.id for a in artis.animals.all()]))


	def test_post_put_respect_with_clause(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.full_clean()
		emmen.save()

		model_data = {
			'name': 'Scooby Doo',
			'zoo': emmen.pk,
		}
		response = self.client.post(
			'/animal/?with=zoo',
			data=json.dumps(model_data),
			content_type='application/json'
		)

		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual(1, len(result['_meta']['with']['zoo']))

		response = self.client.put(
			'/animal/{}/?with=zoo'.format(result['id']),
			data=json.dumps(model_data),
			content_type='application/json'
		)

		self.assertEqual(response.status_code, 200)
		result = jsonloads(response.content)
		self.assertEqual(1, len(result['_meta']['with']['zoo']))
