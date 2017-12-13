from binder.json import jsonloads

from django.test import TestCase, Client

class ApiCatchallTest(TestCase):
	def test_custom_endpoint_not_ignored_by_catchall(self):
		client = Client()
		response = client.get('/custom/route/')

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.content.decode(), '{"custom": true}')

	def test_catchall_encodes_invalid_uri_exception(self):
		client = Client()
		response = client.get('/nonexistent/endpoint/')

		self.assertEqual(response.status_code, 418)

		body = jsonloads(response.content)
		self.assertEqual(body.get('message'), 'Undefined URI for this API.')
		self.assertEqual(body.get('code'), 'InvalidURI')
		self.assertEqual(body.get('path'), '/nonexistent/endpoint/')
