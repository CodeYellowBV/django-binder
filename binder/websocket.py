from msilib.schema import Error
from time import sleep
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

        for listing in self.room_listings:
            rooms += listing(user)

        return rooms


def singleton(get_instance):
    instance = None

    def get_singleton():
        nonlocal instance
        if instance is None:
            instance = get_instance()
        return instance

    return get_singleton


@singleton
def get_channel():
    import pika
    connection_credentials = pika.PlainCredentials(
        settings.HIGH_TEMPLAR['rabbitmq']['username'],
        settings.HIGH_TEMPLAR['rabbitmq']['password'],
    )
    connection_parameters = pika.ConnectionParameters(
        settings.HIGH_TEMPLAR['rabbitmq']['host'],
        credentials=connection_credentials,
    )
    state = { 'value': 0 }

    def on_open():
        state['value'] = 1

    def on_fail_open():
        state['value'] = -1
    
    connection = pika.SelectConnection(
        parameters=connection_parameters,
        on_open_callback=on_open,
        on_open_error_callback=on_fail_open
    )

    while state['value'] == 0:
        sleep(0.5)

    if state['value'] != 1:
        raise Error('Failed to open pika SelectConnection')
        # TODO Test this approach
    return connection.channel()


def trigger(data, rooms):
    if 'rabbitmq' in getattr(settings, 'HIGH_TEMPLAR', {}):
        channel = get_channel()
        channel.basic_publish('hightemplar', routing_key='*', body=jsondumps({
            'data': data,
            'rooms': rooms,
        }))
    if getattr(settings, 'HIGH_TEMPLAR_URL', None):
        url = getattr(settings, 'HIGH_TEMPLAR_URL')
        try:
            requests.post('{}/trigger/'.format(url), data=jsondumps({
                'data': data,
                'rooms': rooms,
            }))
        except RequestException:
            pass
