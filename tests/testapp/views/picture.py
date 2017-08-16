from binder.views import ModelView
from binder.plugins.views import ImageView, CsvExportView

from ..models import Picture

# From the api docs
class PictureView(ModelView, ImageView, CsvExportView):
	model = Picture

	csv_settings = CsvExportView.CsvExportSettings(
		withs=['animal'],
		column_map = [
			('id', 'picture identifier'),
			('animal.id', 'animal identifier'),
			('id', 'squared picture identifier', lambda datum, context, mapping: datum ** 2)
		]
	)
