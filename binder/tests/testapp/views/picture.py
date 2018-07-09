from binder.views import ModelView
from binder.plugins.views import ImageView, CsvExportView

from ..models import Picture

class PictureView(ModelView, ImageView, CsvExportView):
	model = Picture
	file_fields = ['file', 'original_file']
	csv_settings = CsvExportView.CsvExportSettings(['animal'], [
		('id', 'picture identifier'),
		('animal.id', 'animal identifier'),
		('id', 'squared picture identifier', lambda id, row, mapping: id**2),
	])
