
from binder.models import BinderModel
from django.db import models

from binder.plugins.models import HtmlField


class WebPage(BinderModel):
	"""
	Every zoo has a webpage containing some details about the zoo
	"""
	zoo = models.OneToOneField('Zoo', related_name='web_page', on_delete=models.CASCADE)
	content = HtmlField()
