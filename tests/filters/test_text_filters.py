import unittest, os

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from ..testapp.models import Zoo


@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class TextFiltersTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()

        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)

        Zoo(name='Burgers Zoo').save()
        Zoo(name='Artis').save()
        Zoo(name='Apenheul').save()
        Zoo(name='Ouwehand Zoo').save()

    def test_filter_fuzzy(self):
        response = self.client.get('/zoo/', data={'.name:fuzzy': 'b zo'})
        self.assertEqual(response.status_code, 200)
        result = jsonloads(response.content)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Burgers Zoo', result['data'][0]['name'])

        response = self.client.get('/zoo/', data={'.name:fuzzy': '  zo  '})
        self.assertEqual(response.status_code, 200)
        result = jsonloads(response.content)
        self.assertEqual(2, len(result['data']))
        self.assertEqual('Burgers Zoo', result['data'][0]['name'])
        self.assertEqual('Ouwehand Zoo', result['data'][1]['name'])

        response = self.client.get('/zoo/', data={'.name:fuzzy': 'ar'})
        self.assertEqual(response.status_code, 200)
        result = jsonloads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Artis', result['data'][0]['name'])
