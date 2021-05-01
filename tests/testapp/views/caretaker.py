from binder.views import ModelView
from binder.plugins.views import CsvExportView

from ..models import Caretaker

class CaretakerView(CsvExportView, ModelView):
	hidden_fields = ['ssn']
	unwritable_fields = ['last_seen']
	unupdatable_fields = ['first_seen']
	model = Caretaker

	csv_settings = CsvExportView.CsvExportSettings(
		withs=[],
		column_map=[
			('id', 'ID'),
			('name', 'Name'),
			('scary', 'Scary'),
		],
		extra_params={'include_annotations': 'scary'},
	)
