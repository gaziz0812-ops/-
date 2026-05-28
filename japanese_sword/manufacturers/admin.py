from django.contrib import admin

from .models import Manufacturer


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')  # что будет отображаться в админке
    search_fields = ('name',)  # по какому параметру можно сделать поиск