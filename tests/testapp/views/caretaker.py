from binder.views import ModelView
from binder.plugins.views import CsvExportView

from ..models import Caretaker

class CaretakerView(CsvExportView, ModelView):
	hidden_fields = ['ssn']
	unwritable_fields = ['last_seen']
	unupdatable_fields = ['first_seen']
	model = Caretaker


	# see `test_model_validation.py`
	allow_standalone_validation = True

	csv_settings = CsvExportView.CsvExportSettings(
		withs=[],
		column_map=[
			('id', 'ID'),
			('name', 'Name'),
			('scary', 'Scary'),
		],
		extra_params={'include_annotations': 'scary'},
	)

