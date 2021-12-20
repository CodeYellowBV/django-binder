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


CONTENT = b'een foto met die stenen gorilla bij de ingang'
HASH = '0759a35e9983833ce52fe433d2326addf400f344'


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
		zoo.binder_picture = ContentFile(CONTENT, name='pic.jpg')
		self.assertEqual(zoo.binder_picture.content_type, 'image/jpeg')
		self.assertEqual(zoo.binder_picture.content_hash, HASH)
		zoo.save()

		zoo2 = Zoo.objects.get(pk=zoo.pk)
		self.assertEqual(zoo2.binder_picture.content_type, 'image/jpeg')
		self.assertEqual(zoo2.binder_picture.content_hash, HASH)

	def test_post(self):
		filename = 'pic.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture/' % zoo.id, data={
			'file': ContentFile(CONTENT, name=filename),
		})
		self.assertEqual(response.status_code, 200)
		content = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			content['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
		)

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
		)

	def test_post_no_extension(self):
		filename = 'foobar'
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture/' % zoo.id, data={
			'file': ContentFile(CONTENT, name=filename),
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
			'file': ContentFile(CONTENT, name=filename),
		})
		self.assertEqual(response.status_code, 200)
		content = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			content['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
		)

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
		)

	def test_get(self):
		filename = 'pic.jpg'
		zoo = Zoo(name='Apenheul')
		zoo.binder_picture = ContentFile(CONTENT, name=filename)
		zoo.save()

		response = self.client.get('/zoo/{}/'.format(zoo.pk))
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)

		# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
		zoo.refresh_from_db()
		filename = basename(zoo.binder_picture.name) # Without folders foo/bar/

		self.assertEqual(
			data['data']['binder_picture'],
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
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
			file.write(CONTENT)

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
			'/zoo/{}/binder_picture/?h={}&content_type=image/jpeg&filename={}'.format(zoo.pk, HASH, filename),
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
			with self.assertWarns(ResourceWarning):
				response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
					'file': ContentFile(CONTENT, name='foobar.png'),
				})

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
		zoo.django_picture_not_null = ContentFile(CONTENT, name='pic.jpg')
		zoo.binder_picture_not_null = ContentFile(CONTENT, name='pic.jpg')
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
			'file': ContentFile(CONTENT, name='foobar.jpg'),
		})

		self.assertEqual(response.status_code, 400)
		content = jsonloads(response.content)
		self.assertEqual(content['code'], 'FileTypeIncorrect')
		self.assertEqual(content['allowed_types'], [{"extension": "png"}])

	def test_post_without_extension_fails(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		response = self.client.post('/zoo/%s/binder_picture_custom_extensions/' % zoo.id, data={
			'file': ContentFile(CONTENT, name='foobar'),
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
					'file': ContentFile(CONTENT, name=filename),
				})
				self.assertEqual(response.status_code, 200)
				content = jsonloads(response.content)

				# Remove once Django 3 lands with: https://docs.djangoproject.com/en/3.1/howto/custom-file-storage/#django.core.files.storage.get_alternative_name
				zoo.refresh_from_db()
				filename = basename(zoo.binder_picture_custom_extensions.name) # Without folders foo/bar/



				self.assertEqual(
					content['data']['binder_picture_custom_extensions'],
					'/zoo/{}/binder_picture_custom_extensions/?h={}&content_type=image/png&filename={}'.format(zoo.pk, HASH, filename),
				)

				response = self.client.get('/zoo/{}/'.format(zoo.pk))
				self.assertEqual(response.status_code, 200)
				data = jsonloads(response.content)
				self.assertEqual(
					data['data']['binder_picture_custom_extensions'],
					'/zoo/{}/binder_picture_custom_extensions/?h={}&content_type=image/png&filename={}'.format(zoo.pk, HASH, filename),
				)
