from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, EXTRA
from .testapp.models import Zoo, Animal, ContactPerson



class TestFilterManyRels(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		ContactPerson(id=1, name='contact1').save()
		z = Zoo(id=1, name='zoo')
		z.save()
		z.contacts.set([1])
		Animal(id=1, name='animal', zoo_id=1).save()
		Animal(id=2, name='animal2', zoo_id=1).save()



	def test_filter_fk_forward(self):
		response = self.client.get('/animal/?.zoo=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'zoo': 1,
					EXTRA(): None,  # Other fields are dontcare
				},
				{
					'id': 2,
					'zoo': 1,
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_fk_backward(self):
		response = self.client.get('/zoo/?.animals=1&with=animals')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'animals': [1, 2],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_fk_backward_distinct(self):
		response = self.client.get('/zoo/?.animals:in=1,2&with=animals')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'animals': [1, 2],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})



	def test_filter_m2m_forward(self):
		response = self.client.get('/zoo/?.contacts=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'contacts': [1],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})


	# Tricky special case: Two references to the same model, one of
	# which has m2m relations, the other does not.  This is a
	# regression test.  Annoyingly, it would sometimes succeed and
	# sometimes fail.
	def test_m2m_with_multiple_relations(self):
		expectation = {
			'data': {
				'id': 1,
				'name': 'animal',
				'zoo': 1,
				'zoo_of_birth': None,
				EXTRA(): None,  # Other fields are dontcare
			},
			'with': {
				'zoo': [
					{
						'id': 1,
						'contacts': [1],
						EXTRA(): None,
					},
				],
				'contact_person': [
					{
						'id': 1,
						EXTRA(): None,
					}
				]
			},
			EXTRA(): None,  # Debug, meta, etc
		}

		response = self.client.get('/animal/1/?with=zoo_of_birth.contacts,zoo.contacts')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		assert_json(returned_data, expectation)

		# Different order of with should have no effect
		response = self.client.get('/animal/1/?with=zoo.contacts,zoo_of_birth.contacts')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		assert_json(returned_data, expectation)


		# Now ensure we don't put both contact person lists on the same pile
		ContactPerson(id=2, name='contact2').save()
		z2 = Zoo(id=2, name='zoo2')
		z2.save()
		z2.contacts.set([2])
		animal = Animal.objects.get(pk=1)
		animal.zoo_of_birth = z2
		animal.save()

		expectation = {
			'data': {
				'id': 1,
				'name': 'animal',
				'zoo': 1,
				'zoo_of_birth': 2,
				EXTRA(): None,  # Other fields are dontcare
			},
			'with': {
				'zoo': [
					{
						'id': 1,
						'contacts': [1],
						EXTRA(): None,
					},
					{
						'id': 2,
						'contacts': [2],
						EXTRA(): None,
					},
				],
				'contact_person': [
					{
						'id': 1,
						EXTRA(): None,
					},
					{
						'id': 2,
						EXTRA(): None,
					},
				]
			},
			EXTRA(): None,  # Debug, meta, etc
		}

		response = self.client.get('/animal/1/?with=zoo_of_birth.contacts,zoo.contacts')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		assert_json(returned_data, expectation)

		# Different order of with should have no effect
		response = self.client.get('/animal/1/?with=zoo.contacts,zoo_of_birth.contacts')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		assert_json(returned_data, expectation)


	def test_filter_m2m_backward(self):
		response = self.client.get('/contact_person/?.zoos=1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'zoos': [1],
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})
