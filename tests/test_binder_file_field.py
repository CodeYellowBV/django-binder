from os.path import basename
from io import BytesIO
from PIL import Image
from tempfile import NamedTemporaryFile

from django.test import TestCase, Client
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.db import connection

from binder.json import jsonloads

from .testapp.models import Zoo
from .utils import temp_imagefile


JPG_CONTENT = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.\' ",#\x1c\x1c(7),01444\x1f\'9=82<.342\xff\xdb\x00C\x01\t\t\t\x0c\x0b\x0c\x18\r\r\x182!\x1c!22222222222222222222222222222222222222222222222222\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01"\x00\x02\x11\x01\x03\x11\x01\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x10\x00\x02\x01\x03\x03\x02\x04\x03\x05\x05\x04\x04\x00\x00\x01}\x01\x02\x03\x00\x04\x11\x05\x12!1A\x06\x13Qa\x07"q\x142\x81\x91\xa1\x08#B\xb1\xc1\x15R\xd1\xf0$3br\x82\t\n\x16\x17\x18\x19\x1a%&\'()*456789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe1\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf1\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xc4\x00\x1f\x01\x00\x03\x01\x01\x01\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xc4\x00\xb5\x11\x00\x02\x01\x02\x04\x04\x03\x04\x07\x05\x04\x04\x00\x01\x02w\x00\x01\x02\x03\x11\x04\x05!1\x06\x12AQ\x07aq\x13"2\x81\x08\x14B\x91\xa1\xb1\xc1\t#3R\xf0\x15br\xd1\n\x16$4\xe1%\xf1\x17\x18\x19\x1a&\'()*56789:CDEFGHIJSTUVWXYZcdefghijstuvwxyz\x82\x83\x84\x85\x86\x87\x88\x89\x8a\x92\x93\x94\x95\x96\x97\x98\x99\x9a\xa2\xa3\xa4\xa5\xa6\xa7\xa8\xa9\xaa\xb2\xb3\xb4\xb5\xb6\xb7\xb8\xb9\xba\xc2\xc3\xc4\xc5\xc6\xc7\xc8\xc9\xca\xd2\xd3\xd4\xd5\xd6\xd7\xd8\xd9\xda\xe2\xe3\xe4\xe5\xe6\xe7\xe8\xe9\xea\xf2\xf3\xf4\xf5\xf6\xf7\xf8\xf9\xfa\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00?\x00\xb5E\x14W\xc6\x9eq\xff\xd9'
PNG_CONTENT = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc0*K\x01\x00\x01\xea\x01\r1\x93\xfe`\x00\x00\x00\x00IEND\xaeB`\x82'
JPG_HASH = '7f6262521ea97a0dca86703b5fc90d648303f877'
PNG_HASH = '1888ce8ba1019738482c8dc3e30bea871b4e47e7'


class BinderFileFieldTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_save(self):
		zoo = Zoo(name='Apenheul')
		zoo.binder_picture = ContentFile(JPG_CONTENT, name='pic.jpg')
		self.assertEqual(zoo.binder_picture.content_type, 'image/jpeg')
		self.assertEqual(zoo.binder_picture.content_hash, JPG_HASH)
		zoo.save()

		zoo2 = Zoo.objects.get(pk=zoo.pk)
		self.assertEqual(zoo2.binder_picture.content_type, 'image/jpeg')
		self.assertEqual(zoo2.binder_picture.content_hash, JPG_HASH)

	def test_post(self):
		filename = 'pic.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture/' % zoo.id, data={
			'file': ContentFile(JPG_CONTENT, name=filename),
		})
		self.assertEqual(response.status_code, 200)
		content = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			content['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

	def test_post_no_extension(self):
		filename = 'foobar'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture/' % zoo.id, data={
			'file': ContentFile('foobar', name=filename),
		})

		self.assertEqual(response.status_code, 400)

		# # Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		# zoo.refresh_from_db()
		# filename = basename(zoo.binder_picture.name) # Without folders foo/bar/
		#
		# self.assertEqual(
		# 	content['data']['binder_picture'],
		# 	'/zoo/{}/binder_picture/?h={}&content_type=&filename={}'.format(zoo.pk, HASH, filename),
		# )
		#
		# response = self.client.get('/zoo/{}/'.format(zoo.pk))
		#
		# self.assertEqual(response.status_code, 200)
		# data = jsonloads(response.content)
		# self.assertEqual(
		# 	data['data']['binder_picture'],
		# 	'/zoo/{}/binder_picture/?h={}&content_type=&filename={}'.format(zoo.pk, HASH, filename),
		# )

	def test_post_with_long_filename(self):
		filename = 'this_is_an_extremely_long_filename_which_should_be_over_200_chars_but_under_400_and_im_running_out_of_things_to_say_and_i_guess_we_just_keep_going_and_im_now_in_poznan_working_onsite_perhaps_thats_interesting_and_just_ordered_pizza_for_lunch.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture/' % zoo.id, data={
			'file': ContentFile(JPG_CONTENT, name=filename),
		})
		self.assertEqual(response.status_code, 200)
		content = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			content['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

	def test_get(self):
		filename = 'pic.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.binder_picture = ContentFile(JPG_CONTENT, name=filename)
		zoo.save()

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

	def test_setting_blank(self):
		zoo = Zoo(name='Apenheul')
		zoo.binder_picture = ''
		zoo.save()

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertIsNone(data['data']['binder_picture'])

	def test_upgrade_from_normal_file_field_with_existing_data(self):
		filename = 'pic.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		with open(filename, 'wb+') as file:
			file.write(JPG_CONTENT)

		with connection.cursor() as cur:
			# Update db directly to mimic existing records.
			cur.execute("UPDATE {} set binder_picture='{}'".format(zoo._meta.db_table, file.name))

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = zoo.binder_picture.name

		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, JPG_HASH, filename),
		)

	def test_reusing_same_file_for_multiple_fields(self):
		with BytesIO() as bytesio:
			im = Image.new('RGBA', (50,100))
			im.save(bytesio, format='png')
			bytesio.seek(0)
			test_image = SimpleUploadedFile('test.png', bytesio.read())

		zoo1 = Zoo(name='Apenheul', django_picture=test_image)
		zoo1.save()
		zoo2 = Zoo(name='Apenheul', django_picture=test_image)
		zoo2.save()

		zoo3 = Zoo(name='Apenheul', binder_picture=test_image)
		zoo3.save()
		zoo4 = Zoo(name='Apenheul', binder_picture=test_image)
		zoo4.save()

	# I've seen this happen a few times, where a file exists in the db but not on disk.
	def test_non_existing_file_on_diks(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		with connection.cursor() as cur:
			# Update db directly to mimic record without existing file
			cur.execute("UPDATE {} set binder_picture='non-exisiting-pic.jpg'".format(zoo._meta.db_table))

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, '', 'non-exisiting-pic.jpg'),
		)

	def test_post_image_doesnt_leave_unclosed_file(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		# Basically this construction of assertRaise wrapped around assertWarns
		# is to make sure no warning is triggered. This works, since assertWarns
		# raises an AssertionError. Basically a `self.assertNotWarns`.
		with self.assertRaises(AssertionError) as cm:
			with self.assertWarns(ResourceWarning) as cm2:
				response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
					'file': ContentFile(PNG_CONTENT, name='foobar.png'),
				})
			print(cm2.warning)

		self.assertEqual(str(cm.exception), 'ResourceWarning not triggered')


class BinderFileFieldBlankNotNullableTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_setting_blank(self):
		zoo = Zoo(name='Apenheul')
		zoo.django_picture_not_null = ''
		zoo.binder_picture_not_null = ''
		zoo.save()

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertIsNone(data['data']['django_picture_not_null'])
		self.assertIsNone(data['data']['binder_picture_not_null'])

	# When a file field is blank=True and null=False, Django will convert the
	# None to empty string.
	def test_deleting(self):
		zoo = Zoo(name='Apenheul')
		zoo.django_picture_not_null = ContentFile(JPG_CONTENT, name='pic.jpg')
		zoo.binder_picture_not_null = ContentFile(JPG_CONTENT, name='pic.jpg')
		zoo.save()

		zoo.django_picture_not_null.delete()
		zoo.binder_picture_not_null.delete()

		zoo.refresh_from_db()
		self.assertEqual('', zoo.django_picture_not_null)
		self.assertEqual('', zoo.binder_picture_not_null)

class BinderFileFieldAllowedExtensionTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_post_allowed_extension_fail(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
			'file': ContentFile(JPG_CONTENT, name='foobar.jpg'),
		})

		self.assertEqual(response.status_code, 400)

	def test_post_without_extension_fails(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
			'file': ContentFile(PNG_CONTENT, name='foobar'),
		})

		self.assertEqual(response.status_code, 400)
		content = jsonloads(response.content)
		self.assertEqual(content['code'], 'FileTypeIncorrect')
		self.assertEqual(content['allowed_types'], [{"extension": "png"}])

	def test_post_allowed_extension_success(self):
		for filename in ['foobar.png', 'foobar.PNG', 'foobar.Png', 'foobar.pNg', 'foobar.pnG']:
			with self.subTest(filename=filename):
				zoo = Zoo(name='Apenheul')
				zoo.save()

				response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
					'file': ContentFile(PNG_CONTENT, name=filename),
				})
				self.assertEqual(response.status_code, 200)
				content = jsonloads(response.content)

				# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
				zoo.refresh_from_db()
				filename = basename(zoo.binder_picture_custom_extensions.name) # Without folders foo/bar/



				self.assertEqual(
					content['data']['binder_picture_custom_extensions'],
					'/zoo/{}/binder_picture_custom_extensions/?h={}&content_type=image/png&filename={}'.format(zoo.pk, PNG_HASH, filename),
				)

				response = self.client.get('/zoo/{}/'.format(zoo.pk))
				self.assertEqual(response.status_code, 200)
				data = jsonloads(response.content)
				self.assertEqual(
					data['data']['binder_picture_custom_extensions'],
					'/zoo/{}/binder_picture_custom_extensions/?h={}&content_type=image/png&filename={}'.format(zoo.pk, PNG_HASH, filename),
				)
