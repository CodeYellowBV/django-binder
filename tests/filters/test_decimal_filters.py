from django.test import TestCase, Client
from binder.json import jsonloads
from django.contrib.auth.models import User

from ..testapp.models import Zoo, ZooEmployee

class DecimalFiltersTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		zoo = Zoo(name='CY')
		zoo.save()

		ZooEmployee(name='Junior', hourly_wage='12.34', zoo=zoo).save()
		ZooEmployee(name='Senior', hourly_wage='23.45', zoo=zoo).save()


	def test_decimal_filter_exact_match(self):
		response = self.client.get('/zoo_employee/', data={'.hourly_wage': '12.34'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Junior', result['data'][0]['name'])

		response = self.client.get('/zoo_employee/', data={'.hourly_wage': '23.45'})

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Senior', result['data'][0]['name'])


	def test_date_filter_gte_match(self):
		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gte': '12.34', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Junior', result['data'][0]['name'])
		self.assertEqual('Senior', result['data'][1]['name'])

		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gte': '12.341', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Senior', result['data'][0]['name'])

		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gte': '24', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_date_filter_gt_match(self):
		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gt': '12.339', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual('Junior', result['data'][0]['name'])
		self.assertEqual('Senior', result['data'][1]['name'])

		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gt': '23.449', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual('Senior', result['data'][0]['name'])

		response = self.client.get('/zoo_employee/', data={'.hourly_wage:gt': '23.45', 'order_by': 'hourly_wage'})

		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))
