import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from .testapp.models import Zoo


class InheritanceTest(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_add_lion_to_zoo(self):
		zoo = Zoo(name='Artis')
		zoo.save()

		response = self.client.put(
			'/zoo/',
			content_type='application/json',
			data=json.dumps({
				'data': [
					{
						'id': zoo.pk,
						'animals': [-1, -2],
					},
				],
				'with': {
					'lion': [
						{
							'id': -1,
							'name': 'Mufasa',
							'mane_magnificence': 10,
						},
						{
							'id': -2,
							'name': 'Scar',
							'mane_magnificence': 4,
						},
					],
				},
			}),
		)
		self.assertEqual(response.status_code, 200)

		zoo.refresh_from_db()
		animals = list(zoo.animals.all())
		self.assertEqual(len(animals), 2)
		mane_magnificence_map = {
			animal.name: animal.lion.mane_magnificence
			for animal in animals
		}
		self.assertEqual(mane_magnificence_map, {
			'Mufasa': 10,
			'Scar': 4,
		})

	def test_create_lion_with_animal(self):
		response = self.client.put(
			'/animal/',
			content_type='application/json',
			data=json.dumps({
				'data': [{
					'id': -1,
					'name': 'OVERRIDE THIS SHIET',
					'lion': -2,
				}],
				'with': {'lion': [{
					'id': -2,
					'name': 'Mufasa',
					'mane_magnificence': 10,
				}]},
			}),
		)

		self.assertEqual(response.status_code, 200)
		res_data = json.loads(response.content.decode())
		lion_id = res_data['idmap']['lion'][0][1]
		self.assertEqual(res_data, {
			'idmap': {
				'animal': [[-1, lion_id]],
				'lion': [[-2, lion_id]],
			},
		})

	def test_create_lion_with_animal_and_zoo(self):
		response = self.client.put(
			'/animal/',
			content_type='application/json',
			data=json.dumps({
				'data': [{
					'id': -1,
					'name': 'OVERRIDE THIS SHIET',
					'lion': -2,
				}],
				'with': {
					'lion': [{
						'id': -2,
						'name': 'Mufasa',
						'mane_magnificence': 10,
					}],
					'zoo': [{
						'id': -3,
						'name': 'Artis',
						'animals': [-1],
					}],
				},
			}),
		)

		self.assertEqual(response.status_code, 200)
		res_data = json.loads(response.content.decode())
		zoo_id = res_data['idmap']['zoo'][0][1]
		animal_id = res_data['idmap']['animal'][0][1]

		zoo = Zoo.objects.get(pk=zoo_id)
		zoo_animal_ids = [animal.id for animal in zoo.animals.all()]
		self.assertEqual(zoo_animal_ids, [animal_id])
