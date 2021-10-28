from binder.plugins.views.csvexport import CsvFileAdapter, ExcelFileAdapter
from binder.router import list_route
from binder.views import ModelView
from binder.plugins.views import ImageView, CsvExportView

from ..models import Picture, PictureBook


class PictureBookView(ModelView):
	model = PictureBook


class PictureView(ModelView, ImageView, CsvExportView):
	model = Picture
	file_fields = ['file', 'original_file']
	csv_settings = CsvExportView.CsvExportSettings(['animal', 'picture_book'], [
		('id', 'picture identifier'),
		('animal.id', 'animal identifier'),
		('id', 'squared picture identifier', lambda id, row, mapping: id**2),
		('picture_book.name', 'Picturebook name'),
		('id', 'dictionary_example', lambda id, row, mapping: {'id': id}),
		('id', 'list_example', lambda id, row, mapping: [id]),
		('id', 'set_example', lambda id, row, mapping: {id})
	])

	@list_route(name='download_csv', methods=['GET'])
	def download_csv(self, request):
		"""
		Alias for the download csv endpoint, with the CsvFileAdapter
		"""
		self.csv_settings.csv_adapter = CsvFileAdapter
		return self.download(request)

	@list_route(name='download_excel', methods=['GET'])
	def download_excel(self, request):
		"""
		Alias for the download csv endpoint, with the CsvFileAdapter
		"""
		self.csv_settings.csv_adapter = ExcelFileAdapter
		return self.download(request)
