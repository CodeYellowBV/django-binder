from django.contrib.auth.models import User
from django.test import TestCase, Client

from project.testapp.models import Zoo, WebPage


class AnnotationTestCase(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.zoo = Zoo(name='Apenheul')
		self.zoo.save()

		self.webpage = WebPage(zoo=self.zoo, content='')


	def test_save_normal_text_ok(self):
		self.webpage = WebPage(zoo=self.zoo, content='Artis')

