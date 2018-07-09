from binder.router import list_route
from abc import ABCMeta
import csv
from binder.json import jsonloads
from django.http import HttpResponse

# A Mixin to add a GET object/download link, that downloads the get request as csv file
class CsvExportView:
	"""
	This class adds another endpoint to the ModelView, namely GET model/download/. This does the same thing as getting a
	collection, excepts that the result is returned as a csv file, rather than a json file
	"""
	__metaclass__ = ABCMeta

	# CSV setting contains all the information that is needed to define a csv file. This must be one an instance of
	# CSVExportSettings
	csv_settings = None

	class CsvExportSettings:
		"""
		This is a fake struct which contains the definition of the CSV Export
		"""
		def __init__(self, withs, column_map, file_name=None, default_file_name='download', multi_value_delimiter=' ', extra_permission=None):
			"""
			@param withs: String[]  An array of all the withs that are necessary for this csv export
			@param column_map: Tuple[] An array, with all columns of the csv file in order. Each column is represented by a tuple
				(key, title) or (key, title, callback)
			@param file_name: String The file name of the outputted csv file, without the csv extension, if it is a callable it will
				be called on the data retrieved from the get request
			@param default_file_name: String The fallback for when resolving file_name gives back None
			@param multi_value_delimiter: String When one column has multiple values, they are joined, with this value
				as delimiter between them. This may be if an array is returned, or if we have a one to many relation
			@param extra_permission: String When set, an extra binder permission check will be done on this permission.
			"""
			self.withs = withs
			self.column_map = column_map
			self.file_name = file_name
			self.default_file_name = default_file_name
			self.multi_value_delimiter = multi_value_delimiter
			self.extra_permission = extra_permission

	@list_route(name='download', methods=['GET'])
	def download(self, request):
		"""
		Download the get request in csv form
		@param request:
		@return:
		"""

		if self.csv_settings is None:
			raise Exception('No csv settings set!')

		# Sometimes we want to add an extra permission check before a csv file can be downloaded. This checks if the
		# permission is set, and if the permission is set, checks if the current user has the specified permission
		if self.csv_settings.extra_permission is not None:
			self._require_model_perm(self.csv_settings.extra_permission, request)

		# # A bit of a hack. We overwrite some get parameters, to make sure that we can create the CSV file
		mutable = request.POST._mutable
		request.GET._mutable = True
		request.GET['page'] = 1
		request.GET['limit'] = 10000
		request.GET['with'] = ",".join(self.csv_settings.withs)
		request.GET._mutable = mutable

		parent_result = self.get(request)
		parent_data = jsonloads(parent_result.content)

		file_name = self.csv_settings.file_name
		if callable(file_name):
			file_name = file_name(parent_data)
		if file_name is None:
			file_name = self.csv_settings.default_file_name

		response = HttpResponse(content_type='text/csv')
		response['Content-Disposition'] = 'attachment; filename="{}.csv"'.format(file_name)

		writer = csv.writer(response)
		# CSV header
		writer.writerow(list(map(lambda x: x[1], self.csv_settings.column_map)))

		# Make a mapping from the withs. This creates a map. This is needed for easy looking up relations
		# {
		# 	"with_name": {
		#		model_id: model,
		#		...
		#   },
		#	...
		# }
		key_mapping = {}
		for key in parent_data['with']:
			key_mapping[key] = {}
			for row in parent_data['with'][key]:
				key_mapping[key][row['id']] = row


		def get_datum(data, key, prefix=''):
			"""
			Recursively gets the correct data point from the dataset

			@param data: Dict At the first call this is the 'data' value in the response. In the recursion, we go deeper
			in the dict, and we get part of the original dict. However, when we go through a with, we may end up in the
			data from one of the key mappings.
			@param key: String The key of the value we try to find. The level of the dictionary where we need to find
			the data are delimited by a .
			@return: Any: The data point present at key
			"""

			# Add the deepest level we can just get the specified key
			if '.' not in key:
				if key not in data:
					raise Exception("{} not found in data: {}".format(key, data))
				if type(data[key]) == list:
					return self.csv_settings.multi_value_delimiter.join(data[key])
				return data[key]
			else:
				"""
				If we we are not at the deepest level, there are two possibilities:

				- We want to go into an dict. This can be because the model has a json encoded dicts as a value, or because
				the array is created by custom logic
				- We want to follow a relation. In this case we either have a integer (in case of a X-to-one relation) or a
				list of integers (in case of a X-to-many) relation. In this case, we reconstruct the whole path into the data
				(We use the prefix for this). This is then mapped to the correct related model(s), and we go recursively
				deeper in this models.
				"""
				head_key, subkey = key.split('.', 1)
				if head_key in data:
					new_prefix = '{}.{}'.format(prefix, head_key)
					if type(data[head_key]) == dict:
						return get_datum(data[head_key], subkey, new_prefix)
					else:
						# Assume that we have a mapping now
						fk_ids = data[head_key]
						if type(fk_ids) != list:
							fk_ids = [fk_ids]

						# if head_key not in key_mapping:
						prefix_key = parent_data['with_mapping'][new_prefix[1:]]
						datums = [str(get_datum(key_mapping[prefix_key][fk_id], subkey, new_prefix)) for fk_id in fk_ids]
						return self.csv_settings.multi_value_delimiter.join(
							datums
						)

				else:
					raise Exception("{} not found in {}".format(head_key, data))


		for row in parent_data['data']:
			data = []
			for col_definition in self.csv_settings.column_map:
				datum = get_datum(row, col_definition[0])
				if len(col_definition) >= 3:
					transform_function = col_definition[2]
					datum = transform_function(datum, row, key_mapping)
				data.append(datum)
			writer.writerow(data)

		return response
