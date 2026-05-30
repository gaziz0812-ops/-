from django.contrib import admin

from .models import ManualSupply, ManualSupplyItem, Supply, SupplyItem


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
    model = ManualSupplyItem
    verbose_name = 'Ручная позиция поставки'
    verbose_name_plural = 'Ручные позиции поставки'
    extra = 1
    readonly_fields = ('total_cost',)


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
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
