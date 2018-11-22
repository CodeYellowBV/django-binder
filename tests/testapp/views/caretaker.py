from binder.views import ModelView

from ..models import Caretaker

class CaretakerView(ModelView):
	hidden_fields = ['ssn']
	model = Caretaker
