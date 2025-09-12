import json
from .compare import assert_json, EXTRA
from unittest.mock import MagicMock

from django.test import TestCase, Client,  override_settings
from django.db.models import Q

from binder.json import jsonloads, jsondumps
from binder.permissions.views import is_q_stricter, smart_q_or, PermissionView

from .testapp.models import Zoo, ZooEmployee, Country, City, PermanentCity, CityState, Animal
from .testapp.urls import router

from django.contrib.auth.models import User, Group

class TestWithoutPerm(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.zoo = Zoo(name='Artis')
		self.zoo.save()

		self.zoo_employee = ZooEmployee(zoo=self.zoo, name='Piet Heyn')
		self.zoo_employee.save()
	def test_get_resource(self):
		res = self.client.get('/zoo_employee/{}/'.format(self.zoo_employee.id))
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.view_zooemployee',
			EXTRA(): None,
		})


	def test_get_resource_through_with(self):
		res = self.client.get('/zoo/{}/?with=zoo_employees'.format(self.zoo.id))
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.view_zooemployee',
			EXTRA(): None,
		})


	def test_post_new_resource(self):
		res = self.client.post('/zoo_employee/', data='{}', content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})


	def test_multiput_new_resource_through_with(self):
		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': -1,
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})


	def test_put_existing_resource(self):
		res = self.client.put('/zoo_employee/{}/'.format(self.zoo_employee.id), data='{}', content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


	def test_multiput_existing_resource_through_with(self):
		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': self.zoo_employee.id,
			}]
		}}), content_type='application/json')
		#self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


class TestWithPermButOutOfScope(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser2', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser2', password='test')
		self.assertTrue(r)

		self.zoo = Zoo(name='Artis')
		self.zoo.save()
		self.zoo_employee = ZooEmployee(zoo=self.zoo, name='Piet Heyn')
		self.zoo_employee.save()

	def test_get_resource(self):
		res = self.client.get('/zoo_employee/{}/'.format(self.zoo_employee.id))
		self.assertEqual(res.status_code, 404)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'NotFound',
			EXTRA(): None,
		})

	def test_get_resource_through_with(self):
		res = self.client.get('/zoo/{}/?with=zoo_employees'.format(self.zoo.id))
		self.assertEqual(res.status_code, 200)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'data': {
				'id': self.zoo.id,
				EXTRA(): None,
			},
			'with': {
				'zoo_employee': [],
			},
			'with_mapping': {
				'zoo_employees': 'zoo_employee',
			},
			'with_related_name_mapping': {
				'zoo_employees': 'zoo',
			},
			EXTRA(): None,
		})


