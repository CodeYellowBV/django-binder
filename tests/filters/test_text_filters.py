import unittest
import os
from django.test import TestCase, Client
from binder.json import jsonloads
from django.contrib.auth.models import User

from ..testapp.models import Caretaker

class TextFiltersTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		Caretaker(name='Peter').save()
		Caretaker(name='Stefan').save()


	def test_text_filter_exact_match(self):
		response = self.client.get('/caretaker/', data={'.name': 'Stefan'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get('/caretaker/', data={'.name': 'Stefa'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

	def test_text_filter_iexact(self):
		response = self.client.get('/caretaker/', data={'.name:iexact': 'stefan'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get('/caretaker/', data={'.name:iexact': 'sTEfaN'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

	# Unaccent extension tests
	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_exact_match_unaccent(self):
		response = self.client.get('/caretaker/', data={'.name:unaccent': 'Śtefan'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get('/caretaker/', data={'.name:unaccent': 'Śtefa'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_iexact_unaccent(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:iexact': 'stęfan'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:iexact': 'sTĘfaN'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_contains(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:contains': 'stęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:contains': 'Stęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:contains': 'ę'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_icontains(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:icontains': 'stęfi'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:icontains': 'sTĘf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:icontains': 'Ę'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_startswith(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:startswith': 'tęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:startswith': 'Śtęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:startswith': 'śtę'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_istartswith(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:istartswith': 'tęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:istartswith': 'stęf'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:istartswith': 'sTĘF'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_endswith(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:endswith': 'efą'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:endswith': 'efań'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:endswith': 'efaŃ'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

	@unittest.skipIf(
		os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
		"Only available with PostgreSQL"
	)
	def test_text_filter_iendswith(self):
		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:iendswith': 'ęfa'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:iendswith': 'EfĄn'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])

		response = self.client.get(
			'/caretaker/', data={'.name:unaccent:iendswith': 'efąN'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Stefan', result['data'][0]['name'])
