from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .compare import assert_json, EXTRA
from .testapp.models import Zoo, ContactPerson

class TestFilterAlternativeFilters(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		ContactPerson(id=1, name='contact1').save()
		ContactPerson(id=2, name='contact2').save()
		ContactPerson(id=3, name='zoo3').save()
		z1 = Zoo(id=1, name='zoo1')
		z1.save()
		z1.contacts.set([1, 2])
		
		z2 = Zoo(id=2, name='zoo2')
		z2.save()
		z2.contacts.set([2])

		z3 = Zoo(id=3, name='zoo3')
		z3.save()
		z3.contacts.set([3])

	def test_filter_alternative_contacts_one_foreign_field(self):
		response = self.client.get('/zoo/?.all_contact_name:icontains=contact1')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
        # only zoo1 contain contacts.name=contact1

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'name': 'zoo1',
					EXTRA(): None,  # Other fields are dontcare
				},
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_filter_alternative_contacts_multiple_foreign_fields(self):
		response = self.client.get('/zoo/?.all_contact_name:icontains=contact2')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
        # both zoos contain contacts.name=contact2

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'name': 'zoo1',
					EXTRA(): None,  # Other fields are dontcare
				},
				{
					'id': 2,
					'name': 'zoo2',
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})
		
	def test_filter_alternative_contacts_regular_field(self):
		response = self.client.get('/zoo/?.all_contact_name:icontains=zoo2')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
        # only zoo 2 contain .name=zoo2

		assert_json(returned_data, {
			'data': [
				{
					'id': 2,
					'name': 'zoo2',
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_alt_filters_any(self):
		# Any filter should behave like the others
		response = self.client.get('/zoo/?.all_contact_name:any:icontains=zoo2')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
        # only zoo 2 contain .name=zoo2

		assert_json(returned_data, {
			'data': [
				{
					'id': 2,
					'name': 'zoo2',
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_alt_filters_all(self):
		# All filter should make sure all are done
		response = self.client.get('/zoo/?.all_contact_name:all=zoo3')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
        # only zoo 3 has all related names =zoo3 (both contact.name and .name)

		assert_json(returned_data, {
			'data': [
				{
					'id': 3,
					'name': 'zoo3',
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_alt_filters_not_any(self):
		response = self.client.get('/zoo/?.all_contact_name:any:not=contact2')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
		# :not:any means none, so only for zoo3 NONE of the name_fields contains contact2

		assert_json(returned_data, {
			'data': [
				{
					'id': 3,
					'name': 'zoo3',
					EXTRA(): None,  # Other fields are dontcare
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_alt_filters_not_all(self):
		response = self.client.get('/zoo/?.all_contact_name:all:not=zoo3')
		self.assertEqual(response.status_code, 200)
		returned_data = jsonloads(response.content)
		
		# :not:all means that it must contain a field that is NOT zoo3; all but zoo3 contains such a field

		assert_json(returned_data, {
			'data': [
				{
					'id': 1,
					'name': 'zoo1',
					EXTRA(): None,
				},
				{
					'id': 2,
					'name': 'zoo2',
					EXTRA(): None,
				}
			],
			EXTRA(): None,  # Debug, meta, with, etc
		})

	def test_alt_filters_both(self):
		# comibining any and all is not allowed, in any configuration!
		filter_options = [
			'all_contact_name:any:all:icontains',
			'all_contact_name:all:any:icontains',
			'all_contact_name:icontains:any:all',
			'all_contact_name:all:icontains:any',
			'all_contact_name:all:not:icontains:any',
		]

		for filter_value in filter_options:
			response = self.client.get(f'/zoo/?.{filter_value}=zoo2')
			self.assertEqual(response.status_code, 418)
			body = jsonloads(response.content)
