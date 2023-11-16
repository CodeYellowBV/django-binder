from .exceptions import BinderMethodNotAllowed, BinderNotFound


def _route_decorator(is_detail, name=None, methods=None, extra_route='', unauthenticated=False, *, fetch_obj=False):
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
	return _route_decorator(False, *args, **kwargs)


def detail_route(*args, **kwargs):
	return _route_decorator(True, *args, **kwargs)
