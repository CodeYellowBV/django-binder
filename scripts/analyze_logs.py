#! /usr/bin/python3

from collections import defaultdict
from operator import itemgetter, attrgetter



class Request:
	def __init__(self, **kwargs):
		self.uuid = ''
		self.date = None
		self.user = ''
		self.verb = ''
		self.path = ''
		self.status = 0
		self.time = 0
		self.wth = ''
		self.limit = -1

		self.__dict__.update(kwargs)

	@property
	def verb_path(self):
		return self.path + ' ' + self.verb

	@property
	def path_with(self):
		return self.wth + ' ' + self.path

	@property
	def verb_path_with(self):
		return self.wth + ' ' + self.path + ' ' + self.verb

	def __str__(self):
		return 'Request(uuid={}, date={}, verb={}, path={}, user={}, status={}, time={}'.format(self.uuid, self.date, self.verb, self.path, self.user, self.status, self.time)

	def __repr__(self):
		return str(self)



def parse_log(*args):
	import re
	import ast
	import gzip
	import datetime

	dispatch_re = re.compile('^([0-9 .,:-]{23}) \[([a-f0-9-]{36})\]( [0-9:a-zA-Z_]+)? INFO: request dispatch; verb=([A-Z]+), user=([^ ]+), path=([^ ]+)')
	response_re = re.compile('^([0-9 .,:-]{23}) \[([a-f0-9-]{36})\]( [0-9:a-zA-Z_]+)? INFO: request response; status=([0-9]+) time=([0-9]+)ms')
	params_re = re.compile('^([0-9 .,:-]{23}) \[([a-f0-9-]{36})\]( [0-9:a-zA-Z_]+)? INFO: request parameters: (.*)$')

	def read_requests(fd):
		requests = defaultdict(Request)
		for idx, line in enumerate(fd):
			if idx % 1000 == 0:
				print('\rLoading {:,} requests'.format(len(requests)), end='')
			line = line.strip()

			match = dispatch_re.match(line)
			if match:
				date, uuid, pid, verb, user, path = match.groups()
				path = re.sub('/[0-9]+/', '/:id/', path)
				requests[uuid].uuid = uuid
				requests[uuid].date = datetime.datetime.strptime(date[:-4], '%Y-%m-%d %H:%M:%S')
				requests[uuid].user = user
				requests[uuid].verb = verb
				requests[uuid].path = path

			match = response_re.match(line)
			if match:
				date, uuid, pid, status, time = match.groups()
				requests[uuid].status = int(status)
				requests[uuid].time = int(time)

			match = params_re.match(line)
			if match:
				date, uuid, pid, params = match.groups()
				params = ast.literal_eval(params)
				requests[uuid].wth = params.get('with', [''])[0]
				limit = params.get('limit', [-1])[0]
				limit = -2 if limit == 'none' else limit
				requests[uuid].limit = int(limit)
		return requests

	for filename in args:
		if filename.endswith('.gz'):
			with gzip.open(filename, 'rt') as fd:
				requests = read_requests(fd)
		else:
			with open(filename) as fd:
				requests = read_requests(fd)

	print('\rLoaded {:,} requests.'.format(len(requests)))
	return list(requests.values())



def plot(items, sort=None, title=None, left_margin=0.20):
	import matplotlib.pyplot as plt

	if sort == 'keys':
		items = sorted(items, key=itemgetter(0), reverse=True)
	if sort == 'values':
		items = sorted(items, key=itemgetter(1), reverse=True)
	keys, values = list(zip(*items))
	plt.figure()
	if title:
		plt.suptitle(title)
	plt.style.use('seaborn-darkgrid')
	plt.barh(list(range(len(keys))), values)
	plt.yticks(list(range(len(keys))), keys)
	plt.subplots_adjust(left=left_margin, right=0.98, top=0.98, bottom=0.04)
	plt.show(block=False)



