from binder.models import BinderModel
from django.db.models import Model
from django.db.models.fields.files import FieldFile
from django.core.exceptions import ObjectDoesNotExist

class LoadedValuesMixin:
    __loaded_values = {}

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        # This set may be incomplete if we're using .only(...); see
        # also the comment in get_old_value().
        if isinstance(instance, BinderModel): # In migrations, this won't work...
            instance.__loaded_values = instance.binder_concrete_fields_as_dict(skip_deferred_fields=True)
        return instance


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if isinstance(self, BinderModel): # In migrations, this won't work...
            self.__loaded_values = self.binder_concrete_fields_as_dict(skip_deferred_fields=True)


    def field_changed(self, *fields):
        if self.pk is None:
            return True

        for field in fields:
            field_def = self._meta.get_field(field)

            try:
                current_value = getattr(self, field_def.attname)
            except ObjectDoesNotExist:
                current_value = None

            if isinstance(current_value, FieldFile):
                current_value = current_value.name
                if current_value is None:
                    current_value = ''

            old_value = self.get_old_value(field)

            if current_value != old_value:
                return True

        return False


    def get_old_value(self, field):
        try:
            return self.__loaded_values[field]
        except KeyError:
            # KeyError may occur when the field was not included in
            # the set fetched from the db (e.g., due to .only(...))
            # Instead, we rely on lazy-loading to fetch it for us
            # here.  Unfortunately, this may result in hard to debug
            # performance issues.  But at least we get somewhat
            # consistent behaviour.
            value = getattr(self, field)
            if isinstance(value, Model):
                value = value.pk
            elif isinstance(value, FieldFile):
                value = value.name
                if value is None:
                    value = ''
            return value


    def get_old_values(self):
        old_values = self.__loaded_values.copy()
        # Same as in get_old_value: if we've used only(), we fetch the
        # missing fields here for consistency.
        for f in self._meta.get_fields():
            if f.concrete and f.name not in old_values and not f.many_to_many:
                old_values[f.name] = getattr(self, f.attname)
        return old_values


    def save(self, *args, **kwargs):
        res = super().save(*args, **kwargs)
        if isinstance(self, BinderModel): # In migrations, this won't work...
            self.__loaded_values = self.binder_concrete_fields_as_dict()
        return res
