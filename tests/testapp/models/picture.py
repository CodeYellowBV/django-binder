import os
from django.db import models
from django.db.models.signals import post_delete

from binder.models import BinderModel

def delete_files(sender, instance=None, **kwargs):
	for field in sender._meta.fields:
		if isinstance(field, models.fields.files.FileField):
			try:
				file = getattr(instance, field.name).path
				os.unlink(file)
			except Exception:
				pass


class PictureBook(BinderModel):
	"""
	Sometimes customers like to commemorate their visit to the zoo. Of course there are always some shitty pictures that
	we do not want in a picture album

	"""

	name = models.TextField()



# At the website of the zoo there are some pictures of animals. This model links the picture to an animal.
#
# A picture has two files, the original uploaded file, and the modified file. This model is used for testing the
# ImageView plugin
class Picture(BinderModel):
	animal = models.ForeignKey('Animal', on_delete=models.CASCADE, related_name='picture')
	file = models.ImageField(upload_to='floor-plans')
	original_file = models.ImageField(upload_to='floor-plans')
	picture_book = models.ForeignKey('PictureBook', on_delete=models.CASCADE, null=True, blank=True)

	def __str__(self):
		return 'picture %d: (Picture for animal %s)' % (self.pk or 0, self.animal.name)

	class Binder:
		history = True

post_delete.connect(delete_files, sender=Picture)
