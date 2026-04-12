from typing import Optional, List

from .exceptions import BinderMethodNotAllowed, BinderNotFound


def _route_decorator(
	is_detail: bool,
	name: Optional[str] = None,
	methods: Optional[List[str]] = None,
	extra_route: str = '',
	unauthenticated: bool = False,
	*,
	fetch_obj: bool = False):
	"""
	An abstract decorator, which can be used on a view to automatically register routes on a view

	@param is_detail: True if it is bound to an object (has a pk) false otherwise
	@param name: The name of the route, i.e. the first part of the URL. E.g. name='foo', then url = 'api/model/foo/'
	@param methods: List of http methods that the router should be listed at. E.g. ['GET', 'POST']
	@param extra_route: Postfix for the url which can be added behind the URL. Can be a regex. E.g. extra_route=r'(?P<key>[-a-zA-Z0-9_]+)/'
	@param unauthenticated: If not True, will first check if the user is logged in.
	@param fetch_obj: Boolean indicating if we should inject fetch and inject the object
	"""
	def decorator(func):
		def wrapper(self, request=None, *args, **kwargs):
			if methods is not None and request.method not in methods:
				raise BinderMethodNotAllowed(methods)

			if fetch_obj:
				if 'pk' in kwargs:
					pk = kwargs['pk']
					del kwargs['pk']

					try:
						kwargs['obj'] = self.get_queryset(request).get(pk=pk)
					except self.model.DoesNotExist:
						raise BinderNotFound()
				else:
					if len(args) == 0:
						raise Exception('Can not fetch_obj if there is no pk!')

					args = list(args)
					pk = args[0]
					try:
						args[0] = self.get_queryset(request).get(pk=pk)
					except self.model.DoesNotExist:
						raise BinderNotFound()

			return func(self, request, *args, **kwargs)
		if is_detail:
			wrapper.detail_route = True
		else:
			wrapper.list_route = True

		wrapper.route_name = name
		wrapper.extra_route = extra_route
		wrapper.unauthenticated = unauthenticated
		return wrapper
	return decorator


def list_route(*args, **kwargs):
	"""
	Add a list route, i.e. a route without a id in the name

	E.g. on the model foo

		@list_route('bar')

	Will register a route api/foo/bar/


	"""
	return _route_decorator(False, *args, **kwargs)


def detail_route(*args, **kwargs):
	"""
	Add a list route, i.e. a route with a id in the name

	E.g. on the model foo

		@list_route('bar')

	Will register a route api/foo/1/bar/
	"""
	return _route_decorator(True, *args, **kwargs)
