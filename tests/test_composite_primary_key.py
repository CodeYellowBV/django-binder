from datetime import date
from django.contrib.auth.models import User
from django.test import Client, TestCase
import json
import os
import unittest
from .testapp.models import City, ContactPerson, ContactPersonRating, Country, Zoo


@unittest.skipIf(
    'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (5, 2, 0),
    'Only available from Django >= 5.2'
)
class CompositePrimaryKeyTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()
        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)


    def test_create(self):
        ContactPerson.objects.create(name='Jantje')
        creation_data = {
            'contact_person': 'Jantje',
            'date': '2026-07-08',
            'rating': 8,
        }
        response = self.client.post('/contact_person_rating/', data=json.dumps(creation_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(8, ContactPersonRating.objects.get().rating)

    def test_list(self):
        jantje = ContactPerson.objects.create(name='Jantje')
        ContactPersonRating.objects.create(contact_person=jantje, date=date(2026, 1, 1), rating=6)
        ContactPersonRating.objects.create(contact_person=jantje, date=date(2026, 1, 2), rating=7)
        zoo = Zoo.objects.create(name='Dorpje')
        zoo.contacts.add(jantje)

        # Test whether we can list the ratings directly
        response = self.client.get('/contact_person_rating/')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)['data']
        self.assertEqual('Jantje', data[0]['contact_person'])
        self.assertEqual('2026-01-01', data[0]['date'])
        self.assertEqual(6, data[0]['rating'])
        self.assertEqual('Jantje', data[1]['contact_person'])
        self.assertEqual('2026-01-02', data[1]['date'])
        self.assertEqual(7, data[1]['rating'])

        # Test whether we can list the ratings indirectly
        response = self.client.get('/contact_person/?with=ratings')
        self.assertEqual(response.status_code, 200)
        content = json.loads(response.content)
        self.assertEqual(1, len(content['data']))
        person = content['data'][0]
        self.assertEqual('Jantje', person['name'])
        self.assertEqual([['Jantje', '2026-01-01'], ['Jantje', '2026-01-02']], person['ratings'])
        rating = content['with']['contact_person_rating'][0]
        self.assertEqual(['Jantje', '2026-01-01'], rating['pk'])
        self.assertEqual(['Jantje', '2026-01-01'], rating['id'])
        self.assertEqual('Jantje', rating['contact_person'])
        self.assertEqual('2026-01-01', rating['date'])
        self.assertEqual(6, rating['rating'])

    def test_filter_on_relations(self):
        tim = ContactPerson.objects.create(name='Tim')
        eindhoven = City.objects.create(name='Eindhoven', country=Country.objects.create(name='Netherlands'))
        ContactPersonRating.objects.create(contact_person=tim, date=date(2026, 7, 23), rating=10, source_city=eindhoven)

        response = self.client.get('/city/?.rating:isnull=true')
        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual(0, len(response_data['data']))

        response = self.client.get('/city/?.rating:isnull=false')
        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual(1, len(response_data['data']))
