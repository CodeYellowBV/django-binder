from django.conf import settings
import requests

class RoomController(object):
	def __init__(self):
		self.room_listings = []

	def register(self, superclass):
		for view in superclass.__subclasses__():
			if view.register_for_model and view.model is not None:
				listing = getattr(view, 'get_rooms_for_user', None)

				if listing and callable(listing):
					self.room_listings.append(listing)

			self.register(view)

		return self

	def list_rooms_for_user(self, user):
		rooms = []

		for l in self.room_listings:
			rooms += l(user)

		return rooms

def trigger(data, rooms):
	url = getattr(settings, 'HIGH_TEMPLAR_URL', 'localhost')
	port = getattr(settings, 'HIGH_TEMPLAR_PORT', '8002')

	base_url = 'http://{}:{}'.format(url, port)
	return requests.post('{}/trigger/'.format(base_url), data={
			'data': data,
			'rooms': rooms,
		})
