from django.contrib.auth.models import User
from django.test import Client, TestCase
import json
from .testapp.models import ContactPerson, Zoo


class StringPrimaryKeyTest(TestCase):

    def setUp(self):
        super().setUp()
        u = User(username='testuser', is_active=True, is_superuser=True)
        u.set_password('test')
        u.save()
        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)

    def test_create_update_delete(self):
        creation_data = {
            'name': 'Jantje',
        }
        response = self.client.post('/contact_person/', data=json.dumps(creation_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual('Jantje', ContactPerson.objects.get().name)

        update_data = {
            'name': 'Jantje',
            'nick_name': 'Pietje',
        }
        response = self.client.patch('/contact_person/Jantje/', data=json.dumps(update_data), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual('Jantje', ContactPerson.objects.get().name)
        self.assertEqual('Pietje', ContactPerson.objects.get().nick_name)

        response = self.client.delete('/contact_person/Jantje/', data={}, content_type='application/json')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(0, ContactPerson.objects.all().count())

    def test_attach_in_multi_put1(self):
        ContactPerson.objects.create(name='Tim')
        ContactPerson.objects.create(name='Pieter')
        creation_data = {
            'data': [
                {
                    'id': -1,
                    'name': 'Beekse Bergen',
                    'director': 'Tim',
                    'contacts': ['Tim', 'Pieter'],
                },
            ]
        }
        response = self.client.put('/zoo/', data=json.dumps(creation_data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual('Tim', Zoo.objects.get().director.name)
        self.assertEqual(['Pieter', 'Tim'], list(Zoo.objects.get().contacts.all().values_list('name', flat=True)))

    def test_attach_in_multi_put2(self):
        ContactPerson.objects.create(name='Tim')
        ContactPerson.objects.create(name='Pieter')
        Zoo.objects.create(id=1, name='Beekse Bergen')
        creation_data = {
            'data': [
                {
                    'id': 1,
                    'director': 'Tim',
                    'contacts': ['Tim', 'Pieter'],
                },
            ]
        }
        response = self.client.put('/zoo/', data=json.dumps(creation_data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual('Tim', Zoo.objects.get().director.name)
        self.assertEqual(['Pieter', 'Tim'], list(Zoo.objects.get().contacts.all().values_list('name', flat=True)))

    def test_create_and_edit_in_multi_put(self):
        ContactPerson.objects.create(name='Tim')
        ContactPerson.objects.create(name='Bob')
        other_zoo = Zoo.objects.create(name='lalala')
        creation_data = {
            'data': [
                {
                    'id': -1,
                    'name': 'Beekse Bergen',
                    'director': 'Tim',
                    'contacts': ['Tim', 'Pieter'],
                    'originals': ['Nuria', 'Bob'],
                },
            ],
            'with': {
                'contact_person': [
                    { 'name': 'Tim', 'nick_name': 'knokko', 'successor': 'Pieter', 'ratings': [] },
                    { 'name': 'Pieter', 'nick_name': 'Pietje', 'first_zoo': other_zoo.id },
                    { 'name': 'Bob', 'nick_name': 'Gigolo Bob' },
                    { 'name': 'Nuria', 'successor': 'Tim' },
                ]
            }
        }
        response = self.client.put('/zoo/', data=json.dumps(creation_data))
        self.assertEqual(response.status_code, 200)
        self.assertEqual('Tim', Zoo.objects.get(name='Beekse Bergen').director.name)
        self.assertEqual(['Pieter', 'Tim'], list(Zoo.objects.get(name='Beekse Bergen').contacts.all().values_list('name', flat=True)))
        self.assertEqual('knokko', ContactPerson.objects.get(name='Tim').nick_name)
        self.assertEqual('Pietje', ContactPerson.objects.get(name='Pieter').nick_name)
        id_map = json.loads(response.content)['idmap']
        self.assertEqual(1, len(id_map))
        self.assertEqual(1, len(id_map['zoo']))
        self.assertEqual(Zoo.objects.get(name='Beekse Bergen').id, id_map['zoo'][0][-1])
        self.assertEqual('lalala', ContactPerson.objects.get(name='Pieter').first_zoo.name)

    def test_searches(self):
        tim = ContactPerson.objects.create(name='Tim')
        Zoo.objects.create(name='Beekse Bergen', director=tim)
        Zoo.objects.create(name='Dolfinarium')
        response = self.client.get('/zoo/?search=Tim')
        self.assertEqual(200, response.status_code)
        data = json.loads(response.content)['data']
        self.assertEqual(1, len(data))
        self.assertEqual('Beekse Bergen', data[0]['name'])

    def test_filter_on_relations(self):
        tim = ContactPerson.objects.create(name='Tim')
        Zoo.objects.create(name='Beekse Bergen', director=tim)
        response = self.client.get('/zoo/?.director:isnull=true')
        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual(0, len(response_data['data']))

        response = self.client.get('/zoo/?.director:isnull=false')
        self.assertEqual(200, response.status_code)
        response_data = json.loads(response.content)
        self.assertEqual(1, len(response_data['data']))
