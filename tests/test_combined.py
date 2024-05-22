import json

from django.test import TestCase
from django.contrib.auth import get_user_model

from .testapp.models import Zoo, Animal


class CombinedTest(TestCase):
	def setUp(self):
		super().setUp()

		User = get_user_model()
		user = User(username='testuser', is_active=True, is_superuser=True)
		user.set_password('test')
		user.save()

		self.assertTrue(self.client.login(username='testuser', password='test'))

	def test_combined_non_existing_name(self):
		res = self.client.get('/combined/doesnotexist/')
		self.assertEqual(res.status_code, 418)
		data = json.loads(res.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'Unknown model: {doesnotexist}')

	def test_combined_wrong_method(self):
		res = self.client.post('/combined/zoo/animal/')
		self.assertEqual(res.status_code, 405)
		data = json.loads(res.content)
		self.assertEqual(data['code'], 'MethodNotAllowed')
		self.assertEqual(data['allowed_methods'], ['GET'])

	def test_combined_no_data(self):
		res = self.client.get('/combined/zoo/animal/')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		self.assertEqual(data['data'], [])

	def test_combined(self):
		zoo1 = Zoo.objects.create(name='Apenheul')
		zoo2 = Zoo.objects.create(name='Emmen')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe')

		res = self.client.get('/combined/zoo/animal/')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		objs_by_id = {obj['id']: obj for obj in data['data']}

		self.assertEqual(set(objs_by_id), {
			zoo1.id * 2,
			zoo2.id * 2,
			animal1.id * 2 + 1,
			animal2.id * 2 + 1,
		})

		zoo1_data = objs_by_id[zoo1.id * 2]
		self.assertEqual(set(zoo1_data), {'id', 'zoo', 'animal'})
		self.assertEqual(zoo1_data['zoo'], zoo1.id)
		self.assertIsNone(zoo1_data['animal'])

		zoo2_data = objs_by_id[zoo2.id * 2]
		self.assertEqual(set(zoo2_data), {'id', 'zoo', 'animal'})
		self.assertEqual(zoo2_data['zoo'], zoo2.id)
		self.assertIsNone(zoo2_data['animal'])

		animal1_data = objs_by_id[animal1.id * 2 + 1]
		self.assertEqual(set(animal1_data), {'id', 'zoo', 'animal'})
		self.assertIsNone(animal1_data['zoo'])
		self.assertEqual(animal1_data['animal'], animal1.id)

		animal2_data = objs_by_id[animal2.id * 2 + 1]
		self.assertEqual(set(animal2_data), {'id', 'zoo', 'animal'})
		self.assertIsNone(animal2_data['zoo'])
		self.assertEqual(animal2_data['animal'], animal2.id)

	def test_combined_withs(self):
		zoo1 = Zoo.objects.create(name='Apenheul')
		zoo2 = Zoo.objects.create(name='Emmen')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe')

		res = self.client.get('/combined/zoo/animal/?with=zoo,animal.zoo')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)

		self.assertEqual(set(data['with']), {'zoo', 'animal'})
		self.assertEqual(len(data['with']['zoo']), 2)
		self.assertEqual({obj['id'] for obj in data['with']['zoo']}, {zoo1.id, zoo2.id})
		self.assertEqual(len(data['with']['animal']), 2)
		self.assertEqual({obj['id'] for obj in data['with']['animal']}, {animal1.id, animal2.id})

	def test_combined_filter(self):
		zoo1 = Zoo.objects.create(name='Apenheul')
		zoo2 = Zoo.objects.create(name='Emmen')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe')

		# Note that filtering intentionally only filters data with the model
		# specified in the filter
		res = self.client.get(f'/combined/zoo/animal/?.zoo={zoo1.id}&.animal.zoo={zoo1.id}')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		ids = {obj['id'] for obj in data['data']}
		self.assertEqual(ids, {
			zoo1.id * 2,
			animal1.id * 2 + 1,
		})

	def test_combined_order_by_single_field(self):
		zoo1 = Zoo.objects.create(name='Apenheul', founding_date='1980-01-01')
		zoo2 = Zoo.objects.create(name='Emmen', founding_date='1990-01-01')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito', birth_date='1995-01-01')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe', birth_date='1985-01-01')

		res = self.client.get(f'/combined/zoo/animal/?order_by=name')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		ids = [obj['id'] for obj in data['data']]
		self.assertEqual(ids, [
			zoo1.id * 2,  # Apenheul
			animal1.id * 2 + 1,  # Bokito
			zoo2.id * 2,  # Emmen
			animal2.id * 2 + 1,  # Harambe
		])

	def test_combined_order_by_multi_field(self):
		zoo1 = Zoo.objects.create(name='Apenheul', founding_date='1980-01-01')
		zoo2 = Zoo.objects.create(name='Emmen', founding_date='1990-01-01')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito', birth_date='1995-01-01')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe', birth_date='1985-01-01')

		res = self.client.get(f'/combined/zoo/animal/?order_by=(founding_date,birth_date)')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		ids = [obj['id'] for obj in data['data']]
		self.assertEqual(ids, [
			zoo1.id * 2,  # Apenheul
			animal2.id * 2 + 1,  # Harambe
			zoo2.id * 2,  # Emmen
			animal1.id * 2 + 1,  # Bokito
		])

		res = self.client.get(f'/combined/zoo/animal/?order_by=-(founding_date,birth_date)')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		ids = [obj['id'] for obj in data['data']]
		self.assertEqual(ids, [
			animal1.id * 2 + 1,  # Bokito
			zoo2.id * 2,  # Emmen
			animal2.id * 2 + 1,  # Harambe
			zoo1.id * 2,  # Apenheul
		])

	def test_combined_id_filter(self):
		zoo1 = Zoo.objects.create(name='Apenheul', founding_date='1980-01-01')
		zoo2 = Zoo.objects.create(name='Emmen', founding_date='1990-01-01')
		animal1 = Animal.objects.create(zoo=zoo1, name='Bokito', birth_date='1995-01-01')
		animal2 = Animal.objects.create(zoo=zoo2, name='Harambe', birth_date='1985-01-01')

		res = self.client.get(f'/combined/zoo/animal/?.id:in={zoo1.id * 2},{animal2.id * 2 + 1}')
		self.assertEqual(res.status_code, 200)
		data = json.loads(res.content)
		ids = {obj['id'] for obj in data['data']}
		self.assertEqual(ids, {
			zoo1.id * 2,  # Apenheul
			animal2.id * 2 + 1,  # Harambe
		})
