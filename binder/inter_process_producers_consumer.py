import os
import socket
import time

HOST = '127.0.0.1' # I don't want to expose this anyway, so localhost is fine
PORT = 22102

def _retry(task, min_wait_time, max_wait_time, num_attempts):
    for attempt_counter in range(num_attempts):
        if task():
            return
        else:
            time.sleep(min_wait_time + (max_wait_time - min_wait_time) * (attempt_counter / num_attempts))
    raise RuntimeError('Reached maximum number of retries')

# 8 characters to encode the length should be more than enough
NUM_LENGTH_CHARS = 8

def _run_consumer(consumer_setup, consume):
    from utils import debug_log

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        debug_log('consumer_started', 'A consumer managed to bind itself to the port')
        server_socket.settimeout(5)
        consumer = consumer_setup()
        server_socket.listen()

        counter = 1

        try:
            while True:
                client_connection, _ = server_socket.accept()
                debug_log('consumer_accept', 'The consumer accepted connection ' + str(counter))
                counter += 1
                with client_connection:
                    payload_length = int(str(client_connection.recv(NUM_LENGTH_CHARS), 'utf-8'))
                    payload = str(client_connection.recv(payload_length), 'utf-8')
                    debug_log('consumer_consumed', 'Consumed payload ' + payload)
                    consume(consumer, payload)
        except socket.timeout:
            pass

def try_run_consumer(consumer_setup, consume):
    from utils import debug_log

    try:
        _run_consumer(consumer_setup, consume)
    except OSError as error:
        debug_log('consumer_failed_start', 'Failed to start the consumer: ' + str(error))


def _try_produce(payload, consumer_path, consumer_parameters):
    consumer_process = os.popen('python3 ' + str(consumer_path.absolute()) + ' ' + consumer_parameters, mode="w")
    consumer_process.detach()
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
        return False

def produce(payload, consumer_path, consumer_parameters):
    _retry(lambda: _try_produce(payload, consumer_path, consumer_parameters), 0.01, 1.0, 10)
