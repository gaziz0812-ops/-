from django.contrib import admin

from .models import StockMovement, StockBatch


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'product',
        'movement_type',
        'quantity',
        'display_source_type',
        'source_id',
        'created_at'
    )
    list_filter = ('movement_type', 'source_type', 'created_at')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = (
        'product',
        'movement_type',
        'quantity',
        'display_source_type',
        'source_id',
        'created_at',
    )

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        source_type_names = {
            'sale': 'Продажа',
            'supply_item': 'Позиция поставки',
            'manual_supply_item': 'Ручная позиция поставки',
        }
        return source_type_names.get(obj.source_type, obj.source_type)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'product',
        'quantity',
        'remaining_quantity',
        'unit_cost',
        'display_source_type',
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
        'display_source_type',
        'source_id',
        'created_at',
    )

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        source_type_names = {
            'sale': 'Продажа',
            'supply_item': 'Позиция поставки',
            'manual_supply_item': 'Ручная позиция поставки',
        }
        return source_type_names.get(obj.source_type, obj.source_type)


    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False
