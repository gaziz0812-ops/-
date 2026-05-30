from django.contrib import admin

from .models import StockMovement, StockBatch


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'movement_type', 'quantity', 'created_at')
    list_filter = ('movement_type', 'created_at')
    search_fields = ('product__sku', 'product__name')


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'product',
        'quantity',
        'remaining_quantity',
        'unit_cost',
        'source_type',
        'source_id',
        'created_at',
    )
    list_filter = ('created_at', 'source_type')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = (
        'product',
        'quantity',
        'remaining_quantity',
        'unit_cost',
        'source_type',
        'source_id',
        'created_at',
    )
