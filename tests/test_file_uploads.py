import json
import mimetypes

from django.test import TestCase, Client
from django.test.client import encode_multipart
from django.core.files import File
from django.contrib.auth.models import User

from binder.json import jsonloads

from .testapp.models import Animal, Zoo
from .utils import temp_imagefile


class FileUploadTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	# Clean up uploaded files
	def tearDown(self):
		Zoo.objects.all().delete()


	def test_get_model_with_file(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')

		with temp_imagefile(100, 200, 'jpeg') as file:
			emmen.floor_plan.save('plan.jpg', File(file), save=False)
			emmen.save()

		response = self.client.get('/zoo/%d/' % emmen.id)
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(emmen.id, result['data']['id'])
		self.assertEqual(emmen.name, result['data']['name'], 'Wildlands Adventure Zoo Emmen')
		self.assertEqual('/zoo/%d/floor_plan/' % emmen.id, result['data']['floor_plan'])


	# This is a basic regression test for a bug due to the router
	# singleton refactor, GET would crash if the model simply
	# _contained_ a file attribute.
	def test_get_related_model_with_file(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')

		with temp_imagefile(100, 200, 'jpeg') as file:
			emmen.floor_plan.save('plan.jpg', File(file), save=False)
			emmen.save()

		donald = Animal(name='Donald Duck', zoo=emmen)
		donald.save()

		response = self.client.get('/animal/%d/' % donald.id, data={'with': 'zoo'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(donald.id, result['data']['id'])
		self.assertEqual({'zoo': 'zoo'}, result['with_mapping'])
		self.assertEqual({'zoo': 'animals'}, result['with_related_name_mapping'])

		zoo = result['with']['zoo'][0]
		self.assertEqual(emmen.id, zoo['id'])
		self.assertEqual(emmen.name, zoo['name'], 'Wildlands Adventure Zoo Emmen')
		self.assertEqual('/zoo/%d/floor_plan/' % emmen.id, zoo['floor_plan'])


	# Same as above, but in multi-put's code path
	def test_multi_put_model_with_existing_file(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')

		with temp_imagefile(100, 200, 'jpeg') as file:
			emmen.floor_plan.save('plan.jpg', File(file), save=False)
			emmen.save()

		model_data = {
			'data': [{
				'id': emmen.id,
				'name': 'Wildlands!',
			}]
		}
		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')

		self.assertEqual(response.status_code, 200)


	def test_upload_to_file_field_stores_file(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.save()

		with temp_imagefile(100, 200, 'jpeg') as uploaded_file:
			response = self.client.post('/zoo/%s/floor_plan/' % emmen.id, data={'file': uploaded_file})
			self.assertEqual(response.status_code, 200)

			emmen.refresh_from_db()
			uploaded_file.seek(0)
			self.assertTrue(emmen.floor_plan)
			with emmen.floor_plan.file as current_file:
				self.assertEqual(uploaded_file.read(), current_file.read())

		# overwrite with new one
		with temp_imagefile(10, 20, 'jpeg') as replacement_file:
			response = self.client.post('/zoo/%s/floor_plan/' % emmen.id, data={'file': replacement_file})
			self.assertEqual(response.status_code, 200)

			emmen.refresh_from_db()
			replacement_file.seek(0)
			self.assertTrue(emmen.floor_plan)
			with emmen.floor_plan.file as current_file:
				self.assertEqual(replacement_file.read(), current_file.read())


	def test_upload_triggers_file_field_validation_errors(self):
		emmen = Zoo(name='Nowhere')
		emmen.save()

		with temp_imagefile(100, 200, 'jpeg') as uploaded_file:
			response = self.client.post('/zoo/%s/floor_plan/' % emmen.id, data={'file': uploaded_file})
			self.assertEqual(response.status_code, 400)

			returned_data = jsonloads(response.content)
			self.assertEqual(len(returned_data['errors']), 1)
			self.assertEqual(len(returned_data['errors']['zoo']), 1)
			self.assertSetEqual(set(['floor_plan', 'name']), set(returned_data['errors']['zoo'][str(emmen.id)].keys()))
			self.assertEqual('no plan', returned_data['errors']['zoo'][str(emmen.id)]['floor_plan'][0]['code'])
			self.assertEqual('nowhere', returned_data['errors']['zoo'][str(emmen.id)]['name'][0]['code'])

			emmen.refresh_from_db()
			self.assertFalse(emmen.floor_plan)


	def test_upload_size_resized_png(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.save()

		with temp_imagefile(600, 600, 'png') as uploaded_file:
			response = self.client.post('/zoo/%s/floor_plan/' % emmen.id, data={'file': uploaded_file})
		self.assertEqual(response.status_code, 200)

		emmen.refresh_from_db()
		content_type = mimetypes.guess_type(emmen.floor_plan.path)[0]
		self.assertEqual(content_type, 'image/jpeg')
		self.assertEqual(emmen.floor_plan.width, 500)
		self.assertEqual(emmen.floor_plan.height, 500)


	def test_upload_size_resized_jpeg(self):
		emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		emmen.save()

		with temp_imagefile(600, 600, 'jpeg') as uploaded_file:
			response = self.client.post('/zoo/%s/floor_plan/' % emmen.id, data={'file': uploaded_file})
		self.assertEqual(response.status_code, 200)

		emmen.refresh_from_db()
		content_type = mimetypes.guess_type(emmen.floor_plan.path)[0]
		self.assertEqual(content_type, 'image/jpeg')
		self.assertEqual(emmen.floor_plan.width, 500)
		self.assertEqual(emmen.floor_plan.height, 500)

	def test_upload_file_in_post(self):
		with temp_imagefile(500, 500, 'jpeg') as uploaded_file:
			response = self.client.post('/zoo/', data={
				'data': json.dumps({
					'name': 'Wildlands Adventure Zoo Emmen',
					'floor_plan': None,
				}),
				'file:floor_plan': uploaded_file,
			})
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		emmen = Zoo.objects.get(pk=data['id'])
		content_type = mimetypes.guess_type(emmen.floor_plan.path)[0]
		self.assertEqual(content_type, 'image/jpeg')
		self.assertEqual(emmen.floor_plan.width, 500)
		self.assertEqual(emmen.floor_plan.height, 500)

	def test_upload_file_in_multiput(self):
		with temp_imagefile(500, 500, 'jpeg') as uploaded_file:
			boundary = 'my-boundary'
			content_type = 'multipart/form-data; boundary=' + boundary
			data = encode_multipart(boundary, {
				'data': json.dumps({
					'data': [{
						'id': -1,
						'name': 'Wildlands Adventure Zoo Emmen',
						'floor_plan': None,
					}],
				}),
				'file:data.0.floor_plan': uploaded_file,
			})
			response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		emmen = Zoo.objects.get(pk=dict(data['idmap']['zoo'])[-1])
		content_type = mimetypes.guess_type(emmen.floor_plan.path)[0]
		self.assertEqual(content_type, 'image/jpeg')
		self.assertEqual(emmen.floor_plan.width, 500)
		self.assertEqual(emmen.floor_plan.height, 500)

	def test_upload_no_data(self):
		boundary = 'my-boundary'
		content_type = 'multipart/form-data; boundary=' + boundary
		data = encode_multipart(boundary, {})
		response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 418)
		data = jsonloads(response.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'data field is required in multipart body')

	def test_upload_invalid_data(self):
		boundary = 'my-boundary'
		content_type = 'multipart/form-data; boundary=' + boundary
		data = encode_multipart(boundary, {
			'data': 'not valid json',
		})
		response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 418)
		data = jsonloads(response.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'JSON parse error: Expecting value: line 1 column 1 (char 0).')

	def test_upload_non_existing_file_path(self):
		with temp_imagefile(500, 500, 'jpeg') as uploaded_file:
			boundary = 'my-boundary'
			content_type = 'multipart/form-data; boundary=' + boundary
			data = encode_multipart(boundary, {
				'data': json.dumps({
					'data': [{
						'id': -1,
						'name': 'Wildlands Adventure Zoo Emmen',
						'floor_plan': None,
					}],
				}),
				'file:data.1.floor_plan': uploaded_file,
			})
			response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 418)
		data = jsonloads(response.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'unexpected key at path: data.1')

	def test_upload_non_integer_key_at_list(self):
		with temp_imagefile(500, 500, 'jpeg') as uploaded_file:
			boundary = 'my-boundary'
			content_type = 'multipart/form-data; boundary=' + boundary
			data = encode_multipart(boundary, {
				'data': json.dumps({
					'data': [{
						'id': -1,
						'name': 'Wildlands Adventure Zoo Emmen',
						'floor_plan': None,
					}],
				}),
				'file:data.foo.floor_plan': uploaded_file,
			})
			response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 418)
		data = jsonloads(response.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'expected integer key at path: data.foo')

	def test_upload_not_null_at_path(self):
		with temp_imagefile(500, 500, 'jpeg') as uploaded_file:
			boundary = 'my-boundary'
			content_type = 'multipart/form-data; boundary=' + boundary
			data = encode_multipart(boundary, {
				'data': json.dumps({
					'data': [{
						'id': -1,
						'name': 'Wildlands Adventure Zoo Emmen',
						'floor_plan': 'foo',
					}],
				}),
				'file:data.0.floor_plan': uploaded_file,
			})
			response = self.client.put('/zoo/', content_type=content_type, data=data)
		self.assertEqual(response.status_code, 418)
		data = jsonloads(response.content)
		self.assertEqual(data['code'], 'RequestError')
		self.assertEqual(data['message'], 'expected null at path: data.0.floor_plan')
