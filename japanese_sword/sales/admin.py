from django.contrib import admin

from .models import Sale


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'product',
        'customer',
        'quantity',
        'sale_price',
        'cost_price',
        'profit',
        'created_at',
    )
    list_filter = ('created_at',)
    search_fields = ('product__sku', 'product__name', 'customer__username')
    readonly_fields = ('profit', 'created_at')