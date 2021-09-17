from binder.views import ModelView

from ..models import Caretaker

class CaretakerView(ModelView):
	hidden_fields = ['ssn']
	unwritable_fields = ['last_seen']
	unupdatable_fields = ['first_seen']
	model = Caretaker

	# see `test_model_validation.py`
	allow_standalone_validation = True
