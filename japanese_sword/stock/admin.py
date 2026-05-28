from django.contrib import admin

from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'movement_type', 'quantity', 'created_at')  # что отобразится в админке
    list_filter = ('movement_type', 'created_at')  # фильтр в админке
    search_fields = ('product__sku', 'product__name')  # по каким параметрам поиск в админке