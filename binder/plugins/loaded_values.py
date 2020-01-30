from django.db.models import Model
from django.db.models.fields.files import FieldFile


class LoadedValuesMixin:

    __loaded_values = {}

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        instance.__loaded_values = instance.binder_concrete_fields_as_dict()
        return instance

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__loaded_values = self.binder_concrete_fields_as_dict()

    def field_changed(self, *fields):
        if self.pk is None:
            return True

        for field in fields:
            current_value = getattr(self, field)
            if isinstance(current_value, Model):
                current_value = current_value.pk
            elif isinstance(current_value, FieldFile):
                current_value = current_value.name
                if current_value is None:
                    current_value = ''

            old_value = self.get_old_value(field)

            if current_value is not old_value:
                return True

        return False

    def get_old_value(self, field):
        return self.__loaded_values.get(field)

    def save(self, *args, **kwargs):
        res = super().save(*args, **kwargs)
        self.__loaded_values = self.binder_concrete_fields_as_dict()
        return res
