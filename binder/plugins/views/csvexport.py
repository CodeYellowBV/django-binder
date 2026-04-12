import abc
import csv
from tempfile import NamedTemporaryFile
from typing import List

from django.http import HttpResponse, HttpRequest

from binder.json import jsonloads
from binder.router import list_route


class ExportFileAdapter:
	"""
	Adapter between the data that is exported, and the export file
	"""
	__metaclass__ = abc.ABCMeta

	def __init__(self, request: HttpRequest):
		self.request = request

	@abc.abstractmethod
	def set_file_name(self, file_name: str):
		"""
		Sets the file name of the file that needs to be export. File name does not have the extension.

		e.g. set_file_name('foo') => file download name is 'foo.csv' or 'foo.xlsx'

		:param file_name:
		:return:
		"""
		pass

	@abc.abstractmethod
	def set_columns(self, columns: List[str]):
		"""
		Set the column names of the file

		:param columns:
		:return:
		"""
		pass


	@abc.abstractmethod
	def add_row(self, values: List[str]):
		"""
		Add a row with values to the file

		:param values:
		:return:
		"""
		pass



	@abc.abstractmethod
	def get_response(self) -> HttpResponse:
		"""
		Return a http response with the content of the file

		:param columns:
		:return:
		"""
		pass


class CsvFileAdapter(ExportFileAdapter):
	"""
	Adapter for returning CSV files
	"""

	def __init__(self, request: HttpRequest):
		super().__init__(request)
		self.response = HttpResponse(content_type='text/csv')
		self.file_name = 'export'
		self.writer = csv.writer(self.response)

	def set_file_name(self, file_name: str):
		self.file_name = file_name

	def set_columns(self, columns: List[str]):
		self.add_row(columns)

	def add_row(self, values: List[str]):
		self.writer.writerow(values)

	def get_response(self) -> HttpResponse:
		self.response['Content-Disposition'] = 'attachment; filename="{}.csv"'.format(self.file_name)
		return self.response


class ExcelFileAdapter(ExportFileAdapter):
	"""
	Adapter for returning excel files
	"""
	def __init__(self, request: HttpRequest):
		super().__init__(request)

		# Import pandas locally. This means that you can use the CSV adapter without using pandas
		import openpyxl
		self.openpyxl = openpyxl
		self.file_name = 'export'
		# self.writer = self.pandas.ExcelWriter(self.response)

		self.work_book = self.openpyxl.Workbook()
		self.sheet = self.work_book.active

		# The row number we are currently writing to
		self._row_number = 0

	def set_file_name(self, file_name: str):
		self.file_name = file_name

	def set_columns(self, columns: List[str]):
		self.add_row(columns)

	def add_row(self, values: List[str]):
		for (column_id, value) in enumerate(values):
			self.sheet.cell(column=column_id + 1, row=self._row_number + 1, value=value)
		self._row_number += 1

	def get_response(self) -> HttpResponse:
		with NamedTemporaryFile() as tmp:
			self.work_book.save(tmp.name)
			self.response = HttpResponse(
				content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
				content=tmp,
			)
			self.response['Content-Disposition'] = 'attachment; filename="{}.xlsx"'.format(self.file_name)
			return self.response

DEFAULT_RESPONSE_TYPE_MAPPING = {
	'xlsx': ExcelFileAdapter,
}

class RequestAwareAdapter(ExportFileAdapter):
	"""
	Adapter that returns csv files by default, but allows a request parameter to return other files as well

	e.g. foo/download/?response_type=xlsx

	returns a xlsx type
	"""
	def __init__(self, request: HttpRequest):
		super().__init__(request)

		response_type_mapping = DEFAULT_RESPONSE_TYPE_MAPPING
		response_type = request.GET.get('response_type', '').lower()
		AdapterClass = response_type_mapping.get(response_type, CsvFileAdapter)

		self.base_adapter = AdapterClass(request)

	def set_file_name(self, file_name: str):
		return self.base_adapter.set_file_name(file_name)

	def set_columns(self, columns: List[str]):
		return self.base_adapter.set_columns(columns)

	def add_row(self, values: List[str]):
		return self.base_adapter.add_row(values)

	def get_response(self) -> HttpResponse:
		return self.base_adapter.get_response()




class CsvExportView:
	"""
	This class adds another endpoint to the ModelView, namely GET model/download/. This does the same thing as getting a
	collection, excepts that the result is returned as a csv file, rather than a json file
	"""
	__metaclass__ = abc.ABCMeta

	# CSV setting contains all the information that is needed to define a csv file. This must be one an instance of
	# CSVExportSettings
	csv_settings = None

	class CsvExportSettings:
		"""
		This is a fake struct which contains the definition of the CSV Export
		"""

		def __init__(self, withs, column_map, file_name=None, default_file_name='download', multi_value_delimiter=' ',
					extra_permission=None, extra_params={}, csv_adapter=RequestAwareAdapter, limit=10000):
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
			@param csv_adapter: Class. Either an object extending
			@param response_type_mapping: Mapping between the parameter used in the custom response type
			@param limit: Limit for amount of items in the csv. This is a fail save that you do not bring down the server with
			a big query
			"""
			self.withs = withs
			self.column_map = column_map
			self.file_name = file_name
			self.default_file_name = default_file_name
			self.multi_value_delimiter = multi_value_delimiter
			self.extra_permission = extra_permission
			self.extra_params = extra_params
			self.csv_adapter = csv_adapter
			self.limit = limit


	def _generate_csv_file(self, request: HttpRequest, file_adapter: CsvFileAdapter):

		# Sometimes we want to add an extra permission check before a csv file can be downloaded. This checks if the
		# permission is set, and if the permission is set, checks if the current user has the specified permission
		if self.csv_settings.extra_permission is not None:
			self._require_model_perm(self.csv_settings.extra_permission, request)

		# # A bit of a hack. We overwrite some get parameters, to make sure that we can create the CSV file
		mutable = request.POST._mutable
		request.GET._mutable = True
		request.GET['page'] = 1
		request.GET['limit'] = self.csv_settings.limit if self.csv_settings.limit is not None else 'none'
		request.GET['with'] = ",".join(self.csv_settings.withs)
		for key, value in self.csv_settings.extra_params.items():
			request.GET[key] = value
		request.GET._mutable = mutable

		parent_result = self.get(request)
		parent_data = jsonloads(parent_result.content)

		file_name = self.csv_settings.file_name
		if callable(file_name):
			file_name = file_name(parent_data)
		if file_name is None:
			file_name = self.csv_settings.default_file_name
		file_adapter.set_file_name(file_name)

		# CSV header
		file_adapter.set_columns(list(map(lambda x: x[1], self.csv_settings.column_map)))

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
					if isinstance(data[head_key], dict):
						return get_datum(data[head_key], subkey, new_prefix)
					else:
						# Assume that we have a mapping now
						fk_ids = data[head_key]
						if not isinstance(fk_ids, list):
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
				if isinstance(datum, list):
					datum = self.csv_settings.multi_value_delimiter.join(datum)
				data.append(datum)
			file_adapter.add_row(data)

	@list_route(name='download', methods=['GET'])
	def download(self, request):
		"""
		Download the get request in csv form
		@param request:
		@return:
		"""

		if self.csv_settings is None:
			raise Exception('No csv settings set!')

		file_adapter = self.csv_settings.csv_adapter(request)

		self._generate_csv_file(request, file_adapter)

		return file_adapter.get_response()
