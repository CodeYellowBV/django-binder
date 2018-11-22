import json
from PIL import Image
from os import urandom
from tempfile import NamedTemporaryFile

from django.test import TestCase, Client
from django.core.files import File
from django.contrib.auth.models import User

from ..testapp.models import Picture, Animal



class ImageTest(TestCase):
	image_name = 'file'
	image_backup_name = 'original_file'

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	@staticmethod
	def image(width, height):
		return Image.frombytes('RGB', (width, height), urandom(width * height * 3))

	@staticmethod
	def temp_imagefile(width, height, format):
		i = ImageTest.image(width, height)
		f = NamedTemporaryFile(suffix='.jpg')
		i.save(f, format)
		f.seek(0)
		return f

	def _get_picture(self, width, height):
		animal = Animal()
		animal.save()

		file = ImageTest.temp_imagefile(width, height, 'jpeg')

		picture = Picture(
			animal=animal,
		)
		picture.file.save('picture.jpg', File(file), save=False)
		picture.original_file.save('picture_copy.jpg', File(file), save=False)
		picture.save()
		return picture


	def testRotate(self):
		picture = self._get_picture(50, 100)
		result = self.client.patch('/picture/rotate/', data=json.dumps({"ids": [picture.id], "angle": -90}))

		self.assertEqual(200, result.status_code)

		original_file = Image.open(picture.original_file)
		file = Image.open(picture.file)
		self.assertEqual((100, 50), file.size)
		self.assertEqual((50, 100), original_file.size)
		picture.original_file.close()
		picture.file.close()

	def testCrop(self):
		picture = self._get_picture(50, 100)
		result = self.client.patch('/picture/crop/', data=json.dumps({
			"ids": [picture.id], "x_1": 10,
			"x_2": 40, "y_1": 20, "y_2": 30
		}))
		self.assertEqual(200, result.status_code)

		original_file = Image.open(picture.original_file)
		file = Image.open(picture.file)
		self.assertEqual((30, 10), file.size)
		self.assertEqual((50, 100), original_file.size)
		picture.original_file.close()
		picture.file.close()

	def testReset(self):
		picture = self._get_picture(50, 100)
		result = self.client.patch('/picture/crop/', data=json.dumps({
			"ids": [picture.id], "x_1": 10,
			"x_2": 40, "y_1": 20, "y_2": 30
		}))
		self.assertEqual(200, result.status_code)
		result = self.client.patch('/picture/reset/', data=json.dumps({"ids": [picture.id]}))
		self.assertEqual(200, result.status_code)

		original_file = Image.open(picture.original_file)
		file = Image.open(picture.file)
		self.assertEqual((50, 100), file.size)
		self.assertEqual((50, 100), original_file.size)
		picture.original_file.close()
		picture.file.close()
