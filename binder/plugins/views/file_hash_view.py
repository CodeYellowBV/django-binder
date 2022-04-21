from hashlib import md5
from os.path import getmtime
from mimetypes import guess_type

from binder.json import jsonloads, JsonResponse
from binder.exceptions import BinderNotFound
from binder.models import BinderFileField


class FileHashView:
    """
    DEPRECATED: Use BinderFileField instead.
    A mixin for BinderViews to append a hash based on the modification time to
    file fields. This is used to detect changes in cached files.
    """

    file_hash_fields = True
    file_type_fields = True

    def _get_params(self, obj, field):
        params = []
        field_file = getattr(obj, field)

        if self.file_hash_fields is True:
            file_hash_fields = self.file_fields
        elif self.file_hash_fields is False:
            file_hash_fields = []
        else:
            file_hash_fields = self.file_hash_fields

        if self.file_type_fields is True:
            file_type_fields = self.file_fields
        elif self.file_type_fields is False:
            file_type_fields = []
        else:
            file_type_fields = self.file_type_fields

        if field in file_hash_fields:
            try:
                path = field_file.path
                mtime = getmtime(path)
            except Exception:
                pass
            else:
                url_hash = md5(str(mtime).encode()).hexdigest()
                params.append('h=' + url_hash)

        if field in file_type_fields:
            if field_file.name:
                content_type = guess_type(field_file.name)[0]
                params.append('content_type=' + content_type if content_type is not None else '')

        if not params:
            return ''
        else:
            return '?' + '&'.join(params)

    def _get_objs(self, queryset, request=None, annotations=None):
        params = {
            obj.pk: {
                field: self._get_params(obj, field)
                for field in self.file_fields
                # BinderFileField handles this by default
                if not isinstance(obj._meta.get_field(field), BinderFileField)
            }
            for obj in queryset
        }

        data = super()._get_objs(queryset, request, annotations)

        for obj in data:
            obj.update({
                field: obj[field] + field_params
                for field, field_params in params[obj['id']].items()
                if obj[field] is not None
            })

        return data

    def dispatch_file_field(self, request, pk=None, file_field=None):
        if isinstance(pk, self.model):
            obj = pk
        else:
            try:
                obj = self.get_queryset(request).get(pk=int(pk))
            except self.model.DoesNotExist:
                raise BinderNotFound()

        res = super().dispatch_file_field(request, obj, file_field)

        if request.method == 'POST':
            data = jsonloads(res.content)
            field = next(iter(data['data']))
            data['data'][field] += self._get_params(obj, field)
            return JsonResponse(data)

        return res
