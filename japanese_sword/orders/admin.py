from django.contrib import admin

from .models import Order, OrderItem


# Inline показывает позиции заказа прямо внутри страницы Order.
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = ('product', 'quantity', 'unit_price', 'total_price')
    readonly_fields = ('unit_price', 'total_price')
    autocomplete_fields = ('product',)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer_name',
        'telegram_username',
        'status',
        'total_amount',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'id',
        'customer_name',
        'telegram_username',
        'phone',
        'tracking_number',
    )
    readonly_fields = ('total_amount', 'created_at')
    inlines = (OrderItemInline,)
    fieldsets = (
        ('Клиент', {
            'fields': ('customer_name', 'telegram_username', 'phone'),
        }),
        ('Заказ', {
            'fields': ('status', 'customer_comment', 'internal_comment'),
        }),
        ('Оплата и доставка', {
            'fields': ('paid_at', 'shipped_at', 'tracking_number'),
        }),
        ('Служебные данные', {
            'fields': ('total_amount', 'created_at'),
        }),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'order',
        'product',
        'quantity',
        'unit_price',
        'total_price',
    )
    list_filter = ('order__status',)
    search_fields = (
        'order__id',
        'product__sku',
        'product__name',
    )
    readonly_fields = ('unit_price', 'total_price')
    autocomplete_fields = ('order', 'product')