import unittest, os

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from ..testapp.models import Zoo


@unittest.skipIf(
    'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (5, 0, 0),
    'Only available in Django 5+'
)
class GeneratedFieldFiltersTest(TestCase):

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

    def test_filter(self):
        response = self.client.get('/zoo/', data={'.upper_name:contains': 'BURGER'})
        self.assertEqual(response.status_code, 200)
        result = jsonloads(response.content)
        self.assertEqual(1, len(result['data']))
        self.assertEqual('Burgers Zoo', result['data'][0]['name'])
        self.assertEqual('BURGERS ZOO', result['data'][0]['upper_name'])
