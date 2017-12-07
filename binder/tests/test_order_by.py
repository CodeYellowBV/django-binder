from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

# from .compare import assert_json, MAYBE, ANY, EXTRA
from .testapp.models import Animal, Costume, Zoo



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

		Animal(id=1, name='a1').save()
		Animal(id=2, name='a2').save()
		Animal(id=3, name='a3').save()
		Animal(id=4, name='a4').save()

		Costume(animal_id=2, nickname='Foo', description='Bar').save()
		Costume(animal_id=3, nickname='Bar', description='Bar').save()
		Costume(animal_id=1, nickname='Foo', description='Foo').save()
		Costume(animal_id=4, nickname='Bar', description='Foo').save()



	# Order by model default (id)
	def test_order_default(self):
		response = self.client.get('/costume/')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [1, 2, 3, 4])



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
		self.assertEqual(data, [3, 4, 2, 1])



	# Order by description, -nickname
	def test_order_description_revnickname(self):
		response = self.client.get('/costume/?order_by=description,-nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [2, 3, 1, 4])



	# Order by nickname, model default (id)
	def test_order_nickname_default(self):
		response = self.client.get('/costume/?order_by=nickname')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [3, 4, 1, 2])



	# Order by -description, model default (id)
	def test_order_revdescription_default(self):
		response = self.client.get('/costume/?order_by=-description')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [1, 4, 2, 3])



	# Order by nickname, custom model default (-id)
	def test_order_nickname_customdefault(self):
		with CustomOrdering(Costume, '-animal_id'):
			response = self.client.get('/costume/?order_by=nickname')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 3, 2, 1])



	# Order by -description, custom model default (-id)
	def test_order_revdescription_customdefault(self):
		with CustomOrdering(Costume, '-animal_id'):
			response = self.client.get('/costume/?order_by=-description')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 1, 3, 2])



	# Order by -description, custom model default on related model (-animal.name)
	# This would break due to Django vs Binder related object syntax mismatch and
	# missing views for non-Binder relations.
	def test_order_revdescription_customdefault_related_model_name(self):
		with CustomOrdering(Costume, 'animal__name'):
			response = self.client.get('/costume/?order_by=-description')
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [1, 4, 2, 3])



	# Order by nickname, -id (overriding default model order)
	def test_order_nickname(self):
		response = self.client.get('/costume/?order_by=nickname,-id')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		data = [x['id'] for x in returned_data['data']]
		self.assertEqual(data, [4, 3, 2, 1])



	def test_order_related_ids(self):
		z = Zoo(name='hoi')
		z.save()

		a9 = Animal.objects.create(zoo_id=1, name='a9').id
		a0 = Animal.objects.create(zoo_id=1, name='a0').id
		a2 = Animal.objects.create(zoo_id=1, name='a2').id
		a6 = Animal.objects.create(zoo_id=1, name='a6').id
		a7 = Animal.objects.create(zoo_id=1, name='a7').id
		a5 = Animal.objects.create(zoo_id=1, name='a5').id
		a4 = Animal.objects.create(zoo_id=1, name='a4').id
		a3 = Animal.objects.create(zoo_id=1, name='a3').id
		a8 = Animal.objects.create(zoo_id=1, name='a8').id
		a1 = Animal.objects.create(zoo_id=1, name='a1').id

		with CustomOrdering(Animal, 'name'):
			response = self.client.get('/zoo/{}/'.format(z.id))
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		self.assertEqual(returned_data['data']['animals'], [a0, a1, a2, a3, a4, a5, a6, a7, a8, a9])

		with CustomOrdering(Animal, '-name'):
			response = self.client.get('/zoo/{}/'.format(z.id))
			self.assertEqual(response.status_code, 200)
			returned_data = jsonloads(response.content)

		self.assertEqual(returned_data['data']['animals'], [a9, a8, a7, a6, a5, a4, a3, a2, a1, a0])
