import pathlib
import pika

from django.conf import settings
from threading import Semaphore, Thread


RABBITMQ_CONSUMER_PATH = pathlib.Path(__file__).absolute()


def _rabbitmq_thread_function(consumer):
    (produced_payload_semaphore, consumed_payload_semaphore, produced_payload) = consumer

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
        has_task = produced_payload_semaphore.acquire(timeout=0.01)
        if has_task:
            channel.basic_publish('hightemplar', routing_key='*', body=produced_payload[0])
            consumed_payload_semaphore.release()
        connection.process_data_events(0)

def _consumer_setup():
    produced_payload_semaphore = Semaphore(0)
    consumed_payload_semaphore = Semaphore(0)
    produced_payload = [None]

    consumer = (produced_payload_semaphore, consumed_payload_semaphore, produced_payload)

    rabbitmq_thread = Thread(target=lambda: _rabbitmq_thread_function(consumer))
    rabbitmq_thread.setDaemon(True)
    rabbitmq_thread.start()

    return consumer

def _consume(consumer, payload):
    (produced_payload_semaphore, consumed_payload_semaphore, produced_payload) = consumer

    produced_payload[0] = payload
    produced_payload_semaphore.release()
    consumed_payload_semaphore.acquire()

def main():
    from inter_process_producers_consumer import try_run_consumer

    try_run_consumer('rabbitmq-consumer.lock', _consumer_setup, _consume)

if __name__ == '__main__':
    main()
