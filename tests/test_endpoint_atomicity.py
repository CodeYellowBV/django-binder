from django.contrib.auth.models import User
from django.test import Client, TestCase
from .testapp.models import Truck


class EndpointAtomicityTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()
        self.client = Client()
        self.assertTrue(self.client.login(username='testuser', password='test'))

    def test_atomic_list_route(self):
        old_num_trucks = Truck.objects.all().count()
        self.assertEqual(400, self.client.get('/truck/atomic/').status_code)
        self.assertEqual(old_num_trucks, Truck.objects.all().count())

    def test_non_atomic_list_route(self):
        old_num_trucks = Truck.objects.all().count()
        self.assertEqual(400, self.client.get('/truck/non-atomic/').status_code)
        self.assertEqual(old_num_trucks + 1, Truck.objects.all().count())

    def test_atomic_detail_route(self):
        old_truck = Truck.objects.create(name='old')
        old_num_trucks = Truck.objects.all().count()
        self.assertEqual(400, self.client.get(f'/truck/{old_truck.id}/atomic/').status_code)
        self.assertEqual(old_num_trucks, Truck.objects.all().count())

    def test_non_atomic_detail_route(self):
        old_truck = Truck.objects.create(name='old')
        old_num_trucks = Truck.objects.all().count()
        self.assertEqual(400, self.client.get(f'/truck/{old_truck.id}/non-atomic/').status_code)
        self.assertEqual(old_num_trucks + 1, Truck.objects.all().count())
