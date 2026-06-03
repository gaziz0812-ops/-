from django.contrib import admin
from django import forms
from django.db import models

from .models import Manufacturer


# @admin.register связывает Manufacturer с настройками ManufacturerAdmin в админке.
@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ('id', 'name')
    search_fields = ('name',)

    # formfield_overrides меняет виджет всех CharField только в этой админской форме.
    formfield_overrides = {
        models.CharField: {
            'widget': forms.TextInput(attrs={'style': 'width: 350px;'}),
        },
    }
