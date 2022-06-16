import pathlib
import pika

from threading import Semaphore, Thread
from time import sleep


"""
The absolute path to this file. This is needed for the inter-process producers-consumer system.
"""
RABBITMQ_CONSUMER_PATH = pathlib.Path(__file__).absolute()


"""
This method will be executed on the RabbitMQ thread of the consumer. It will create a RabbitMQ
connection and publish all payloads it receives from the consumer. It will communicate with the
main consumer thread using semaphores.

The RabbitMQ connection is managed in a separate thread to keep the connection responsive while
the main thread is busy interacting with potentially slow producers.
"""
def _rabbitmq_thread_function(consumer):
    from sys import argv

    (produced_payload_semaphore, consumed_payload_semaphore, produced_payload) = consumer

    rabbitmq_username = argv[1]
    rabbitmq_password = argv[2]
    rabbitmq_host = argv[3]

    connection_credentials = pika.PlainCredentials(rabbitmq_username, rabbitmq_password)
    connection_parameters = pika.ConnectionParameters(rabbitmq_host, credentials=connection_credentials)

    connection = pika.BlockingConnection(parameters=connection_parameters)
    channel = connection.channel()
    
    # To communicate a stop message, the length of produced_payload will be set to 0
    while len(produced_payload) == 1:

        # To prevent the connection from being closed due to not responding, we don't wait
        # on the semaphore indefinitely, but instead process data events every 0.01 seconds
        # or after each publish.
        has_task = produced_payload_semaphore.acquire(timeout=0.01)
        if has_task:
            channel.basic_publish('hightemplar', routing_key='*', body=produced_payload[0])
            consumed_payload_semaphore.release()
        connection.process_data_events(0)

    connection.close()

"""
Creates the consumer and starts the RabbitMQ thread. It will use semaphores to manage
the synchronization and it will use an array of length 1 to communicate the payload
(the array can be shared between threads and the payload can be communicated by changing
its first and only element).
"""
def _consumer_setup():
    produced_payload_semaphore = Semaphore(0)
    consumed_payload_semaphore = Semaphore(0)
    produced_payload = [None]

    consumer = (produced_payload_semaphore, consumed_payload_semaphore, produced_payload)

    rabbitmq_thread = Thread(target=lambda: _rabbitmq_thread_function(consumer))
    # Make it a daemon thread to prevent it from outliving the main thread in case of
    # unexpected errors. (But it should close the RabbitMQ connection properly in normal
    # circumstances.)
    rabbitmq_thread.setDaemon(True)
    rabbitmq_thread.start()

    return consumer

"""
Consumer a payload from a producer and propagates it to the RabbitMQ thread. It will block until
the payload has been published by the RabbitMQ thread.
"""
def _consume(consumer, payload):
    (produced_payload_semaphore, consumed_payload_semaphore, produced_payload) = consumer

    produced_payload[0] = payload
    produced_payload_semaphore.release()
    consumed_payload_semaphore.acquire()

"""
Sends the stop signal to the RabbitMQ thread
"""
def _consumer_shutdown(consumer):
    (_, _, produced_payload) = consumer
    
    # This will change the length of produced_payload to zero, which is the stop signal for
    # the RabbitMQ thread
    produced_payload.pop()
    
    # Give the RabbitMQ thread some time to observe the signal and cleanly close the connection
    sleep(0.1)

"""
Starts the RabbitMQ consumer
"""
def main():
    from inter_process_producers_consumer import try_run_consumer

    try_run_consumer(_consumer_setup, _consume, _consumer_shutdown)

# IMPORTANT: only call main() in the actual consumer process. NOT when the main process just
# tries to access *RABBITMQ_CONSUMER_PATH*
if __name__ == '__main__':
    main()
