from collections import defaultdict
from hashlib import md5
from itertools import product
from os.path import getmtime
import mimetypes

from binder.json import jsonloads, JsonResponse
from binder.exceptions import BinderNotFound


class FileHashView:
    """
    A mixin for BinderViews to append a hash based on the modification time to
    file fields. This is used to detect changes in cached files.
    """

    # The fields that should have the hash appended
    file_hash_fields = []

    def _get_objs(self, queryset, request=None):
        hashes = defaultdict(dict)
        for obj, field in product(queryset, self.file_hash_fields):
            if getattr(obj, field):
                try:
                    md5_hash = md5(
                        str(getmtime(getattr(obj, field).path)).encode()
                    ).hexdigest()
                    content_type = mimetypes.guess_type(getattr(obj, field).path)[0]

                    hashes[obj.pk][field] = {
                        'hash': md5_hash,
                        'content_type': content_type,
                    }
                except Exception:
                    # It made an error in activity view
                    # hashes[obj.pk][field] = {}
                    pass

        data = super()._get_objs(queryset, request)

        for obj in data:
            obj.update({
                field: '{}?h={}&content_type={}'.format(obj[field], meta['hash'], meta['content_type'])
                for field, meta in hashes[obj['id']].items()
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
            if field in self.file_hash_fields:
                try:
                    file_hash = md5(
                        str(getmtime(getattr(obj, field).path)).encode()
                    ).hexdigest()
                    content_type = mimetypes.guess_type(getattr(obj, field).path)[0]
                except Exception:
                    file_hash = ''
                    content_type = ''

                data['data'][field] = '{}?h={}&content_type={}'.format(
                    data['data'][field],
                    file_hash,
                    content_type,
                )
            return JsonResponse(data)

        return res
