from django.test import TestCase, Client
from django.contrib.auth.models import User
from unittest import mock
from binder.views import JsonResponse
from .testapp.urls import room_controller
from .testapp.models import Animal, Costume
import requests
import json


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
	def test_post_save_trigger(self, mock):
		doggo = Animal(name='Woofer')
		doggo.full_clean()
		doggo.save()

		costume = Costume(nickname='Gnarls Barker', description='Foo Bark', animal=doggo)
		costume.full_clean()
		costume.save()
		self.assertEqual(1, requests.post.call_count)
		mock.assert_called_with('http://localhost:8002/trigger/', data=json.dumps({
				'data': {'id': doggo.id},
				'rooms': [{'costume': doggo.id}]
			}))

	def test_post_succeeds_when_trigger_fails(self):
		doggo = Animal(name='Woofer')
		doggo.full_clean()
		doggo.save()

		costume = Costume(nickname='Gnarls Barker', description='Foo Bark', animal=doggo)
		costume.full_clean()
		costume.save()

		self.assertIsNotNone(costume.pk)
