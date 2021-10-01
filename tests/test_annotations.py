from tests.test_order_by import CustomOrdering
from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads
from .testapp.models import Animal, Caretaker, Zoo, Costume


class AnnotationTestCase(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.caretaker = Caretaker(name='carl')
		self.caretaker.save()

		self.zoo = Zoo(name='Apenheul')
		self.zoo.save()

		self.animal = Animal(name='Harambe', zoo=self.zoo, caretaker=self.caretaker)
		self.animal.save()

	def test_get_data(self):
		res = self.client.get('/caretaker/{}/'.format(self.caretaker.pk))
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(data['data']['animal_count'], 1)

	def test_add_animal(self):
		animal = Animal(name='Bokito', zoo=self.zoo, caretaker=self.caretaker)
		animal.save()

		res = self.client.get('/caretaker/{}/'.format(self.caretaker.pk))
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(data['data']['animal_count'], 2)

	def test_order_by_animal_count(self):
		caretaker_2 = Caretaker(name='caretaker 2')
		caretaker_2.save()
		caretaker_3 = Caretaker(name='caretaker 3')
		caretaker_3.save()

		for i in range(3):
			Animal(
				name='animal 2 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_2,
			).save()
		for i in range(2):
			Animal(
				name='animal 3 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_3,
			).save()

		res = self.client.get('/caretaker/?order_by=-animal_count')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		order = [ct['id'] for ct in data['data']]
		self.assertEqual(order, [caretaker_2.pk, caretaker_3.pk, self.caretaker.pk])
		self.assertEqual(data['data'][0]['best_animal'], 'animal 2 2')

	def test_f_expression(self):
		self.caretaker.ssn = 'blablabla'
		self.caretaker.save()

		res = self.client.get('/caretaker/{}/'.format(self.caretaker.pk))
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(data['data']['bsn'], 'blablabla')

	def test_filter_on_animal_count(self):
		caretaker_2 = Caretaker(name='caretaker 2')
		caretaker_2.save()
		caretaker_3 = Caretaker(name='caretaker 3')
		caretaker_3.save()

		for i in range(3):
			Animal(
				name='animal 2 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_2,
			).save()
		for i in range(2):
			Animal(
				name='animal 3 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_3,
			).save()

		res = self.client.get('/caretaker/?.animal_count=2')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		order = [ct['id'] for ct in data['data']]
		self.assertEqual(order, [caretaker_3.pk])

	def test_filter_on_animal_count_nested(self):
		caretaker_2 = Caretaker(name='caretaker 2')
		caretaker_2.save()
		caretaker_3 = Caretaker(name='caretaker 3')
		caretaker_3.save()

		for i in range(3):
			Animal(
				name='animal 2 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_2,
			).save()
		animal_pks = set()
		for i in range(2):
			animal = Animal(
				name='animal 3 {}'.format(i),
				zoo=self.zoo,
				caretaker=caretaker_3,
			)
			animal.save()
			animal_pks.add(animal.pk)

		res = self.client.get('/animal/?.caretaker.animal_count=2')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		pks = {a['id'] for a in data['data']}
		self.assertEqual(pks, animal_pks)

	def test_context_annotation(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()
		harambe = Animal(zoo=zoo, name='Harambe')
		harambe.save()
		bokito = Animal(zoo=zoo, name='Bokito')
		bokito.save()

		res = self.client.get('/animal/{}/'.format(self.animal.pk))
		self.assertEqual(res.status_code, 200)
		data = jsonloads(res.content)
		self.assertEqual(data['data']['name'], 'Harambe')
		self.assertEqual(data['data']['prefixed_name'], 'Sir Harambe')

		res = self.client.get('/animal/{}/?animal_name_prefix=Lady'.format(self.animal.pk))
		self.assertEqual(res.status_code, 200)
		data = jsonloads(res.content)
		self.assertEqual(data['data']['name'], 'Harambe')
		self.assertEqual(data['data']['prefixed_name'], 'Lady Harambe')

	def test_context_annotation_sorting(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()
		harambe = Animal(zoo=zoo, name='Harambe', age=4)
		harambe.save()
		bokito = Animal(zoo=zoo, name='Bokito', age=3)
		bokito.save()

		with CustomOrdering(Animal, 'age_product'):
			res = self.client.get('/animal/?factor=2')
			self.assertEqual(res.status_code, 200)
			returned_data = jsonloads(res.content)

		data = [x['name'] for x in returned_data['data']]
		self.assertEqual(['Bokito', 'Harambe'], data)

		with CustomOrdering(Animal, 'age_product'):
			# This time the factor is negative, which should give the reverse effect
			res = self.client.get('/animal/?factor=-2')
			self.assertEqual(res.status_code, 200)
			returned_data = jsonloads(res.content)

		data = [x['name'] for x in returned_data['data']]
		self.assertEqual(['Harambe', 'Bokito'], data)

	def test_context_aware_relation_error(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()
		harambe = Animal(zoo=zoo, name='Harambe', age=4)
		harambe.save()
		bokito = Animal(zoo=zoo, name='Bokito', age=3)
		bokito.save()
		harambe_costume = Costume(animal=harambe)
		bokito_costume = Costume(animal=bokito)

		with CustomOrdering(Costume, 'animal.age_product'):
			res = self.client.get('/animal/?factor=2')
			self.assertEqual(res.status_code, 418)

class IncludeAnnotationsTest(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.caretaker = Caretaker(name='carl')
		self.caretaker.save()

		self.zoo = Zoo(name='Apenheul')
		self.zoo.save()

		self.animal = Animal(name='Harambe', zoo=self.zoo, caretaker=self.caretaker)
		self.animal.save()

	def test_include_one_annotation(self):
		res = self.client.get(
			'/caretaker/{}/?include_annotations=animal_count'.format(self.caretaker.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertIn('animal_count', data['data'])
		self.assertNotIn('best_animal', data['data'])
		self.assertNotIn('bsn', data['data'])
		self.assertNotIn('last_present', data['data'])
		self.assertNotIn('scary', data['data'])

	def test_exclude_one_annotation(self):
		res = self.client.get(
			'/caretaker/{}/?include_annotations=*,-animal_count'.format(self.caretaker.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertNotIn('animal_count', data['data'])
		self.assertIn('best_animal', data['data'])
		self.assertIn('bsn', data['data'])
		self.assertIn('last_present', data['data'])
		self.assertNotIn('scary', data['data'])

	def test_include_optional_annotation(self):
		res = self.client.get(
			'/caretaker/{}/?include_annotations=*,scary'.format(self.caretaker.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertIn('animal_count', data['data'])
		self.assertIn('best_animal', data['data'])
		self.assertIn('bsn', data['data'])
		self.assertIn('last_present', data['data'])
		self.assertIn('scary', data['data'])

	def test_include_no_annotations(self):
		res = self.client.get(
			'/caretaker/{}/?include_annotations='.format(self.caretaker.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertNotIn('animal_count', data['data'])
		self.assertNotIn('best_animal', data['data'])
		self.assertNotIn('bsn', data['data'])
		self.assertNotIn('last_present', data['data'])
		self.assertNotIn('scary', data['data'])

	def test_relation_include_one_annotation(self):
		res = self.client.get(
			'/animal/{}/?with=caretaker&include_annotations=caretaker(animal_count)'.format(self.animal.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertIn('animal_count', data['with']['caretaker'][0])
		self.assertNotIn('best_animal', data['with']['caretaker'][0])
		self.assertNotIn('bsn', data['with']['caretaker'][0])
		self.assertNotIn('last_present', data['with']['caretaker'][0])
		self.assertNotIn('scary', data['with']['caretaker'][0])

	def test_relation_exclude_one_annotation(self):
		res = self.client.get(
			'/animal/{}/?with=caretaker&include_annotations=caretaker(*,-animal_count)'.format(self.animal.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertNotIn('animal_count', data['with']['caretaker'][0])
		self.assertIn('best_animal', data['with']['caretaker'][0])
		self.assertIn('bsn', data['with']['caretaker'][0])
		self.assertIn('last_present', data['with']['caretaker'][0])
		self.assertNotIn('scary', data['with']['caretaker'][0])

	def test_relation_include_optional_annotation(self):
		res = self.client.get(
			'/animal/{}/?with=caretaker&include_annotations=caretaker(*,scary)'.format(self.animal.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertIn('animal_count', data['with']['caretaker'][0])
		self.assertIn('best_animal', data['with']['caretaker'][0])
		self.assertIn('bsn', data['with']['caretaker'][0])
		self.assertIn('last_present', data['with']['caretaker'][0])
		self.assertIn('scary', data['with']['caretaker'][0])

	def test_relation_include_no_annotations(self):
		res = self.client.get(
			'/animal/{}/?with=caretaker&include_annotations=caretaker()'.format(self.animal.pk)
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertNotIn('animal_count', data['with']['caretaker'][0])
		self.assertNotIn('best_animal', data['with']['caretaker'][0])
		self.assertNotIn('bsn', data['with']['caretaker'][0])
		self.assertNotIn('last_present', data['with']['caretaker'][0])
		self.assertNotIn('scary', data['with']['caretaker'][0])

	def test_filter_on_relation_with_include_annotations(self):
		res = self.client.get(
			'/caretaker/?include_annotations=scary&.animals.name=Harambe'
		)
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)
		self.assertEqual(len(data['data']), 1)
		self.assertNotIn('animal_count', data['data'][0])
		self.assertNotIn('best_animal', data['data'][0])
		self.assertNotIn('bsn', data['data'][0])
		self.assertNotIn('last_present', data['data'][0])
		self.assertIn('scary', data['data'][0])
