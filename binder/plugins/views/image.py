from PIL import Image
from abc import ABCMeta

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.translation import ugettext as _
from django import forms

from binder.json import jsonloads, JsonResponse
from binder.exceptions import BinderValidationError
from binder.router import list_route
from binder.permissions.views import PermissionView

class MultiIdField(forms.Field):
	def validate(self, value):
		"""Check if value consists only of valid ids."""
		# Use the parent's handling of required fields, etc.
		super(MultiIdField, self).validate(value)

		for i in value:
			try:
				i = int(i)
			except TypeError:
				raise ValidationError(_("{} is not a valid integer").format(i))

class RotateForm(forms.Form):
	# ids = MultiIdField()
	angle = forms.IntegerField(max_value=360)

class CropForm(forms.Form):
	# ids = MultiIdField()
	x_1 = forms.IntegerField()
	y_1 = forms.IntegerField()
	x_2 = forms.IntegerField()
	y_2 = forms.IntegerField()

class ResetForm(forms.Form):
	ids = MultiIdField()



'''
Abstract view that allows for rotating/cropping/resetting images. Used for both scans and sheets
'''
class ImageView:
	__metaclass__ = ABCMeta

	image_name = 'file'
	image_backup_name = 'original_file'

	def _get_file(self, imageObject):
		''' Get the image file from the imageObject '''
		return getattr(imageObject, self.image_name)

	def _get_backup_file(self, imageObject):
		''' Get the backup file from the imageObject '''
		return getattr(imageObject, self.image_backup_name)

	@list_route(name='rotate', methods=['PATCH'])
	def rotate(self, request):
		body = jsonloads(request.body)

		form = RotateForm(body)

		if not form.is_valid():
			raise BinderValidationError(form.errors)

		angle = body['angle']

		for s in self._get_images(body, request):
			file = self._get_file(s)
			src_im = Image.open(file)
			rotated_img = src_im.rotate(angle, expand=1)
			rotated_img.save(file.file.name, overwrite=True)
			file.close()
		return JsonResponse([])

	@list_route(name='crop', methods='PATCH')
	def crop(self, request):
		body = jsonloads(request.body)

		form = CropForm(body)
		if not form.is_valid():
			raise BinderValidationError(form.errors)

		x_1 = body['x_1']
		x_2 = body['x_2']
		y_1 = body['y_1']
		y_2 = body['y_2']

		for s in self._get_images(body, request):
			file = self._get_file(s)
			src_im = Image.open(file)
			rotated_img = src_im.crop((x_1, y_1, x_2, y_2))
			rotated_img.save(file.file.name, overwrite=True)
			file.close()

		return JsonResponse([])

	@list_route(name='reset', methods='PATCH')
	def reset(self, request):
		body = jsonloads(request.body)

		# form = ResetForm(body)
		# if not form.is_valid():
		# 	raise BinderValidationError(form.errors)

		for s in self._get_images(body, request):
			file = self._get_file(s)
			original_file = self._get_backup_file(s)
			src_im = Image.open(original_file)
			src_im.save(file.file.name, overwrite=True)
			file.file.close()
			original_file.file.close()

		return JsonResponse([])

	def _get_images(self, body, request):
		'''
		Get all the scans defined in the body's ids paramater, or retruns a validation error if one of the objects
		does not exist
		'''
		ids = body['ids']

		scans = []
		for i in ids:
			try:
				scans.append(self.model.objects.get(pk=i))
			except ObjectDoesNotExist:
				raise BinderValidationError({
					'ids': ['ImageObject with id {} not found'.format(i)]
				})

		if isinstance(self, PermissionView):
			self.scope_change_list(request, scans, {})
		return scans
