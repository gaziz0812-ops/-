from django.contrib import admin

from .models import Supply, SupplyItem


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


@admin.register(Supply)
class SupplyAdmin(admin.ModelAdmin):
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        form.instance.recalculate_costs()


    list_display = (
        'id',
        'manufacturer',
        'supply_date',
        'yuan_rate',
        'cargo_commission_percent',
        'total_shipping_cost',
        'total_package_weight',
        'created_at',
    )
    list_filter = ('supply_date', 'manufacturer')
    search_fields = ('manufacturer__name', 'order_url')
    inlines = (SupplyItemInline,)
    fieldsets = (
        ('Поставка', {
            'fields': ('manufacturer', 'supply_date', 'order_url', 'comment'),
        }),
        ('Расчёт себестоимости', {
            'fields': ('yuan_rate', 'cargo_commission_percent', 'total_shipping_cost', 'total_package_weight'),
        }),
    )


@admin.register(SupplyItem)
class SupplyItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'supply',
        'product',
        'quantity',
        'price_yuan',
        'china_shipping_yuan',
        'unit_weight',
        'calculated_unit_cost',
    )
    list_filter = ('supply', 'product')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = (
        'product_cost_rub',
        'allocated_shipping_cost',
        'calculated_unit_cost',
    )
    fieldsets = (
        ('Позиция поставки', {
            'fields': ('supply', 'product', 'quantity', 'price_yuan', 'china_shipping_yuan', 'unit_weight'),
        }),
        ('Расчёт', {
            'fields': ('product_cost_rub', 'allocated_shipping_cost', 'calculated_unit_cost'),
        }),
    )
