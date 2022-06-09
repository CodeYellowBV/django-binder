import pathlib
import pika

from threading import Semaphore, Thread


RABBITMQ_CONSUMER_PATH = pathlib.Path(__file__).absolute()


def _rabbitmq_thread_function(consumer):
    from utils import debug_log
    from sys import argv

    (produced_payload_semaphore, consumed_payload_semaphore, produced_payload) = consumer
    debug_log('rabbitmq_start', 'Started rabbitmq thread')

    rabbitmq_username = argv[1]
    rabbitmq_password = argv[2]
    rabbitmq_host = argv[3]

    debug_log('rabbitmq_arguments', 'username=' + rabbitmq_username + ' and password=' + rabbitmq_password + ' and host=' + rabbitmq_host)

    connection_credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    connection_parameters = pika.ConnectionParameters(rabbitmq_host, credentials=connection_credentials)

    connection = pika.BlockingConnection(parameters=connection_parameters)
    channel = connection.channel()
    debug_log('rabbitmq_open', 'Opened RabbitMQ channel')
    while True:
        has_task = produced_payload_semaphore.acquire(timeout=0.01)
        if has_task:
            channel.basic_publish('hightemplar', routing_key='*', body=produced_payload[0])
            debug_log('rabbitmq_published_payload', 'published payload ' + produced_payload[0])
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
