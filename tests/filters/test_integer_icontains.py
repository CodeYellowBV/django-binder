import unittest, os

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from ..testapp.models import Zoo, ZooEmployee


@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class IntegerIcontainsTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()

        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)

        zoo = Zoo(name='Yes')
        zoo.save()

        ZooEmployee(name='Small Number Fan', favorite_number='3', zoo=zoo).save()
        ZooEmployee(name='Big Number Enjoyer', favorite_number='100023', zoo=zoo).save()
        ZooEmployee(name='Bob', favorite_number='101', zoo=zoo).save()

    def test_filter_partial_match(self):
        response = self.client.get('/zoo_employee/', data={'.favorite_number:icontains': '3'})

        self.assertEqual(response.status_code, 200)

        result = jsonloads(response.content)
        self.assertEqual(2, len(result['data']))
        self.assertEqual('Small Number Fan', result['data'][0]['name'])
        self.assertEqual('Big Number Enjoyer', result['data'][1]['name'])

        response = self.client.get('/zoo_employee/', data={'.favorite_number:icontains': '100'})

        result = jsonloads(response.content)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Big Number Enjoyer', result['data'][0]['name'])

    def test_filter_exact_match(self):
        response = self.client.get('/zoo_employee/', data={'.favorite_number': '3'})

        self.assertEqual(response.status_code, 200)

        result = jsonloads(response.content)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Small Number Fan', result['data'][0]['name'])

        response = self.client.get('/zoo_employee/', data={'.favorite_number': '101'})

        result = jsonloads(response.content)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Bob', result['data'][0]['name'])
