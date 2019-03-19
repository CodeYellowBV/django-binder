from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads
from .testapp.models import Animal, Caretaker, Zoo


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
