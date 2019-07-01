import json
from os import urandom
from PIL import Image
from tempfile import NamedTemporaryFile
from django.test import TestCase, Client
import mimetypes

from binder.json import jsonloads
from django.core.files import File
from django.contrib.auth.models import User

from .testapp.models import Animal, Zoo

def image(width, height):
	return Image.frombytes('RGB', (width, height), urandom(width * height * 3))


IMG_SUFFIX = {
	'jpeg': '.jpg',
	'png': '.png',
}


def temp_imagefile(width, height, format):
	i = image(width, height)
	f = NamedTemporaryFile(suffix=IMG_SUFFIX[format])
	i.save(f, format)
	f.seek(0)
	return f


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
		print(response.content.decode())
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
