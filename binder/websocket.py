from django.conf import settings
from .json import jsondumps
import requests
from requests.exceptions import RequestException

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
	url = getattr(settings, 'HIGH_TEMPLAR_URL', 'http://localhost:8002')

	try:
		requests.post('{}/trigger/'.format(url), data=jsondumps({
			'data': data,
			'rooms': rooms,
		}))
	except RequestException:
		pass