def hist(requests, filter=None, groupby=None, binning=None, xform=attrgetter('time'), aggr=len, keys=[], sort=True, left_margin=0.2):
	bins = defaultdict(list)

	if filter:
		requests = [r for r in requests if filter(r)]

	if not requests:
		raise('No requests to plot!')

	for k in keys:
		bins[k]

	for l in requests:
		val = groupby(l)
		if binning:
			val = round(val / binning) * binning
		bins[val].append(xform(l))

	for k, v in bins.items():
		bins[k] = aggr(v)

	args = []
	for a in [filter, groupby, binning, xform, aggr]:
		try:
			args.append(a.__name__)
		except AttributeError:
			args.append(str(a))
	title = 'filter={}    groupby={}    binning={}    xform={}    aggr={}'.format(*args)

	plot(bins.items(), sort=('values' if sort else 'keys'), title=title, left_margin=left_margin)



def avg(items):
	try:
		return sum(items) / len(items)
	except ZeroDivisionError:
		return 0



def isverb(vs):
	from functools import partial

	def cmp(rvs, req):
		return req.verb in rvs

	if isinstance(vs, str):
		vs = [vs]
	ret = partial(cmp, vs)
	ret.__name__ = 'isverb({})'.format(', '.join(vs))
	return ret



def istime(min=None, max=None):
	from functools import partial

	def cmp(rmin, rmax, req):
		return rmin <= req.time <= rmax

	ret = partial(cmp, 0 if min is None else min, 999999999 if max is None else max)
	ret.__name__ = '{}time{}'.format('' if min is None else '{}<'.format(min), '' if max is None else '>{}'.format(max))
	return ret



print("""
imported: defaultdict, attrgetter, itemgetter, avg

Load log files:
  reqs = parse_log('foo.log', ['bar.log.gz', ...])

Requests per hour:
  hist(reqs, groupby=attrgetter('date.hour'), keys=range(24), sort=False)

Unique users per hour:
  hist(reqs, groupby=attrgetter('date.hour'), keys=range(24), xform=attrgetter('user'), sort=False, aggr=lambda r: len(set(r)))

Request duration histogram per 50ms:
  hist(reqs, filter=istime(max=2000), groupby=attrgetter('time'), binning=50, sort=False)

Request time per user:
  hist(reqs, groupby=attrgetter('user'), aggr=sum)

Average request time per GET path:
  hist(reqs, filter=isverb('GET'), groupby=attrgetter('path'), aggr=avg)

Total request time per verb/path:
  hist(reqs, groupby=attrgetter('verb_path'), aggr=sum)

Number of requests taking >1s per verb/path:
  hist(reqs, filter=istime(min=1000), groupby=attrgetter('verb_path'), aggr=len)

hist() arguments:
  filter: (Request -> bool)    Whether or not to include a request
  groupby: (Request -> value)  Requests will be binned by <value> in the histogram
  binning: number              Further group the results in bins of size <number>
  xform: (Request -> value)    Transforms each Request into a value to aggregate into a histogram bar
  aggr: ([value] -> value)     How to aggregate the above values; len() would count, sum() add them, etc
  keys: [value, ...]           Always display these keys, even if they have no matching requests
  sort: bool                   If True, sort the histogram by bar size; if False, sort by key (Y-axis)
  left_margin: float           Ratio of the diagram to use as left margin; increase for large labels
""")



if __name__ == '__main__':
	import sys

	def copen(_globals, _locals):
		import code
		import readline
		import rlcompleter

		context = _globals.copy()
		context.update(_locals)
		readline.set_completer(rlcompleter.Completer(context).complete)
		readline.parse_and_bind("tab: complete")
		shell = code.InteractiveConsole(context)
		shell.interact()

	if len(sys.argv) > 1:
		reqs = parse_log(sys.argv[1])
		print("Requests in variable 'reqs'")
		print()

	copen(globals(), locals())
