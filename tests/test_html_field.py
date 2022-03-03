from django.contrib.auth.models import User
from django.test import TestCase, Client

import json
from .testapp.models import Zoo, WebPage


class HtmlFieldTestCase(TestCase):

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

		self.webpage = WebPage.objects.create(zoo=self.zoo, content='')



	def test_save_normal_text_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/', data=json.dumps({'content': 'Artis'}))
		self.assertEqual(response.status_code, 200)

	def test_simple_html_is_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<h1>Artis</h1><b><p>Artis is a zoo in amsterdam</a>'}))
		self.assertEqual(response.status_code, 200)

	def test_wrong_attribute_not_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<b onclick="">test</b>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)
		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('invalid_attribute', parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])

	def test_simple_link_is_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/', data=json.dumps(
			{'content': '<a href="https://www.artis.nl/en/" rel="noreferrer noopener">Visit artis website</a>'}))

		self.assertEqual(response.status_code, 200)



	def test_javascript_link_is_not_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({
													   'content': '<a href="javascrt:alert(document.cookie)" rel="noreferrer noopener">Visit artis website</a>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)
		self.assertEqual('ValidationError', parsed_response['code'])

		self.assertEqual('invalid_attribute', parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])



	def test_script_is_not_ok(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<script>alert(\'hoi\');</script>'}))

		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)
		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('invalid_tag', parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])

	def test_script_is_not_ok_nested(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<b><script>alert(\'hoi\');</script></b>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)
		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('invalid_tag', parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])


	def test_can_handle_reallife_data(self):
		"""
		This is the worst case that we could produce on the WYIWYG edittor
		"""
		content = '<p>normal text</p><p><br></p><h1>HEADing 1</h1><p><br></p><h2>HEADING 2</h2><h3><br></h3><h3>HEADING 3</h3><p><br></p><p><strong>bold</strong></p><p><br></p><p><em>italic</em></p><p><br></p><p><u>underlined</u></p><p><br></p><p><a href=\"http://codeyellow.nl\" rel=\"noopener noreferrer\" target=\"_blank\">Link</a></p><p><br></p><ol><li>ol1</li><li>ol2</li></ol><ul><li>ul1</li><li>ul2</li></ul><p><br></p><p>subscripttgege</p><p>g</p>"'
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': content}))

		self.assertEqual(response.status_code, 200)

	def test_multiple_errors(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({
									   'content': '<foo><bar>Visit artis website</foo></bar>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)
		self.assertEqual('ValidationError', parsed_response['code'])


		self.assertEqual('invalid_tag',
						 parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])
		self.assertEqual('invalid_tag',
						 parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][1]['code'])


	def test_link_no_rel_errors(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<a href="https://codeyellow.nl">bla</a>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)

		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('missing_attribute',
						 parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])

	def test_link_noopener_required(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<a href="https://codeyellow.nl" rel="noreferrer">bla</a>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)

		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('invalid_attribute',
						 parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])

	def test_link_noreferrer_required(self):
		response = self.client.put(f'/web_page/{self.webpage.id}/',
								   data=json.dumps({'content': '<a href="https://codeyellow.nl" rel="noopener">bla</a>'}))
		self.assertEqual(response.status_code, 400)

		parsed_response = json.loads(response.content)

		self.assertEqual('ValidationError', parsed_response['code'])
		self.assertEqual('invalid_attribute',
						 parsed_response['errors']['web_page'][f'{self.webpage.id}']['content'][0]['code'])
