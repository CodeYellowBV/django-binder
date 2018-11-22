import pprint



_LINELEN = 120
_REPR_ELLIPSIZE = 20



class OR:
	def __init__(self, *args):
		self.options = args

	def __repr__(self):
		return 'OR({})'.format(', '.join(repr(o) for o in self.options))



class ANY:
	def __init__(self, cls=None):
		self.cls = cls

	def __repr__(self):
		return 'ANY({})'.format('' if self.cls is None else self.cls.__name__)



class EXTRA:
	def __repr__(self):
		return 'EXTRA()'



class MAYBE:
	def __init__(self, value):
		self.value = value

	def __repr__(self):
		return 'MAYBE({})'.format(repr(self.value))



def _success(func, *args, **kwargs):
	try:
		func(*args, **kwargs)
		return True
	except AssertionError:
		return False



def _erepr(o):
	s = repr(o)
	return s[:_REPR_ELLIPSIZE] + '...' if len(s) > _REPR_ELLIPSIZE else s



def _assert_json(value, spec):
	# ANY
	if isinstance(spec, ANY):
		if spec.cls is None:
			# ANY() means *anything*
			return
		else:
			# ANY(klass), so check type
			if type(value) == spec.cls:
				return
		raise AssertionError('{} is wrong type for {}'.format(repr(value), spec))

	# OR
	if isinstance(spec, OR):
		if all(not _success(_assert_json, value, s) for s in spec.options):
			raise AssertionError('{} does not match any of {}'.format(repr(value), spec))
		return

	# This seems too strict (duck typing etc), but this is meant mainly for comparing json
	# results, ans we actually want to be strict about types (True != 1 etc)!
	if type(value) != type(spec):
		raise AssertionError('Cannot compare {} ({}) and {} ({})'.format(
			repr(value), type(value), repr(spec), type(spec)))

	# dict
	if isinstance(spec, dict):
		value_copy = dict(value)
		extra = False
		for k, s in spec.items():
			if isinstance(k, EXTRA):
				extra = True
				continue

			maybe = isinstance(k, MAYBE)
			if maybe:
				k = k.value

			if k in value_copy:
				_assert_json(value_copy[k], s)
				value_copy.pop(k)
			else:
				if not maybe:
					raise AssertionError('missing key {} in dict "{}"'.format(repr(k), _erepr(value)))

		if value_copy and not extra:
			raise AssertionError('dict "{}" has extra keys: "{}"'.format(_erepr(value), _erepr(list(value_copy.keys()))))
		return

	# list
	if isinstance(spec, list):
		value_copy = list(value)
		extra = False
		for s in spec:
			if isinstance(s, EXTRA):
				extra = True
				continue

			maybe = isinstance(s, MAYBE)
			if maybe:
				s = s.value

			for v in value_copy:
				if _success(_assert_json, v, s):
					value_copy.remove(v)
					break
			else:
				if not maybe:
					raise AssertionError('missing value {} in list "{}"'.format(repr(s), _erepr(value)))

		if value_copy and not extra:
			raise AssertionError('list "{}" has extra items: "{}"'.format(_erepr(value), _erepr(value_copy)))
		return

	# Scalars -> equality test
	if type(spec) in {str, int, float, bool, type(None)}:
		if value != spec:
			raise AssertionError('{} != {}'.format(repr(value), repr(spec)))
		return

	# You whatnow?
	raise TypeError('Cannot handle spec {} ({})'.format(repr(spec), type(spec)))



def assert_json(value, spec):
	try:
		_assert_json(value, spec)
	except AssertionError as e:
		msg, *rest = e.args
		msg += '\n\n{}\n\ndoes not match spec:\n\n{}'.format(pprint.pformat(value, width=_LINELEN), pprint.pformat(spec, width=_LINELEN))
		e.args = tuple([msg] + rest)
		raise e
