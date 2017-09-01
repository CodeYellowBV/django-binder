from django.test import TestCase
from .testapp.urls import room_controller


class MockUser:
	def __init__(self, costumes):
		self.costumes = costumes


class WebsocketTest(TestCase):
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
		from pudb import set_trace; set_trace()

		rooms = room_controller.list_rooms_for_user(user)
		self.assertCountEqual(allowed_rooms, rooms)
