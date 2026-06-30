from django.contrib import admin

from .models import Product, ProductImage


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1


# @admin.register связывает модель Product с настройками ProductAdmin в админке.
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    # list_display определяет колонки в списке товаров админки.
    list_display = ('id', 'sku', 'name', 'manufacturer', 'sale_price', 'is_active', 'display_stock_balance')

    # list_filter добавляет боковые фильтры в админке.
    list_filter = ('is_active', 'manufacturer')

    # search_fields включает поиск по артикулу и названию товара.
    search_fields = ('sku', 'name')

    inlines = (ProductImageInline,)

    # admin.display задает название вычисляемой колонки в админке.
    @admin.display(description='Остаток')
    def display_stock_balance(self, obj):
        # obj здесь конкретный Product из строки админки, не ProductAdmin.
        return obj.stock_balance


