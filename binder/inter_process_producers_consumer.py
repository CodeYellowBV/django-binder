import os
import socket
import time

from fasteners import InterProcessLock

HOST = '127.0.0.1' # I don't want to expose this anyway, so localhost is fine
PORT = 22102

def _retry(task, wait_time, num_attempts):
    for _ in range(num_attempts):
        if task():
            return
        else:
            time.sleep(wait_time)
    raise RuntimeError('Reached maximum number of retries')

# 8 characters to encode the length should be more than enough
NUM_LENGTH_CHARS = 8

def _run_consumer(consumer_setup, consume, consumer_shutdown):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.settimeout(5)
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

def _try_produce(payload, lock, run_consumer):
    # Check whether a consumer server is already running. If not, start it
    if os.fork() == 0:
        if lock.acquire(blocking=False):
            print('ACQUIRED LOCK')
            try:
                run_consumer()
            except RuntimeError as uh_ooh:
                print('Failed to start consumer server', uh_ooh)
            lock.release()
            print('RELEASED LOCK')
        exit(0)
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
    except ConnectionRefusedError:
        return False

def produce(payload, lock_path, consumer_setup, consume, consumer_shutdown):
    lock = InterProcessLock(lock_path)

    _retry(lambda: _try_produce(payload, lock, lambda: _run_consumer(consumer_setup, consume, consumer_shutdown)), 0.01, 10)
