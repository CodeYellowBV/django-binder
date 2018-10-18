from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads
from .testapp.models import Animal, ContactPerson, Zoo, Caretaker
from .testapp.views import AnimalView

class CustomDefaultLimit:
	def __init__(self, cls, limit):
		self.cls = cls
		self.new_limit = limit

	def __enter__(self):
		self.old_limit = self.cls.limit_default
		self.cls.limit_default = self.new_limit

	def __exit__(self, *args, **kwargs):
		self.cls.limit_default = self.old_limit


class CustomMaxLimit:
	def __init__(self, cls, limit):
		self.cls = cls
		self.new_limit = limit

	def __enter__(self):
		self.old_limit = self.cls.limit_max
		self.cls.limit_max = self.new_limit

	def __exit__(self, *args, **kwargs):
		self.cls.limit_max = self.old_limit


class TestPagination(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.gaia = Zoo(name='GaiaZOO') # 3
		self.gaia.save()

		self.wildlands = Zoo(name='Wildlands Adventure Zoo Emmen') # 4
		self.wildlands.full_clean()
		self.wildlands.save()

		self.artis = Zoo(name='Artis') # 1
		self.artis.full_clean()
		self.artis.save()

		self.harderwijk = Zoo(name='Dolfinarium Harderwijk') # 2
		self.harderwijk.full_clean()
		self.harderwijk.save()

		self.donald = Animal(name='Donald Duck', zoo=self.wildlands) # 1
		self.donald.save()
		self.mickey = Animal(name='Mickey Mouse', zoo=self.gaia) # 2
		self.mickey.save()
		self.pluto = Animal(name='Pluto', zoo=self.artis) # 4
		self.pluto.save()
		self.minnie = Animal(name='Minnie Mouse', zoo=self.gaia) # 3
		self.minnie.save()
		self.scrooge = Animal(name='Scrooge McDuck', zoo=self.artis) # 5
		self.scrooge.save()

		self.director = ContactPerson(name='Director') # 2
		self.director.save()

		self.gaia.contacts.add(self.director)
		self.wildlands.contacts.add(self.director)

		self.janitor = ContactPerson(name='Janitor') # 3
		self.janitor.save()

		self.gaia.contacts.add(self.janitor)

		self.cleaning_lady = ContactPerson(name='Cleaning lady') # 1
		self.cleaning_lady.save()

		self.gaia.contacts.add(self.cleaning_lady)

		self.caretaker1 = Caretaker(name='Caretaker 1') # 1 (Ran out of inspiration)
		self.caretaker1.save()

		self.caretaker2 = Caretaker(name='Caretaker 2') # 2
		self.caretaker2.save()

		self.caretaker1.animals.add(self.donald)
		self.caretaker1.animals.add(self.mickey)
		self.caretaker1.animals.add(self.scrooge)

		self.caretaker2.animals.add(self.pluto)
		self.caretaker2.animals.add(self.minnie)


	def test_limit_parsing(self):
		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 'haha'})
		self.assertEqual(response.status_code, 418)

		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': '-1'})
		self.assertEqual(response.status_code, 418)

		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': '0'})
		self.assertEqual(response.status_code, 200)

		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 'none'})
		self.assertEqual(response.status_code, 200)

		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 'nope'})
		self.assertEqual(response.status_code, 418)

		response = self.client.get('/animal/', data={'order_by': 'name', 'limit': ''})
		self.assertEqual(response.status_code, 418)


	def test_basic_limit_offset(self):
		response = self.client.get('/animal/', data={'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(5, data['meta']['total_records'])
		self.assertEqual(5, len(data['data']))

		response = self.client.get('/animal/', data={'limit': 1, 'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(5, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.donald.id, data['data'][0]['id'])


		response = self.client.get('/animal/', data={'limit': 1, 'offset': 1, 'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(5, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.mickey.id, data['data'][0]['id'])


		response = self.client.get('/animal/', data={'limit': 2, 'offset': 1, 'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(5, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.mickey.id, data['data'][0]['id'])
		self.assertEqual(self.minnie.id, data['data'][1]['id'])


		response = self.client.get('/animal/', data={'limit': 2, 'offset': 100, 'order_by': 'name'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(5, data['meta']['total_records'])
		self.assertEqual(0, len(data['data']))


	def test_basic_limit_offset_honors_custom_default(self):
		with CustomDefaultLimit(AnimalView, 2):
			response = self.client.get('/animal/', data={'order_by': 'name'})
			self.assertEqual(response.status_code, 200)
			data = jsonloads(response.content)

			self.assertEqual(5, data['meta']['total_records'])
			self.assertEqual(2, len(data['data']))
			self.assertEqual(self.donald.id, data['data'][0]['id'])
			self.assertEqual(self.mickey.id, data['data'][1]['id'])


			response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 'none'})
			self.assertEqual(response.status_code, 200)
			data = jsonloads(response.content)

			self.assertEqual(5, data['meta']['total_records'])
			self.assertEqual(5, len(data['data']))


	def test_basic_limit_offset_honors_custom_maximum(self):
		with CustomMaxLimit(AnimalView, 3):
			# This is inconsistent with the default value, and Binder fails
			response = self.client.get('/animal/', data={'order_by': 'name'})
			self.assertEqual(response.status_code, 418)
			data = jsonloads(response.content)

			response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 2})
			self.assertEqual(response.status_code, 200)
			data = jsonloads(response.content)

			self.assertEqual(5, data['meta']['total_records'])
			self.assertEqual(2, len(data['data']))
			self.assertEqual(self.donald.id, data['data'][0]['id'])
			self.assertEqual(self.mickey.id, data['data'][1]['id'])


			with CustomDefaultLimit(AnimalView, 2):
				response = self.client.get('/animal/', data={'order_by': 'name'})
				self.assertEqual(response.status_code, 200)
				data = jsonloads(response.content)

				self.assertEqual(5, data['meta']['total_records'])
				self.assertEqual(2, len(data['data']))
				self.assertEqual(self.donald.id, data['data'][0]['id'])
				self.assertEqual(self.mickey.id, data['data'][1]['id'])


				response = self.client.get('/animal/', data={'order_by': 'name', 'offset': 3})
				self.assertEqual(response.status_code, 200)
				data = jsonloads(response.content)

				self.assertEqual(5, data['meta']['total_records'])
				self.assertEqual(2, len(data['data']))
				self.assertEqual(self.pluto.id, data['data'][0]['id'])
				self.assertEqual(self.scrooge.id, data['data'][1]['id'])

				response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 'none'})
				self.assertEqual(response.status_code, 418)

				response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 4})
				self.assertEqual(response.status_code, 418)


				response = self.client.get('/animal/', data={'order_by': 'name', 'limit': 3})
				self.assertEqual(response.status_code, 200)


	def test_limit_offset_using_with(self):
		response = self.client.get('/zoo/', data={'order_by': 'name', 'limit': 2, 'with': 'animals'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(4, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.artis.id, data['data'][0]['id'])
		self.assertEqual(self.harderwijk.id, data['data'][1]['id'])

		self.assertEqual('animal', data['with_mapping']['animals'])
		self.assertEqual('zoo', data['with_related_name_mapping']['animals'])

		self.assertEqual({self.pluto.id, self.scrooge.id}, set(data['data'][0]['animals']))
		self.assertEqual([], data['data'][1]['animals'])


		response = self.client.get('/zoo/', data={'order_by': 'name', 'limit': 2, 'offset': 1, 'with': 'animals'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(4, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.harderwijk.id, data['data'][0]['id'])
		self.assertEqual(self.gaia.id, data['data'][1]['id'])

		self.assertEqual('animal', data['with_mapping']['animals'])
		self.assertEqual('zoo', data['with_related_name_mapping']['animals'])

		self.assertEqual([], data['data'][0]['animals'])
		self.assertEqual({self.mickey.id, self.minnie.id}, set(data['data'][1]['animals']))


	def test_limit_offset_filtering(self):
		response = self.client.get('/zoo/', data={'order_by': 'name', 'limit': 2, '.name:not': 'GaiaZOO'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(3, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.artis.id, data['data'][0]['id'])
		self.assertEqual(self.harderwijk.id, data['data'][1]['id'])

		response = self.client.get('/zoo/', data={'order_by': 'name', 'limit': 2, 'offset': 1, '.name:not': 'GaiaZOO'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(3, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.harderwijk.id, data['data'][0]['id'])
		self.assertEqual(self.wildlands.id, data['data'][1]['id'])


	def test_limit_offset_related_filtering(self):
		response = self.client.get('/contact_person/', data={'order_by': 'name', 'limit': 2, '.zoos.name': 'Wildlands Adventure Zoo Emmen'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(1, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.director.id, data['data'][0]['id'])


		response = self.client.get('/contact_person/', data={'order_by': 'name', 'limit': 2, 'offset': 1, '.zoos.name': 'Wildlands Adventure Zoo Emmen'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(1, data['meta']['total_records'])
		self.assertEqual(0, len(data['data']))


		response = self.client.get('/contact_person/', data={'order_by': 'name', 'limit': 2, 'offset': 1, '.zoos.name': 'GaiaZOO'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(3, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.director.id, data['data'][0]['id'])
		self.assertEqual(self.janitor.id, data['data'][1]['id'])


		# Same set, but deeper filtering
		response = self.client.get('/contact_person/', data={'order_by': 'name', 'limit': 2, 'offset': 1, '.zoos.animals.name': 'Mickey Mouse'})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(3, data['meta']['total_records'])
		self.assertEqual(2, len(data['data']))
		self.assertEqual(self.director.id, data['data'][0]['id'])
		self.assertEqual(self.janitor.id, data['data'][1]['id'])


	def test_limit_offset_filtering_on_annotations(self):
		response = self.client.get('/caretaker/', data={'order_by': 'name', 'limit': 1, 'offset': 0, '.animal_count:gt': 1})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(2, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.caretaker1.id, data['data'][0]['id'])


		response = self.client.get('/caretaker/', data={'order_by': 'name', 'limit': 1, 'offset': 1, '.animal_count:gt': 1})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(2, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.caretaker2.id, data['data'][0]['id'])


		response = self.client.get('/caretaker/', data={'order_by': 'name', 'limit': 1, 'offset': 0, '.animal_count:gt': 2})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		self.assertEqual(1, data['meta']['total_records'])
		self.assertEqual(1, len(data['data']))
		self.assertEqual(self.caretaker1.id, data['data'][0]['id'])
