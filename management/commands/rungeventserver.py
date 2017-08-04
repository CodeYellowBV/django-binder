import sys
import errno
import os
import socket
from django.core.management.base import BaseCommand
from django.core.handlers.wsgi import WSGIHandler
from werkzeug.serving import run_with_reloader
from gevent import pywsgi
from geventwebsocket.handler import WebSocketHandler
from django.utils.encoding import force_text

class Command(BaseCommand):
	default_addr = '127.0.0.1'
	default_port = '8000'

	def add_arguments(self, parser):
		parser.add_argument(
			'addrport', nargs='?',
			help='Optional port number, or ipaddr:port'
		)
		parser.add_argument(
			'--ipv6', '-6', action='store_true', dest='use_ipv6',
			help='Tells Django to use an IPv6 address.',
		)
		parser.add_argument(
			'--nothreading', action='store_false', dest='use_threading',
			help='Tells Django to NOT use threading.',
		)
		parser.add_argument(
			'--noreload', action='store_false', dest='use_reloader',
			help='Tells Django to NOT use the auto-reloader.',
		)

	def handle(self, *args, **options):
		# monkey.patch_all(thread=False)

		if not options['addrport']:
			self.addr = ''
			self.port = self.default_port

		self.run(**options)

	def run(self, **options):
		"""
		Runs the server, using the autoreloader if needed
		"""
		use_reloader = options['use_reloader']

		if use_reloader:
			run_with_reloader(self.inner_run)
			# restart_with_reloader(self.inner_run)
			# autoreload.main(self.inner_run, None, options)
		else:
			self.inner_run(None, **options)

	def inner_run(self):
		try:
			bind = (self.addr, int(self.port))
			app = WSGIHandler()
			server = pywsgi.WSGIServer(bind, app, handler_class=WebSocketHandler)
			server.serve_forever()
		except socket.error as e:
			# Use helpful error messages instead of ugly tracebacks.
			ERRORS = {
				errno.EACCES: "You don't have permission to access that port.",
				errno.EADDRINUSE: "That port is already in use.",
				errno.EADDRNOTAVAIL: "That IP address can't be assigned to.",
			}
			try:
				error_text = ERRORS[e.errno]
			except KeyError:
				error_text = force_text(e)
			self.stderr.write("Error: %s" % error_text)
			# Need to use an OS exit because sys.exit doesn't work in a thread
			os._exit(1)
		except KeyboardInterrupt:
			sys.exit(0)
