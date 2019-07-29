import unittest

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

# from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Animal, Costume, Zoo, Caretaker
import os



class CustomOrdering:
	def __init__(self, cls, order):
		self.cls = cls
		self.order = order

	def __enter__(self):
		self.old = self.cls._meta.ordering[0]
		self.cls._meta.ordering[0] = self.order

	def __exit__(self, *args, **kwargs):
		self.cls._meta.ordering[0] = self.old



class TestOrderBy(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.a1 = Animal(name='a1')
		self.a1.save()
		self.a2 = Animal(name='a2')
		self.a2.save()
		self.a3 = Animal(name='a3')
		self.a3.save()
		self.a4 = Animal(name='a4')
		self.a4.save()

		self.c1 = Costume(animal_id=self.a2.id, nickname='Foo', description='Bar')
		self.c1.save()
		self.c2 = Costume(animal_id=self.a3.id, nickname='Bar', description='Bar')
		self.c2.save()
		self.c3 = Costume(animal_id=self.a1.id, nickname='Foo', description='Foo')
		self.c3.save()
		self.c4 = Costume(animal_id=self.a4.id, nickname='Bar', description='Foo')
		self.c4.save()



	# Order by model default (id)
	def test_order_default(self):
		response = self.client.get('/costume/')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a1.pk, self.a2.pk, self.a3.pk, self.a4.pk])



	# Order by custom model default (nickname)
	def test_order_customdefault(self):
		with CustomOrdering(Costume, 'nickname'):
			response = self.client.get('/costume/')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		# Test for nickname, because id sorting is undefined at this point
		data = [x['nickname'] for x in returned_data['data']]
		self.assertEqual(data, ['Bar', 'Bar', 'Foo', 'Foo'])



	# Order by nickname, description
	def test_order_nickname_description(self):
		response = self.client.get('/costume/?order_by=nickname,description')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a3.pk, self.a4.pk, self.a2.pk, self.a1.pk])



	# Order by description, -nickname
	def test_order_description_revnickname(self):
		response = self.client.get('/costume/?order_by=description,-nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a2.pk, self.a3.pk, self.a1.pk, self.a4.pk])



	# Order by nickname, model default (id)
	def test_order_nickname_default(self):
		response = self.client.get('/costume/?order_by=nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a3.pk, self.a4.pk, self.a1.pk, self.a2.pk])



	# Order by -description, model default (id)
	def test_order_revdescription_default(self):
		response = self.client.get('/costume/?order_by=-description')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a1.pk, self.a4.pk, self.a2.pk, self.a3.pk])



	# Order by nickname, custom model default (-id)
	def test_order_nickname_customdefault(self):
		with CustomOrdering(Costume, '-animal_id'):
			response = self.client.get('/costume/?order_by=nickname')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a4.pk, self.a3.pk, self.a2.pk, self.a1.pk])



	# Order by -description, custom model default (-id)
	def test_order_revdescription_customdefault(self):
		with CustomOrdering(Costume, '-animal_id'):
			response = self.client.get('/costume/?order_by=-description')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a4.pk, self.a1.pk, self.a3.pk, self.a2.pk])



	# Order by -description, custom model default on related model (-animal.name)
	# This would break due to Django vs Binder related object syntax mismatch and
	# missing views for non-Binder relations.
	def test_order_revdescription_customdefault_related_model_name(self):
		with CustomOrdering(Costume, 'animal__name'):
			response = self.client.get('/costume/?order_by=-description')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a1.pk, self.a4.pk, self.a2.pk, self.a3.pk])



	# Order by nickname, -id (overriding default model order)
	def test_order_nickname(self):
		response = self.client.get('/costume/?order_by=nickname,-id')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [self.a4.pk, self.a3.pk, self.a2.pk, self.a1.pk])



	def test_m2m_distinct(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		for i in range(2):
			Animal.objects.create(zoo=zoo, name='a{}'.format(i))

		response = self.client.get('/zoo/?order_by=animals.name'.format(zoo.id))
		self.assertEqual(response.status_code, 200)

		returned_data = jsonloads(response.content)
		pks = [obj['id'] for obj in returned_data['data']]
		self.assertEqual(pks, [zoo.pk])



	def test_order_related_ids(self):
		z = Zoo(name='hoi')
		z.save()

		a9 = Animal.objects.create(zoo_id=z.id, name='a9').id
		a0 = Animal.objects.create(zoo_id=z.id, name='a0').id
		a2 = Animal.objects.create(zoo_id=z.id, name='a2').id
		a6 = Animal.objects.create(zoo_id=z.id, name='a6').id
		a7 = Animal.objects.create(zoo_id=z.id, name='a7').id
		a5 = Animal.objects.create(zoo_id=z.id, name='a5').id
		a4 = Animal.objects.create(zoo_id=z.id, name='a4').id
		a3 = Animal.objects.create(zoo_id=z.id, name='a3').id
		a8 = Animal.objects.create(zoo_id=z.id, name='a8').id
		a1 = Animal.objects.create(zoo_id=z.id, name='a1').id

		with CustomOrdering(Animal, 'name'):
			response = self.client.get('/zoo/{}/?with=animals'.format(z.id))
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		self.assertEqual(returned_data['data']['animals'], [a0, a1, a2, a3, a4, a5, a6, a7, a8, a9])

		with CustomOrdering(Animal, '-name'):
			response = self.client.get('/zoo/{}/?with=animals'.format(z.id))
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		self.assertEqual(returned_data['data']['animals'], [a9, a8, a7, a6, a5, a4, a3, a2, a1, a0])

class TestOrderByNullsLastOnAnnotation(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.c1 = Caretaker(name='c1')
		self.c2 = Caretaker(name='c2')
		self.c3 = Caretaker(name='c3')

		self.c1.save()
		self.c2.save()
		self.c3.save()


		self.a1 = Animal(name='a1', caretaker=self.c1)
		self.a1.save()
		self.a2 = Animal(name='a2', caretaker=self.c2)
		self.a2.save()

	@unittest.skipIf(
		'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (2, 1, 0),
		"Only available from DJango >2.1"
	)
	def test_order_by_nulls_last_on_annotation_aggregate(self):
		# ASC, Nulls last gives c1 (name='a1'), C2 (name='a2'), C3 (nulls)
		response = self.client.get('/caretaker/?order_by=best_animal__nulls_last')
		self.assertEqual(200, response.status_code)

	@unittest.skipIf(
		'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (2, 1, 0),
		"Only available from DJango >2.1"
	)
	def test_order_by_nulls_last_on_annotation_noaggregate(self):
		response = self.client.get('/caretaker/?order_by=bsn__nulls_last')
		self.assertEqual(200, response.status_code)
