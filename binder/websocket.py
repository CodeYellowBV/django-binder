from time import sleep
from threading import Thread
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


use_channel_queue = None
def use_channel(use_function):
    global use_channel_queue

    if use_channel_queue is None:
        use_channel_queue = []

        def connection_thread_function():
            import pika
            connection_credentials = pika.PlainCredentials(
                settings.HIGH_TEMPLAR['rabbitmq']['username'],
                settings.HIGH_TEMPLAR['rabbitmq']['password'],
            )
            connection_parameters = pika.ConnectionParameters(
                settings.HIGH_TEMPLAR['rabbitmq']['host'],
                credentials=connection_credentials,
            )
            connection = pika.BlockingConnection(parameters=connection_parameters)
            channel = connection.channel()

            while True:
                for use_function in use_channel_queue:
                    use_function(channel)
                use_channel_queue.clear()
                connection.sleep(0.1)

        connection_thread = Thread(target=connection_thread_function)
        connection_thread.setDaemon(True)
        connection_thread.start()

    use_channel_queue.append(use_function)
    while len(use_channel_queue) > 0:
        sleep(0.11)

def trigger(data, rooms):
    if 'rabbitmq' in getattr(settings, 'HIGH_TEMPLAR', {}):
        def use_function(channel):
            channel.basic_publish('hightemplar', routing_key='*', body=jsondumps({
                'data': data,
                'rooms': rooms,
            }))
        use_channel(use_function)
        
    if getattr(settings, 'HIGH_TEMPLAR_URL', None):
        url = getattr(settings, 'HIGH_TEMPLAR_URL')
        try:
            requests.post('{}/trigger/'.format(url), data=jsondumps({
                'data': data,
                'rooms': rooms,
            }))
        except RequestException:
            pass
