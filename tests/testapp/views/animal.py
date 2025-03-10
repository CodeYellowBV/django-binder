from django.db.models import Count, Value, Sum

from binder.views import ModelView, Stat

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
	stats = {
		'without_caretaker': Stat(
			Count(Value(1)),
			filters={'caretaker:isnull': 'true'},
		),
		'by_zoo': Stat(
			Count(Value(1)),
			group_by='zoo.name',
		),
		'stat_total_magic_number': Stat(
			Sum('magic_number'),
			annotations=['magic_number'],
		),
		'stat_total_magic_number_times_hunderd': Stat(
			Sum('magic_number')*100,
			annotations=['magic_number'],
		),
	}
