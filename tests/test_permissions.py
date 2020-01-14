from binder.json import jsondumps
from django.test import TestCase, override_settings

from django.contrib.auth.models import User, Group
from django.test import Client

from tests.testapp.models import Country, City

#
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
            ('testapp.change_country', 'all')
        ]
    })
    def test_delete_scoping_on_multiput(self):
        country = Country.objects.create(name='Nederland')
        city1 = City.objects.create(country=country, name='Amsterdam')
        city2 = City.objects.create(country=country, name='Leeuwarden')

        # Now suppose Friesland is finally going to seperate

        foo = self.client.get('/country/?with=cities')

        res = self.client.put('/country/', data=jsondumps({
            'data': [{
                'id': country.pk,
                'name': 'Nederland',
                'cities': [city1.pk]
            }]
        }))


        # This is not ok
        assert res.status_code != 200

        # City 2 still exists!
        city2.refresh_from_db()


        print(city2)
