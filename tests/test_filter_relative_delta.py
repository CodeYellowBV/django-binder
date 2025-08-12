from dateutil.relativedelta import relativedelta
from django.contrib.auth.models import User
from django.test import Client, TestCase
from json import loads
from .testapp.models import Animal


class FilterRelativeDeltaTest(TestCase):
    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()
        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)

    def test_filter(self):
        bokito = Animal.objects.create(name='Bokito', feeding_period=relativedelta(hours=5))
        harambe = Animal.objects.create(name='Harambe', feeding_period=relativedelta(days=2))
        self.assertEqual(bokito.id, Animal.objects.filter(feeding_period__lt=relativedelta(days=1)).get().id)
        response = self.client.get('/animal/?.feeding_period:gt=P1DT6H')
        content = loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(content['data']))
        self.assertEqual(harambe.id, content['data'][0]['id'])

    def test_sort(self):
        bokito = Animal.objects.create(name='Bokito', feeding_period=relativedelta(hours=5))
        harambe = Animal.objects.create(name='Harambe', feeding_period=relativedelta(days=2))
        otto = Animal.objects.create(name='Otto', feeding_period=relativedelta(days=1, hours=1))

        sanity = list(Animal.objects.all().order_by('feeding_period'))
        self.assertEqual(bokito.id, sanity[0].id)
        self.assertEqual(otto.id, sanity[1].id)
        self.assertEqual(harambe.id, sanity[2].id)

        response = self.client.get('/animal/?order_by=feeding_period')
        content = loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(3, len(content['data']))
        self.assertEqual(bokito.id, content['data'][0]['id'])
        self.assertEqual(otto.id, content['data'][1]['id'])
        self.assertEqual(harambe.id, content['data'][2]['id'])

        response = self.client.get('/animal/?order_by=-feeding_period')
        content = loads(response.content)
        self.assertEqual(200, response.status_code)
        self.assertEqual(3, len(content['data']))
        self.assertEqual(harambe.id, content['data'][0]['id'])
        self.assertEqual(otto.id, content['data'][1]['id'])
        self.assertEqual(bokito.id, content['data'][2]['id'])

    def test_default_value(self):
        self.assertEqual(relativedelta(days=1), Animal.objects.create(name='Default').feeding_period)
