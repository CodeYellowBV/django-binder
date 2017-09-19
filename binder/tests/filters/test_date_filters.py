from django.test import TestCase, Client
from binder.json import jsonloads
from django.contrib.auth.models import User

from ..testapp.models import Zoo

class DateFiltersTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		Zoo(name='Burgers Zoo', founding_date='1913-02-13').save()  # Couldn't find exact date, only year, but meh
		Zoo(name='Artis', founding_date='1838-05-01').save()


	def test_date_filter_exact_match(self):
		response = self.client.get('/zoo/', data={'.founding_date': '1838-05-01'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Artis', result['data'][0]['name'])

		response = self.client.get('/zoo/', data={'.founding_date': '1913-02-13'})

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Burgers Zoo', result['data'][0]['name'])


	def test_date_filter_gte_match(self):
		response = self.client.get('/zoo/', data={'.founding_date:gte': '1838-05-01', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Artis', result['data'][0]['name'])
		self.assertEqual('Burgers Zoo', result['data'][1]['name'])

		response = self.client.get('/zoo/', data={'.founding_date:gte': '1838-05-02', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Burgers Zoo', result['data'][0]['name'])

		response = self.client.get('/zoo/', data={'.founding_date:gte': '2001-01-01', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_date_filter_gt_match(self):
		response = self.client.get('/zoo/', data={'.founding_date:gt': '1838-04-30', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Artis', result['data'][0]['name'])
		self.assertEqual('Burgers Zoo', result['data'][1]['name'])

		response = self.client.get('/zoo/', data={'.founding_date:gt': '1838-05-01', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Burgers Zoo', result['data'][0]['name'])

		response = self.client.get('/zoo/', data={'.founding_date:gt': '2001-01-01', 'order_by': 'founding_date'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_date_filter_syntax_errors_cause_error_response(self):
		response = self.client.get('/zoo/', data={'.founding_date': '1838-05'})
		# Not much more we can do...  There's no indication what's wrong so far
		self.assertEqual(response.status_code, 418)

		response = self.client.get('/zoo/', data={'.founding_date': '1838-05-01-02'})
		self.assertEqual(response.status_code, 418)

		# These are valid for datetimes, but not for dates
		response = self.client.get('/zoo/', data={'.founding_date': '1838-05-01T02:10:02'})
		self.assertEqual(response.status_code, 418)

		response = self.client.get('/zoo/', data={'.founding_date': '1838-05-01T02:10:02Z'})
		self.assertEqual(response.status_code, 418)
