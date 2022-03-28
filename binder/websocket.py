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


#def singleton(get_instance):
#    instance = None
#
#    def get_singleton():
#        nonlocal instance
#        if instance is None:
#            instance = get_instance()
#        return instance
#
#    return get_singleton
#
#
#@singleton
#def get_channel():
#    import pika
#    connection_credentials = pika.PlainCredentials(
#        settings.HIGH_TEMPLAR['rabbitmq']['username'],
#        settings.HIGH_TEMPLAR['rabbitmq']['password'],
#    )
#    connection_parameters = pika.ConnectionParameters(
#        settings.HIGH_TEMPLAR['rabbitmq']['host'],
#        credentials=connection_credentials,
#    )
#    connection = pika.BlockingConnection(parameters=connection_parameters)
#    return connection.channel()

_connection = None 
def get_rabbitmq_connection(force_refresh=False):
    global _connection
    if not _connection or force_refresh:
        import pika
        connection_credentials = pika.PlainCredentials(
            settings.HIGH_TEMPLAR['rabbitmq']['username'],
            settings.HIGH_TEMPLAR['rabbitmq']['password'],
        )
        connection_parameters = pika.ConnectionParameters(
            settings.HIGH_TEMPLAR['rabbitmq']['host'],
            credentials=connection_credentials,
        )
        _connection = pika.BlockingConnection(parameters=connection_parameters)

    return _connection


    



def trigger(data, rooms):
    if 'rabbitmq' in getattr(settings, 'HIGH_TEMPLAR', {}):
        from pika.exceptions import ConnnectionClosed
        try:
            connection = get_rabbitmq_connection()
            # Handle heartbeat
            connection.process_data_events()
        except ConnnectionClosed:
            connection= get_rabbitmq_connection(force_refresh=True)

        channel = connection.channel()
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
