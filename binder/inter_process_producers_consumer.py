import os
import socket
import time

# This file provides functions to create an inter-process producers-consumer system. The basic
# concept is that the *produce* method can be called to ensure that a given 'payload' is
# 'consumed' in another process: the consumer process. If the consumer process is not yet
# running, it will also be started by the *produce* method. After consuming the message, it
# will wait for payloads of future producers and it will quit when it hasn't received anything
# for a certain amount of time.
#
# This system is used to maintain our RabbitMQ connection: the consumer will create a RabbitMQ
# connection and publish all payloads it gets from the producers to RabbitMQ. This avoids the
# need to create and destroy a RabbitMQ connection for each payload.


# The producers and the consumer will run on the same machine, so we should use localhost
"""
The host at which the consumer will listen for incoming producer connections
"""
HOST = '127.0.0.1'

# We might want to stop hardcoding the port at some point and use some environment variable instead, 
# but this is not as easy as it looks: the consumer will run in a different process and thus won't
# be able to read the environment variables, so it will have to be propgated some other way.
"""
The port at which the consumer will listen for incoming producer connections
"""
PORT = 22102

"""
The consumer will stop when it hasn't received anything for *MAX_CONSUMER_WAIT_TIME* seconds long
"""
MAX_CONSUMER_WAIT_TIME = 5

"""
Retries the given *task* *num_attempts* times until it succeeds (returns True). 

After each failed attempt, it will wait between *min_wait_time* and *max_wait_time* seconds 
before doing the next attempt. The time between the first attempt and the second attempt is 
the shortest, and the time between consecutive attempts will take longer and longer (but never 
longer than *max_wait_time*).

This behavior is nice because it ensures that the first failure is retried quickly while decreasing
the system load when retrying many times.
"""
def _retry(task, min_wait_time, max_wait_time, num_attempts):
    for attempt_counter in range(num_attempts):
        if task():
            return
        else:
            time.sleep(min_wait_time + (max_wait_time - min_wait_time) * (attempt_counter / num_attempts))
    raise RuntimeError('Reached maximum number of retries')

"""
The number of characters (well... bytes) used to encode the payload length of the producers.

The producer will write the payload length in the first 8 bytes and write the actual payload
thereafter. This is needed to let the consumer know how long each payload is.

The value is currently 8 characters long, which allows payloads of at most 10^8 bytes, which
should be more than we will ever need.
"""
NUM_LENGTH_CHARS = 8

"""
Tries to start the consumer.

This method will try to open a TCP server socket at port *PORT*. If that succeeds, it will
call *consumer_setup()*. The result of *consumer_setup()* is the consumer. 

Then, it will listen for incoming socket connections from the producers. For each incoming 
connection, it will call *consume(consumer, payload)* where *payload* is the payload received 
from the incoming connection. (Currently, it allows only 1 payload per producer connection.)

When no incoming connections have been made for *MAX_CONSUMER_WAIT_TIME* seconds, the server
socket will be closed and it will call *consumer_shutdown(consumer)*.
"""
def _run_consumer(consumer_setup, consume, consumer_shutdown):
    from struct import pack

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:

        # This sockopt will cause the server socket port to be freed instantly after the server
        # socket is closed. If we would NOT do this, the entire producer-consumer system would
        # hang when a payload is produced soon after a consumer has stopped.
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, pack('ii', 1, 0))
        server_socket.bind((HOST, PORT))
        server_socket.settimeout(MAX_CONSUMER_WAIT_TIME)
        consumer = consumer_setup()
        server_socket.listen()

        try:
            while True:
                client_connection, _ = server_socket.accept()
                with client_connection:
                    payload_length = int(str(client_connection.recv(NUM_LENGTH_CHARS), 'utf-8'))
                    payload = str(client_connection.recv(payload_length), 'utf-8')
                    consume(consumer, payload)
        except socket.timeout:
            consumer_shutdown(consumer)

"""
Calls _run_consumer and catches any OSError it may throw.
"""
def try_run_consumer(consumer_setup, consume, consumer_shutdown):
    try:
        _run_consumer(consumer_setup, consume, consumer_shutdown)
    except OSError:
        pass


"""
Performs a single attempt to produce the given *payload*. If the consumer can NOT be reached, it
will try to start a new consumer.
"""
def _try_produce(payload, consumer_path, consumer_parameters):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
            client_socket.connect((HOST, PORT))
            payload_length = str(len(payload))
            if len(payload_length) > NUM_LENGTH_CHARS:
                raise RuntimeError('Payload is too large')
            while len(payload_length) < NUM_LENGTH_CHARS:
                payload_length = '0' + payload_length
            client_socket.sendall(bytes(payload_length, 'utf-8'))
            client_socket.sendall(bytes(payload, 'utf-8'))
            return True
    except ConnectionRefusedError or TimeoutError:

        # If the connection failed, the consumer is probably not running, so we should try to
        # start it (in a different process).
        consumer_process = os.popen('python3 ' + str(consumer_path.absolute()) + ' ' + consumer_parameters, mode="w")
        consumer_process.detach()
        return False


"""
Ensures that the given *payload* is 'consumed' in another process. The *consumer_path* should
point to a .py file that will call the *try_run_consumer* method of this class. If the consumer
is not yet running, this method will basically execute "python3 consumer_path consumer_parameters* 
in a new process.
"""
def produce(payload, consumer_path, consumer_parameters):

    # Since the _try_produce method is rather fragile, we may need to retry it a couple of times.
    # It is fragile because:
    #
    # (1) The consumer may or may not be running. If it is not running, the _try_produce will
    # obviously fail, but it will try to create a new consumer, so there is a big chance the
    # next attempt will succeed.
    #
    # (2) When a new consumer is created, the OS scheduler might not start it immediately, so
    # the second and third attempt may also fail.
    #
    # (3) When the existing consumer is quitting, the produce attempt will also fail, and so will
    # its attempt to create a new consumer (since the port is still claimed by the quitting
    # consumer). This will cause the second attempt to fail as well, and maybe also the third and
    # fourth attempt.
    _retry(lambda: _try_produce(payload, consumer_path, consumer_parameters), 0.01, 1.0, 10)
