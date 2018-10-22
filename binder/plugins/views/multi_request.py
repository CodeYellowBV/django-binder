from collections import defaultdict

from django.http import HttpRequest, JsonResponse
from django.db import transaction
from django.core.handlers.base import BaseHandler

from binder.exceptions import (
	BinderException, BinderRequestError, BinderMethodNotAllowed,
)
from binder.json import jsonloads, jsondumps


class RequestHandler(BaseHandler):

	def __init__(self):
		self.load_middleware()


class ErrorStatus(Exception):

	def __init__(self, status):
		super().__init__()
		self.status = status


def multi_request_view(request):
	if request.method == 'GET':
		allowed_methods = ['GET']
	elif request.method == 'POST':
		allowed_methods = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE']
	else:
		try:
			raise BinderMethodNotAllowed()
		except BinderException as e:
			e.log()
			return e.response(request)

	requests = jsonloads(request.body)
	responses = []
	key_responses = {}

	if not isinstance(requests, list):
		try:
			raise BinderRequestError('requests should be a list')
		except BinderException as e:
			e.log()
			return e.response(request)

	handler = RequestHandler()

	try:
		with transaction.atomic():
			for i, data in enumerate(requests):
				key = data.pop('key', i)

				# Get response from request
				try:
					req = parse_request(
						data, allowed_methods, key_responses, request,
					)
				except BinderException as e:
					e.log()
					res = e.response(request)
				else:
					res = handler.get_response(req)

				# Serialize and add to responses
				res_data = serialize_response(res)
				responses.append(res_data)

				# Add by key so that we can reference it in other requests
				key_responses[key] = res_data

				# Rollback the transaction if the request has a failing code
				if res.status_code >= 400:
					raise ErrorStatus(res.status_code)
	except ErrorStatus as e:
		status = e.status
	else:
		status = 200

	return JsonResponse(responses, safe=False, status=status)


def parse_request(data, allowed_methods, responses, request):
	if not isinstance(data, dict):
		raise BinderRequestError('requests should be dicts')

	# Transform data
	transforms = data.pop('transforms', [])
	str_params = defaultdict(dict)

	if not isinstance(transforms, list):
		raise BinderRequestError('transforms should be a list')

	for transform in transforms:
		if 'source' not in transform:
			raise BinderRequestError('transforms require the field source')
		if 'target' not in transform:
			raise BinderRequestError('transforms require the field target')
		if (
			not isinstance(transform['source'], list) or
			len(transform['source']) < 1
		):
			raise BinderRequestError('source must be a non empty list')
		if (
			not isinstance(transform['target'], list) or
			len(transform['target']) < 2
		):
			raise BinderRequestError('target must be a non empty list')

		# Get value through source
		value = responses
		for key in transform['source']:
			if not isinstance(value, (list, dict)):
				raise BinderRequestError(
					'source can only iterate through lists and dicts'
				)
			try:
				value = value[key]
			except (KeyError, IndexError):
				raise BinderRequestError(
					'invalid source {}, error at key {}'
					.format(transform['source'], key)
				)

		# Set value according to target
		target = data
		target_key = transform['target'][0]
		for i, key in enumerate(transform['target'][1:]):
			if isinstance(target, (list, dict)):
				try:
					target = target[target_key]
				except (KeyError, IndexError):
					raise BinderRequestError(
						'invalid target {}, error at key {}'
						.format(transform['target'], target_key)
					)
				target_key = key
			else:
				raise BinderRequestError(
					'target can only iterate through lists and dicts'
				)

		if isinstance(target, (list, dict)):
			try:
				target[target_key] = value
			except IndexError:
				raise BinderRequestError(
					'invalid target {}, error at key {}'
					.format(transform['target'], target_key)
				)
		elif isinstance(target, str):
			str_params[tuple(transform['target'][:-1])][transform['target'][-1]] = value
		else:
			raise BinderRequestError(
				'target can only modify lists, dicts and strs'
			)

	try:
		for keys, params in str_params.items():
			target = data
			target_key = keys[0]
			for key in keys[1:]:
				target = target[target_key]
				target_key = key
			s = target[target_key]
			try:
				s = s.format(**params)
			except KeyError as e:
				raise BinderRequestError(
					'str formatting at {}, missing key: {}'
					.format(keys, e.args[0])
				)
			target[target_key] = target[target_key].format(**params)
	except Exception:
		# All kind of things can go wrong when the data is altered through
		# a transform that occured after the str_params where determined
		# causing the target not to exist anymore or not be a str
		raise BinderRequestError(
			'transforms altered data in such a way that str params became '
			'invalid'
		)

	# Validate request
	if 'method' not in data:
		raise BinderRequestError('requests require the field method')
	if 'path' not in data:
		raise BinderRequestError('requests require the field path')

	# Validate method is allowed
	if data['method'] not in allowed_methods:
		raise BinderMethodNotAllowed()

	# Create request
	req = HttpRequest()
	req.method = data['method']
	req.path = data['path']
	req.path_info = req.path
	req.COOKIES = request.COOKIES
	req.META = request.META
	req.content_type = 'application/json'

	if 'body' in data:
		req._body = jsondumps(data['body']).encode()
	else:
		req._body = b''

	return req


def serialize_response(response):
	content_type = response.get('Content-Type', '')
	if content_type == 'application/json':
		body = jsonloads(response.content)
	else:
		body = response.content.decode()

	return {
		'status': response.status_code,
		'body': body,
		'content_type': content_type,
	}
