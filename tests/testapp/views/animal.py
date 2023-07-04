from binder.views import ModelView

from ..models import Animal
from binder.plugins.views import CsvExportView

# From the api docs


class AnimalView(ModelView, CsvExportView):
	model = Animal
	m2m_fields = ['costume']
	searches = ['name__icontains']
	transformed_searches = {'zoo_id': int}

	csv_settings = CsvExportView.CsvExportSettings(
		withs=['zoo', 'caretaker'],
		column_map=[
			('id', 'ID'),
			('zoo.id', 'Zoo ID'),
			('caretaker.id', 'Caretaker ID'),
		],
	)
