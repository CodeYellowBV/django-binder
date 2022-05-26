from threading import Semaphore, Thread
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


use_channel_function = None
sent_channel_task_semaphore = Semaphore(0)
finished_channel_task_semaphore = Semaphore(0)

def use_channel(use_function):
    global use_channel_function
    global sent_channel_task_semaphore
    global finished_channel_task_semaphore

    if use_channel_function is None:
        use_channel_function = [None]

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
                has_task = sent_channel_task_semaphore.acquire(timeout=0.01)
                if has_task:
                    use_channel_function[0](channel)
                    finished_channel_task_semaphore.release()
                connection.process_data_events(0)

        connection_thread = Thread(target=connection_thread_function)
        connection_thread.start()

    use_channel_function[0] = use_function
    sent_channel_task_semaphore.release()
    finished_channel_task_semaphore.acquire()

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
