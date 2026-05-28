from django.contrib import admin

from .models import Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'sku', 'name', 'manufacturer', 'sale_price', 'is_active', 'stock_balance')  # отобразится в админке
    list_filter = ('is_active', 'manufacturer')  # фильтр
    search_fields = ('sku', 'name')  # поиск