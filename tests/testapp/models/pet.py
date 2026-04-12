from binder.models import BinderModel

from .animal import Animal

class Pet(Animal):
    class Meta(BinderModel.Meta):
        proxy = True
