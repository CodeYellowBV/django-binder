from PIL import Image
from os import urandom
from tempfile import NamedTemporaryFile
import io

from django.test import TestCase, Client
from django.core.files import File
from django.contrib.auth.models import User

from ..testapp.models import Picture, Animal, Caretaker
import csv

class CsvExportTest(TestCase):

	@staticmethod
	def image(width, height):
		return Image.frombytes('RGB', (width, height), urandom(width * height * 3))

	@staticmethod
	def temp_imagefile(width, height, format):
		i = CsvExportTest.image(width, height)
		f = NamedTemporaryFile(suffix='.jpg')
		i.save(f, format)
		f.seek(0)
		return f

	def setUp(self):
		animal = Animal(name='test')
		animal.save()

		self.pictures = []

		for i in range(3):
			picture = Picture(animal=animal)
			file = CsvExportTest.temp_imagefile(50, 50, 'jpeg')
			picture.file.save('picture.jpg', File(file), save=False)
			picture.original_file.save('picture_copy.jpg', File(file), save=False)
			picture.save()
			self.pictures.append(picture)

		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def testSimpleDownload(self):
		response = self.client.get('/picture/download/')
		self.assertEqual(200, response.status_code)
		response_data = csv.reader(io.StringIO(response.content.decode("utf-8")))

		data = list(response_data)

		# First line needs to be the header
		self.assertEqual(data[0], ['picture identifier', 'animal identifier', 'squared picture identifier'])

		# All other data needs to be ordered using the default ordering (by id, asc)
		self.assertEqual(data[1], [str(self.pictures[0].id), str(self.pictures[0].animal_id), str(self.pictures[0].id ** 2)])
		self.assertEqual(data[2], [str(self.pictures[1].id), str(self.pictures[1].animal_id), str(self.pictures[1].id ** 2)])
		self.assertEqual(data[3], [str(self.pictures[2].id), str(self.pictures[2].animal_id), str(self.pictures[2].id ** 2)])

	def test_download_extra_params(self):
		caretaker_1 = Caretaker(name='Foo')
		caretaker_1.save()
		caretaker_2 = Caretaker(name='Bar')
		caretaker_2.save()
		caretaker_3 = Caretaker(name='Baz')
		caretaker_3.save()

		response = self.client.get('/caretaker/download/')
		self.assertEqual(200, response.status_code)
		response_data = csv.reader(io.StringIO(response.content.decode("utf-8")))

		data = list(response_data)

		# First line needs to be the header
		self.assertEqual(data[0], ['ID', 'Name', 'Scary'])

		# All other data needs to be ordered using the default ordering (by id, asc)
		self.assertEqual(data[1], [str(caretaker_1.id), 'Foo', 'boo!'])
		self.assertEqual(data[2], [str(caretaker_2.id), 'Bar', 'boo!'])
		self.assertEqual(data[3], [str(caretaker_3.id), 'Baz', 'boo!'])