class TestWithCustomPerm(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser3', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser3', password='test')
		self.assertTrue(r)

		self.zoo = Zoo(name='Artis')
		self.zoo.save()
		self.zoo_employee = ZooEmployee(zoo=self.zoo, name='Piet Heyn')
		self.zoo_employee.save()


	def test_post_new_resource(self):
		res = self.client.post('/zoo_employee/', data=jsondumps({
			'zoo': self.zoo.id,
			'name': 'change okay',
		}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})

		res = self.client.post('/zoo_employee/', data=jsondumps({
			'zoo': self.zoo.id,
			'name': 'add okay',
		}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_new_resource_through_with(self):
		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': -1,
				'name': 'change okay',
				'zoo': self.zoo.id,
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})

		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': -1,
				'name': 'add okay',
				'zoo': self.zoo.id,
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_new_resource_through_main_data(self):
		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': -1,
				'name': 'change okay',
				'zoo': self.zoo.id,
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})

		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': -1,
				'name': 'add okay',
				'zoo': self.zoo.id,
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_put_existing_resource(self):
		res = self.client.put('/zoo_employee/{}/'.format(self.zoo_employee.id), data='{"name": "add okay"}', content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.add_zooemployee',
			EXTRA(): None,
		})

		res = self.client.put('/zoo_employee/{}/'.format(self.zoo_employee.id), data='{"name": "change okay"}', content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_existing_resource_through_with(self):
		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': self.zoo_employee.id,
				'name': 'add okay',
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': self.zoo_employee.id,
				'name': 'change okay',
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_existing_resource_through_main_data(self):
		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': self.zoo_employee.id,
				'name': 'add okay',
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': self.zoo_employee.id,
				'name': 'change okay',
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_existing_and_new_resource_through_with(self):
		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': self.zoo_employee.id,
				'name': 'add okay',
			}, {
				'id': -1,
				'zoo': self.zoo.id,
				'name': 'change okay',
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


		res = self.client.put('/zoo/', data=jsondumps({'data': [], 'with': {
			'zoo_employee': [{
				'id': self.zoo_employee.id,
				'name': 'change okay',
			}, {
				'id': -1,
				'zoo': self.zoo.id,
				'name': 'add okay',
			}]
		}}), content_type='application/json')
		self.assertEqual(res.status_code, 200)


	def test_multiput_existing_and_new_resource_through_main_endpoint(self):
		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': self.zoo_employee.id,
				'name': 'add okay',
			}, {
				'id': -1,
				'zoo': self.zoo.id,
				'name': 'change okay',
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			# We actually get a different error: "you do not have a scope that allows..."
			#'required_permission': 'testapp.change_zooemployee',
			EXTRA(): None,
		})


		res = self.client.put('/zoo_employee/', data=jsondumps({
			'data': [{
				'id': self.zoo_employee.id,
				'name': 'change okay',
			}, {
				'id': -1,
				'zoo': self.zoo.id,
				'name': 'add okay',
			}]
		}), content_type='application/json')
		self.assertEqual(res.status_code, 200)




class TestPutRelationScoping(TestCase):
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

		# Now suppose Friesland is finally going to separate

		res = self.client.put('/country/', data=jsondumps({
			'data': [{
				'id': country.pk,
				'name': 'Nederland',
				'cities': [city1.pk]
			}]
		}))

		# This is not ok
		self.assertEqual(403, res.status_code)

		content = jsonloads(res.content)
		self.assertEqual('testapp.delete_city',  content['required_permission'])

		# City 2 still exists!
		city2.refresh_from_db()
		self.assertEqual(country, city2.country) # And belongs to the nederlands

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

		# Now suppose Friesland is finally going to separate

		res = self.client.put('/country/', data=jsondumps({
			'data': [{
				'id': country.pk,
				'name': 'Nederland',
				'cities': [city1.pk]
			}]
		}))

		self.assertEqual(200, res.status_code)

		# City 2 must not exist.
		with self.assertRaises(City.DoesNotExist):
			city2.refresh_from_db()
		self.assertEqual(1, country.cities.count())

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
		self.assertEqual(403, res.status_code)
		content = jsonloads(res.content)
		self.assertEqual('testapp.change_city', content['required_permission'])

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

		# Now suppose Friesland is finally going to separate

		res = self.client.put('/country/{}/'.format(country.pk), data=jsondumps({
			'id': country.pk,
			'name': 'Nederland',
			'cities': [city1.pk]
		}))

		# This is not ok
		self.assertEqual(res.status_code, 403)

		content = jsonloads(res.content)
		self.assertEqual('testapp.delete_city', content['required_permission'])

		# City 2 still exists!
		city2.refresh_from_db()
		self.assertEqual(country, city2.country)

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

		self.assertEqual(200, res.status_code)

		with self.assertRaises(City.DoesNotExist):
			city2.refresh_from_db()
		self.assertEqual(1, country.cities.count())

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

		self.assertEqual(200,  res.status_code)
		city1.refresh_from_db()
		self.assertTrue(city1.deleted)

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

		self.assertEqual(res.status_code, 403)
		content = jsonloads(res.content)
		self.assertEqual('testapp.delete_permanentcity', content['required_permission'])

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
		self.assertEqual(200, res.status_code)

		city1.refresh_from_db()

		self.assertIsNone(city1.country)

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

		self.assertEqual(403, res.status_code)

		content = jsonloads(res.content)
		self.assertEqual('testapp.change_citystate', content['required_permission'])

		city1.refresh_from_db()

		self.assertEqual(country.pk, country.pk)

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_country', 'all'),
			('testapp.delete_country', 'all'),
		],
	})
	def test_multiput_deletions(self):
		country = Country.objects.create(name='Netherlands')
		res = self.client.put('/country/'.format(country.pk), data=jsondumps({
			'deletions': [country.pk],
		}))

		self.assertEqual(200, res.status_code)

		with self.assertRaises(Country.DoesNotExist):
			country.refresh_from_db()

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_country', 'all'),
		],
	})
	def test_multiput_deletions_no_perm(self):
		country = Country.objects.create(name='Netherlands')
		res = self.client.put('/country/'.format(country.pk), data=jsondumps({
			'deletions': [country.pk],
		}))

		self.assertEqual(403, res.status_code)

		country.refresh_from_db()

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_country', 'all'),
			('testapp.delete_country', 'all'),
		],
	})
	def test_multiput_with_deletions(self):
		country = Country.objects.create(name='Netherlands')
		res = self.client.put('/city/'.format(country.pk), data=jsondumps({
			'with_deletions': {'country': [country.pk]},
		}))

		self.assertEqual(200, res.status_code)

		with self.assertRaises(Country.DoesNotExist):
			country.refresh_from_db()

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_country', 'all'),
		],
	})
	def test_multiput_with_deletions_no_perm(self):
		country = Country.objects.create(name='Netherlands')
		res = self.client.put('/city/'.format(country.pk), data=jsondumps({
			'with_deletions': {'country': [country.pk]},
		}))

		self.assertEqual(403, res.status_code)

		country.refresh_from_db()


