class classproperty:
	"""
	Simple implementation for a classproperty decorator. Does not support
	setters.
	"""

	def __init__(self, func):
		if not isinstance(func, (classmethod, staticmethod)):
			func = classmethod(func)
		self.func = func

	def __get__(self, obj, cls=None):
		if cls is None:
			cls = type(obj)
		return self.func.__get__(obj, cls)()

	def __set__(self, obj, value):
		raise AttributeError('can\'t set classproperty')
