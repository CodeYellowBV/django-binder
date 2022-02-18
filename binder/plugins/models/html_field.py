from django.db.models import TextField


class HtmlField(TextField):
	"""
	Determine a safe way to save "secure" user provided HTML input, and prevent
	"""


	def validate(self, value, _):
		pass
