from django.test import TestCase, Client
from django.core.files.base import ContentFile
from django.contrib.auth.models import User

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
		zoo.picture = ContentFile(CONTENT, name='pic.jpg')
		self.assertEqual(zoo.picture.content_type, 'image/jpeg')
		self.assertEqual(zoo.picture.content_hash, HASH)
		zoo.save()

		zoo2 = Zoo.objects.get(pk=zoo.pk)
		self.assertEqual(zoo2.picture.content_type, 'image/jpeg')
		self.assertEqual(zoo2.picture.content_hash, HASH)

	def test_get(self):
		zoo = Zoo(name='Apenheul')
		zoo.picture = ContentFile(CONTENT, name='pic.jpg')
		zoo.save()

		response = self.client.get(f'/zoo/{zoo.pk}/')
		self.assertEqual(response.status_code, 200)
		data = jsonloads(response.content)
		self.assertEqual(
			data['data']['picture'],
			f'/zoo/{zoo.pk}/picture/pic.jpg?h={HASH}&content_type=image/jpeg',
		)
