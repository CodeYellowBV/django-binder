from django.test import TestCase, Client

from .testapp.models import Zoo


class HandleExceptionsTest(TestCase):

	def test_res(self):
		self.assertEqual(Zoo.objects.count(), 0)

		client = Client()
		res = client.get('/handle_exceptions/', {'res': 'foo'})
		self.assertEqual(res.status_code, 200)
		self.assertEqual(res.content.decode(), 'foo')

		self.assertEqual(Zoo.objects.count(), 1)

	def test_err(self):
		self.assertEqual(Zoo.objects.count(), 0)

		client = Client()
		res = client.get('/handle_exceptions/')
		self.assertEqual(res.status_code, 418)

		self.assertEqual(Zoo.objects.count(), 0)

	def test_method_not_allowed(self):
		client = Client()
		res = client.post('/handle_exceptions/')
		self.assertEqual(res.status_code, 405)
