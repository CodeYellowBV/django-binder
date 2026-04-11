from django.test import TestCase, Client
from binder.json import jsonloads
from django.contrib.auth.models import User

from ..testapp.models import Zoo
import os

# This is not possible in
if os.environ.get('BINDER_TEST_MYSQL', '0') != '1':
	class TimeFiltersTest(TestCase):

		def setUp(self):
			super().setUp()
			u = User(username='testuser', is_active=True, is_superuser=True)
			u.set_password('test')
			u.save()
			self.client = Client()
			r = self.client.login(username='testuser', password='test')
			self.assertTrue(r)

			Zoo(name='Burgers Zoo', opening_time='11:00:00').save()
			Zoo(name='Artis', opening_time='09:00:00').save()


		def test_time_filter_exact_match(self):
			response = self.client.get('/zoo/', data={'.opening_time': '09:00:00Z'})
			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Artis', result['data'][0]['name'])

			response = self.client.get('/zoo/', data={'.opening_time': '11:00:00Z'})

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Burgers Zoo', result['data'][0]['name'])

			response = self.client.get('/zoo/', data={'.opening_time': '09:00:00.000+00:00'})
			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Artis', result['data'][0]['name'])

			response = self.client.get('/zoo/', data={'.opening_time': '11:00:00.000000+0000'})

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Burgers Zoo', result['data'][0]['name'])


		def test_time_filter_gte_match(self):
			response = self.client.get('/zoo/', data={'.opening_time:gte': '09:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(2, len(result['data']))
			self.assertEqual('Artis', result['data'][0]['name'])
			self.assertEqual('Burgers Zoo', result['data'][1]['name'])

			response = self.client.get('/zoo/', data={'.opening_time:gte': '10:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Burgers Zoo', result['data'][0]['name'])

			response = self.client.get('/zoo/', data={'.opening_time:gte': '12:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(0, len(result['data']))


		def test_time_filter_gt_match(self):
			response = self.client.get('/zoo/', data={'.opening_time:gt': '08:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(2, len(result['data']))
			self.assertEqual('Artis', result['data'][0]['name'])
			self.assertEqual('Burgers Zoo', result['data'][1]['name'])

			response = self.client.get('/zoo/', data={'.opening_time:gt': '09:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Burgers Zoo', result['data'][0]['name'])

			response = self.client.get('/zoo/', data={'.opening_time:gt': '12:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(0, len(result['data']))

		def time_time_filter_overnight_range(self):
			response = self.client.get('/zoo/', data={'.opening_time:range': '22:00:00Z,10:00:00Z', 'order_by': 'opening_time'})

			self.assertEqual(response.status_code, 200)

			result = jsonloads(response.content)
			self.assertEqual(1, len(result['data']))
			self.assertEqual('Artis', result['data'][0]['name'])

		def test_time_filter_syntax_errors_cause_error_response(self):
			response = self.client.get('/zoo/', data={'.opening_time': '1838-05-01'})
			self.assertEqual(response.status_code, 418)

			response = self.client.get('/zoo/', data={'.opening_time': '09:00:00Z-02'})
			self.assertEqual(response.status_code, 418)