class ViewScopeTest(TestCase):

	def setUp(self):
		self.zoo = Zoo.objects.create(name='Zoo')
		Animal.objects.create(zoo=self.zoo, name='Foo')
		Animal.objects.create(zoo=self.zoo, name='Bar')

	def test_bad_scope(self):
		user = User.objects.create(username='testuser_for_bad_q_filter')

		ZooView = router.model_views[Zoo]
		zoo_view = ZooView()
		zoo_view.router = router

		request = MagicMock()
		request.user = user

		zoos = list(zoo_view.get_queryset(request).values_list('pk', flat=True))
		self.assertEqual(zoos, [self.zoo.pk, self.zoo.pk])

	def test_good_scope(self):
		user = User.objects.create(username='testuser_for_good_q_filter')

		ZooView = router.model_views[Zoo]
		zoo_view = ZooView()
		zoo_view.router = router

		request = MagicMock()
		request.user = user

		zoos = list(zoo_view.get_queryset(request).values_list('pk', flat=True))
		self.assertEqual(zoos, [self.zoo.pk])


class IsQStricterTest(TestCase):

	def test_stricter(self):
		foo = Q(foo=1)
		foo_and_bar = Q(foo=1, bar=2)

		self.assertTrue(is_q_stricter(foo, foo))
		self.assertFalse(is_q_stricter(foo, foo_and_bar))
		self.assertTrue(is_q_stricter(foo_and_bar, foo))
		self.assertTrue(is_q_stricter(foo_and_bar, foo_and_bar))

	def test_distinct(self):
		foo = Q(foo=1)
		bar = Q(bar=2)

		self.assertTrue(is_q_stricter(foo, foo))
		self.assertFalse(is_q_stricter(foo, bar))
		self.assertFalse(is_q_stricter(bar, foo))
		self.assertTrue(is_q_stricter(bar, bar))

	def test_pk_not_in_empty_list(self):
		pk_not_in_empty_list = ~Q(pk__in=[])
		foo = Q(foo=1)

		self.assertTrue(is_q_stricter(pk_not_in_empty_list, pk_not_in_empty_list))
		self.assertFalse(is_q_stricter(pk_not_in_empty_list, foo))
		self.assertTrue(is_q_stricter(foo, pk_not_in_empty_list))
		self.assertTrue(is_q_stricter(foo, foo))


