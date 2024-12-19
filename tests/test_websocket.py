from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest import mock
from binder.views import JsonResponse
from binder.websocket import trigger
from .testapp.urls import room_controller
from .testapp.models import Animal, Costume
import requests
import json
from django.test import override_settings


class MockUser:
	def __init__(self, costumes):
		self.costumes = costumes


def mock_post_high_templar(*args, **kwargs):
	return JsonResponse({'ok': True})


class WebsocketTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_room_controller_list_rooms_for_user(self):
		allowed_rooms = [
			{
				'zoo': 'all',
			},
			{
				'costume': 1337,
			},
			{
				'costume': 1338,
			}
		]

		user = MockUser([1337, 1338])

		rooms = room_controller.list_rooms_for_user(user)
		self.assertCountEqual(allowed_rooms, rooms)

	@mock.patch('requests.post', side_effect=mock_post_high_templar)
	@override_settings(HIGH_TEMPLAR_URL="http://localhost:8002")
	def test_post_save_trigger(self, mock):
		doggo = Animal(name='Woofer')
		doggo.save()

		costume = Costume(nickname='Gnarls Barker', description='Foo Bark', animal=doggo)
		costume.save()
		self.assertEqual(1, requests.post.call_count)
		mock.assert_called_with('http://localhost:8002/trigger/', data=json.dumps({
				'data': {'id': doggo.id},
				'rooms': [{'costume': doggo.id}]
			}))

	def test_post_succeeds_when_trigger_fails(self):
		doggo = Animal(name='Woofer')
		doggo.save()

		costume = Costume(nickname='Gnarls Barker', description='Foo Bark', animal=doggo)
		costume.save()

		self.assertIsNotNone(costume.pk)


class TriggerConnectionCloseTest(TestCase):
	@override_settings(
		HIGH_TEMPLAR={
			'rabbitmq': {
				'host': 'localhost',
				'username': 'guest',
				'password': 'guest'
			}
		}
	)
	@mock.patch('pika.BlockingConnection')
	def test_trigger_calls_connection_close(self, mock_connection_class):
		mock_connection = mock_connection_class.return_value
		mock_connection.is_closed = False

		data = {'id': 123}
		rooms = [{'costume': 123}]

		trigger(data, rooms)

		mock_connection.close.assert_called_once()

