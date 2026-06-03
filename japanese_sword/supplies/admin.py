from django.contrib import admin
from django import forms
from django.db import models

from .models import ManualSupply, ManualSupplyItem, Supply, SupplyItem


# Inline позволяет заполнять позиции расчетной поставки прямо внутри формы Supply.
class SupplyItemInline(admin.TabularInline):
    model = SupplyItem
    verbose_name = 'Позиция поставки'
    verbose_name_plural = 'Позиции поставки'
    extra = 1
    readonly_fields = (
        'product_cost_rub',
        'allocated_shipping_cost',
        'calculated_unit_cost',
    )

class ManualSupplyItemInline(admin.TabularInline):
    # Inline позволяет заполнять ручные позиции прямо внутри формы ManualSupply.
    model = ManualSupplyItem
    verbose_name = 'Ручная позиция поставки'
    verbose_name_plural = 'Ручные позиции поставки'
    extra = 1
    readonly_fields = ('total_cost',)
    formfield_overrides = {
        # Для TextField в inline уменьшаем textarea, чтобы таблица не растягивалась на полэкрана.
        models.TextField: {
            'widget': forms.Textarea(attrs={'rows': 2, 'cols': 30}),
        },
    }


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    # save_related вызывается Django admin после сохранения Supply и всех inline-позиций.
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)

        # После сохранения позиций пересчитываем себестоимость всей поставки.
        form.instance.recalculate_costs()


    list_display = (
        'id',
        'supply_date',
        'yuan_rate',
        'cargo_commission_percent',
        'total_shipping_cost',
        'total_package_weight',
        'created_at',
    )
    list_filter = ('supply_date',)
    search_fields = ('order_url',)
    inlines = (SupplyItemInline,)
    fieldsets = (
        ('Поставка', {
            'fields': ('supply_date', 'order_url', 'comment'),
        }),
        ('Расчёт себестоимости', {
            'fields': ('yuan_rate', 'cargo_commission_percent', 'total_shipping_cost', 'total_package_weight'),
        }),
    )


@admin.register(ManualSupply)
class ManualSupplyAdmin(admin.ModelAdmin):
    # Ручная поставка использует inline без юаней/веса/доставки, только ручную себестоимость.
    list_display = (
        'id',
        'supply_date',
        'comment',
        'created_at',
    )
    list_filter = ('supply_date',)
    search_fields = ('comment',)
    inlines = (ManualSupplyItemInline,)
    fieldsets = (
        ('Ручная поставка', {
            'fields': ('supply_date', 'comment'),
        }),
    )
