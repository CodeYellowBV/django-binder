from django.contrib.auth.models import User
from django.test import Client, TestCase
from .testapp.models import Pet, Truck


class ModelViewEndpointAtomicityTest(TestCase):

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

class PermissionViewEndpointAtomicityTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()
        self.client = Client()
        self.assertTrue(self.client.login(username='testuser', password='test'))

    def test_atomic_list_route(self):
        old_num_pets = Pet.objects.all().count()
        with self.assertRaises(PermissionError):
            self.client.get('/pet/atomic/')
        self.assertEqual(old_num_pets, Pet.objects.all().count())

    def test_non_atomic_list_route(self):
        old_num_pets = Pet.objects.all().count()
        with self.assertRaises(PermissionError):
            self.client.get('/pet/non-atomic/')
        self.assertEqual(old_num_pets + 1, Pet.objects.all().count())

    def test_atomic_detail_route(self):
        old_pet = Pet.objects.create(name='old')
        old_num_pets = Pet.objects.all().count()
        with self.assertRaises(PermissionError):
            self.client.get(f'/pet/{old_pet.id}/atomic/')
        self.assertEqual(old_num_pets, Pet.objects.all().count())

    def test_non_atomic_detail_route(self):
        old_pet = Pet.objects.create(name='old')
        old_num_pets = Pet.objects.all().count()
        with self.assertRaises(PermissionError):
            self.client.get(f'/pet/{old_pet.id}/non-atomic/')
        self.assertEqual(old_num_pets + 1, Pet.objects.all().count())