class SmartQOrTest(TestCase):

	def test_stricter(self):
		foo = Q(foo=1)
		foo_and_bar = Q(foo=1, bar=2)

		combined = smart_q_or(foo, foo_and_bar)
		self.assertEqual(combined, foo)

	def test_distinct(self):
		foo = Q(foo=1)
		bar = Q(bar=2)

		combined = smart_q_or(foo, bar)
		self.assertEqual(combined, foo | bar)

	def test_pk_not_in_empty_list(self):
		pk_not_in_empty_list = ~Q(pk__in=[])
		foo = Q(foo=1)

		combined = smart_q_or(pk_not_in_empty_list, foo)
		self.assertEqual(combined, pk_not_in_empty_list)

	def test_stricter_top_level_or(self):
		foo = Q(foo=1)
		foo_and_bar = Q(foo=1, bar=2)

		combined = smart_q_or(foo | foo_and_bar)
		self.assertEqual(combined, foo)

	def test_distinct_top_level_or(self):
		foo = Q(foo=1)
		bar = Q(bar=2)

		combined = smart_q_or(foo | bar)
		self.assertEqual(combined, foo | bar)

	def test_pk_not_in_empty_list_top_level_or(self):
		pk_not_in_empty_list = ~Q(pk__in=[])
		foo = Q(foo=1)

		combined = smart_q_or(pk_not_in_empty_list | foo)
		self.assertEqual(combined, pk_not_in_empty_list)

class ForUpdateErrorNotOccurringTest(TestCase):
	"""
	Previously there was a bug where if you did a delete on an object in a permisionview, while at the same time you
	also had a view scope that depended on a nullable field, then a SQL error would occur during the deletion:


	"FOR UPDATE cannot be applied to the nullable side of an outer join"

	"""
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
			('testapp.view_country', 'all'),
			('testapp.view_citystate', 'netherlands'),
			('testapp.delete_citystate', 'all'),
		],
	})
	def test_for_update_bug_not_occurs_on_deletion(self):
		country = Country.objects.create(name='Netherlands')
		city_state = CityState.objects.create(name='Luxembourg', country=country)

		res = self.client.delete(f'/city_state/{city_state.id}/')

		self.assertEqual(204, res.status_code)

	@override_settings(BINDER_PERMISSION={
		'testapp.view_country': [
			('testapp.view_country', 'all'),
			('testapp.view_citystate', 'netherlands'),
			('testapp.delete_citystate', 'all'),
			('testapp.change_citystate', 'all'),
		],
	})
	def test_for_update_bug_not_occurs_on_put(self):
		# Same bug occurred with a put request
		country = Country.objects.create(name='Netherlands')
		city_state = CityState.objects.create(name='Luxembourg', country=country)

		res = self.client.put(f'/city_state/{city_state.id}/', data=jsondumps({
		}))
		print(res.json())

		self.assertEqual(200, res.status_code)

class TestColumnScoping(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser_for_not_all_fields', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser_for_not_all_fields', password='test')
		self.assertTrue(r)

		self.zoo: Zoo = Zoo.objects.create(name='Artis')


	def test_column_scoping_excludes_columns(self):
		res = self.client.get('/zoo/{}/'.format(self.zoo.id))
		self.assertEqual(res.status_code, 200)

		columns = jsonloads(res.content)['data'].keys()

		for field in ['name', 'founding_date', 'django_picture']:
			self.zoo._meta.get_field(field) # check if those fields exist, otherwise throw error
			self.assertFalse(field in columns)

		self.assertFalse('zoo_name' in columns)
		self.assertFalse('animal_count' in columns)


	def test_column_scoping_includes_columns(self):
		res = self.client.get('/zoo/{}/'.format(self.zoo.id))
		self.assertEqual(res.status_code, 200)

		columns = jsonloads(res.content)['data'].keys()

		for field in ['id', 'floor_plan']:
			self.zoo._meta.get_field(field)
			self.assertTrue(field in columns)

		self.assertTrue('another_zoo_name' in columns)
		self.assertTrue('another_animal_count' in columns)
