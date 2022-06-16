from django.conf import settings

from .json import jsondumps
from binder.inter_process_producers_consumer import produce
from binder.rabbitmq import RABBITMQ_CONSUMER_PATH
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

        for listing in self.room_listings:
            rooms += listing(user)

        return rooms

# WARNING: When this is non-empty, the entire RabbitMQ connection will be mocked
mock_trigger_listeners = []

def trigger(data, rooms):
    if 'rabbitmq' in getattr(settings, 'HIGH_TEMPLAR', {}):
        global mock_trigger_listeners
        if len(mock_trigger_listeners) > 0:
            for trigger_listener in mock_trigger_listeners:
                trigger_listener(jsondumps({ 'data': data, 'rooms' : rooms }))
        else:
            rabbitmq_consumer_args = settings.HIGH_TEMPLAR['rabbitmq']['username'] + ' ' + settings.HIGH_TEMPLAR['rabbitmq']['password'] + ' ' + settings.HIGH_TEMPLAR['rabbitmq']['host']
            produce(jsondumps({ 'data': data, 'rooms': rooms }), RABBITMQ_CONSUMER_PATH, rabbitmq_consumer_args)
    if getattr(settings, 'HIGH_TEMPLAR_URL', None):
        url = getattr(settings, 'HIGH_TEMPLAR_URL')
        try:
            requests.post('{}/trigger/'.format(url), data=jsondumps({
                'data': data,
                'rooms': rooms,
            }))
        except RequestException:
            pass
