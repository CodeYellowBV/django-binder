import json
from binder.json import jsondumps
from django.test import TestCase, override_settings

from django.contrib.auth.models import User, Group
from django.test import Client

from tests.testapp.models import Country, City, PermanentCity, CityState


class TestScoping(TestCase):
    def setUp(self):
        super().setUp()

        group = Group.objects.get()

        u = User(username='testuser', is_active=True, is_superuser=False)
        u.set_password('test')
        u.save()
        u.groups.add(group)

        self.client = Client()
        r = self.client.login(username='testuser', password='test')
        self.assertTrue(r)

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.change_country', 'all'),
            ('testapp.view_city', 'all')
        ]
    })
    def test_cannot_delete_on_multiput_without_delete_permission(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')
        city2 = City.objects.create(country=country, name='Leeuwarden')

        # Now suppose Friesland is finally going to seperate

        res = self.client.put('/country/', data=jsondumps({
            'data': [{
                'id': country.pk,
                'name': 'Nederland',
                'cities': [city1.pk]
            }]
        }))

        # This is not ok
        assert res.status_code == 403

        content = json.loads(res.content)
        assert 'testapp.delete_city' == content['required_permission']

        # City 2 still exists!
        city2.refresh_from_db()

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.change_country', 'all'),
            ('testapp.view_city', 'all'),
            ('testapp.delete_city', 'all'),
        ]
    })
    def test_delete_scoping_on_multiput_with_delete_permission(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')
        city2 = City.objects.create(country=country, name='Leeuwarden')

        # Now suppose Friesland is finally going to seperate

        res = self.client.put('/country/', data=jsondumps({
            'data': [{
                'id': country.pk,
                'name': 'Nederland',
                'cities': [city1.pk]
            }]
        }))

        # This is not ok
        assert res.status_code == 200

        # City 2 must not exist. TODO: test this
        with self.assertRaises(City.DoesNotExist):
            city2.refresh_from_db()

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.change_country', 'all')
        ]
    })
    def test_cannot_change_on_multiput_without_change_permission(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')

        res = self.client.put('/country/', data=jsondumps({
            'data': [{
                'id': country.pk,
                'name': 'Nederland',
                'cities': [city1.pk]
            }],
            'with': {
                'city': [{
                    'id': city1.pk,
                    'name': 'Rotterdam',
                }]
            }
        }))

        # This is not ok
        assert res.status_code == 403
        content = json.loads(res.content)
        assert 'testapp.change_city' == content['required_permission']

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_city', 'all'),
        ]
    })
    def test_cannot_delete_on_put_without_delete_permission(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')
        city2 = City.objects.create(country=country, name='Leeuwarden')

        # Now suppose Friesland is finally going to seperate

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Nederland',
            'cities': [city1.pk]
        }))

        # This is not ok
        assert res.status_code == 403

        content = json.loads(res.content)
        assert 'testapp.delete_city' == content['required_permission']

        # City 2 still exists!
        city2.refresh_from_db()

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_city', 'all'),
            ('testapp.delete_city', 'all')
        ]
    })
    def test_can_delete_on_put_with_delete_permission(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')
        city2 = City.objects.create(country=country, name='Leeuwarden')

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Nederland',
            'cities': [city1.pk]
        }))

        assert res.status_code == 200

        with self.assertRaises(City.DoesNotExist):
            city2.refresh_from_db()

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_permanentcity', 'all'),
            ('testapp.delete_permanentcity', 'all')
        ]
    })
    def test_softdelete_on_put_with_delete_permission_softdeletable(self):
        country = Country.objects.create(name='Nederland')
        city1 = PermanentCity.objects.create(country=country, name='Rotterdam', deleted=False)

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Nederland',
            'permanent_cities': []
        }))

        assert res.status_code == 200
        city1.refresh_from_db()
        assert city1.deleted

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_permanentcity', 'all'),
        ]
    })
    def test_softdelete_on_put_without_softdelete_permission_fails(self):
        country = Country.objects.create(name='Nederland')
        city1 = PermanentCity.objects.create(country=country, name='Rotterdam', deleted=False)

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Nederland',
            'permanent_cities': []
        }))

        assert res.status_code == 403
        content = json.loads(res.content)
        assert 'testapp.delete_permanentcity' == content['required_permission']

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_citystate', 'all'),
            ('testapp.change_citystate', 'all'),
        ]
    })
    def test_related_object_nullable_on_delete_is_set_to_null(self):
        country = Country.objects.create(name='Belgium')
        city1 = CityState.objects.create(country=country, name='Brussels')

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Belgium',
            'city_states': []
        }))
        assert res.status_code == 200

        city1.refresh_from_db()

        assert city1.country is None

    @override_settings(BINDER_PERMISSION={
        'testapp.view_country': [
            ('testapp.view_country', 'all'),
            ('testapp.change_country', 'all'),
            ('testapp.view_citystate', 'all'),
        ]
    })
    def test_related_object_nullable_on_delete_no_change_permission_not_allowed(self):
        country = Country.objects.create(name='Belgium')
        city1 = CityState.objects.create(country=country, name='Brussels')

        res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
            'id': country.pk,
            'name': 'Belgium',
            'city_states': []
        }))

        assert res.status_code == 403

        content = json.loads(res.content)
        assert 'testapp.change_citystate' == content['required_permission']

        city1.refresh_from_db()

        assert city1.country.pk == country.pk
