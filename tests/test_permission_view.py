from .compare import assert_json, EXTRA

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads, jsondumps

from .testapp.models import Zoo, ZooEmployee

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
