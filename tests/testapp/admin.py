from django.contrib import admin

from testapp.models import Animal, Caretaker, ContactPerson, Costume, Zoo



@admin.register(Animal)
class AnimalAdmin(admin.ModelAdmin):
	list_display = ['name', 'id', 'zoo', 'caretaker', 'deleted']
	list_filter = ['deleted', 'zoo', 'caretaker']



@admin.register(Caretaker)
class CaretakerAdmin(admin.ModelAdmin):
	list_display = ['name', 'id', 'last_seen']



@admin.register(Costume)
class CostumeAdmin(admin.ModelAdmin):
	list_display = ['description', 'id', 'animal']



@admin.register(ContactPerson)
class ContactPersonAdmin(admin.ModelAdmin):
	list_display = ['name', 'id']



@admin.register(Zoo)
class ZooAdmin(admin.ModelAdmin):
	list_display = ['name', 'id', 'founding_date', 'floor_plan']
