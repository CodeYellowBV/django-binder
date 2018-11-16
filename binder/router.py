from importlib import import_module

import django
from django.apps import apps
from django.urls import reverse

from binder.views import ModelView
from .exceptions import BinderRequestError, BinderCSRFFailure, BinderMethodNotAllowed



def _route_decorator(is_detail, name=None, methods=None, extra_route='', unauthenticated=False):
	def decorator(func):
		def wrapper(self, request=None, *args, **kwargs):
			if methods is not None and request.method not in methods:
				raise BinderMethodNotAllowed(methods)
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



def csrf_failure(request, reason=None):
	# Hack to make sure the exception is thrown; the traceback code depends on that.
	try:
		raise BinderCSRFFailure(reason)
	except BinderRequestError as e:
		e.log()
		return e.response()



class Route(object):
	route = None
	list_endpoint = None
	detail_endpoint = None

	def __init__(self, route, list_endpoint=True, detail_endpoint=True):
		self.route = route
		self.list_endpoint = list_endpoint
		self.detail_endpoint = detail_endpoint



class Router(object):

	@staticmethod
	def bootstrap():
		me = Router()

		# import all views
		for app in apps.get_app_configs():
			try:
				import_module('.views', app.name)
			except ImportError:
				# No views to be imported for this app
				pass
		me.register(ModelView)
		return me


	def __init__(self):
		self.model_views = {}
		self.model_routes = {}
		self.route_views = {}
		# FIXME: this needs to be much much better defined
		self.name_models = {}



	def register(self, superclass):
		for view in superclass.__subclasses__():
			if view.register_for_model and view.model is not None:
				if view.model in self.model_views:
					raise ValueError('Model-View mapping conflict for {}: {} vs {}'.format(view.model, view, self.model_views[view.model]))
				self.model_views[view.model] = view
				self.name_models[view._model_name()] = view.model

			if view.route is not None:
				if isinstance(view.route, Route):
					route = view.route
				elif isinstance(view.route, str):
					route = Route(view.route)
				elif view.route is True:
					if view.model is None:
						route = None
					else:
						route = Route(view._model_name())
				else:
					raise TypeError('{}.route'.format(view))

				if route:
					for r, v in self.route_views.items():
						if r.route == route.route:
							raise ValueError('Routing conflict for "{}": {} vs {}'.format(route.route, view, v))
					self.route_views[route] = view

			# Recurse subclasses of this subclass, so we register all descendants.
			self.register(view)
		return self



	def model_view(self, model):
		try:
			return self.model_views[model]
		except KeyError:
			# FIXME: this should actually be a 500
			raise BinderRequestError('No view defined for model {}.'.format(model.__name__))



	def model_route(self, model, pk=None, field=None):
		if not model in self.model_routes:
			self.model_routes[model] = reverse(model.__name__)
		route = self.model_routes[model]

		if pk and field:
			return '{}{}/{}/'.format(route, pk, field.name)

		if pk:
			return '{}{}/'.format(route, pk)

		return route



	@property
	def urls(self):
		urls = []
		for route, view in self.route_views.items():
			name = view.model.__name__ if view.model else route.route
			# List and detail endpoints
			if route.list_endpoint:
				urls.append(django.conf.urls.url(r'^{}/$'.format(route.route), view.as_view(), {'router': self}, name=name))
			if route.detail_endpoint:
				urls.append(django.conf.urls.url(r'^{}/(?P<pk>[0-9]+)/$'.format(route.route), view.as_view(), {'router': self}, name=name))

			# History views
			if view.model and hasattr(view.model, 'Binder') and view.model.Binder.history:
				urls.append(django.conf.urls.url(r'^{}/(?P<pk>[0-9]+)/history/$'.format(route.route), view.as_view(), {'history': 'normal', 'router': self}, name=name))
				urls.append(django.conf.urls.url(r'^{}/(?P<pk>[0-9]+)/history/debug/$'.format(route.route), view.as_view(), {'history': 'debug', 'router': self}, name=name))

			# File field endpoints
			for ff in view.file_fields:
				urls.append(django.conf.urls.url(r'^{}/(?P<pk>[0-9]+)/{}/$'.format(route.route, ff),
						view.as_view(), {'file_field': ff, 'router': self}, name='{}.{}'.format(name, ff)))

			# Custom endpoints
			for m in dir(view):
				method = getattr(view, m)
				if hasattr(method, 'detail_route') or hasattr(method, 'list_route'):
					route_name = method.route_name
					extra = method.extra_route
					kwargs = {'method': m, 'router': self}
					if method.unauthenticated:
						kwargs['unauthenticated'] = True
					if hasattr(method, 'detail_route'):
						urls.append(django.conf.urls.url(r'^{}/(?P<pk>[0-9]+)/{}/{}$'.format(route.route, route_name, extra),
								view.as_view(), kwargs, name='{}.{}'.format(name, route_name)))
					if hasattr(method, 'list_route'):
						urls.append(django.conf.urls.url(r'^{}/{}/{}$'.format(route.route, route_name, extra),
								view.as_view(), kwargs, name='{}.{}'.format(name, route_name)))

		return urls
