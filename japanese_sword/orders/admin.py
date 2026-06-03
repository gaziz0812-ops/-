from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.urls import path

from products.models import Product

from .forms import OrderItemAdminForm
from .models import Order, OrderItem


# Inline показывает позиции заказа прямо внутри страницы Order.
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    form = OrderItemAdminForm
    extra = 1
    fields = ('product', 'quantity', 'discount_percent', 'unit_price', 'unit_price_after_discount', 'total_price')
    readonly_fields = ('unit_price', 'unit_price_after_discount', 'total_price')
    autocomplete_fields = ('product',)

    def get_readonly_fields(self, request, obj=None):
        # После проведения продажи позиции заказа становятся историческим документом.
        if obj and obj.sales.exists():
            return ('product', 'quantity', 'discount_percent', 'unit_price', 'unit_price_after_discount', 'total_price')

        return self.readonly_fields

    def has_add_permission(self, request, obj=None):
        # Нельзя добавлять товары в заказ, по которому уже проведена продажа.
        if obj and obj.sales.exists():
            return False

        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        # Нельзя удалять позиции заказа после проведения продажи.
        if obj and obj.sales.exists():
            return False

        return super().has_delete_permission(request, obj)


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'customer_name',
        'telegram_username',
        'status',
        'total_amount',
        'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = (
        'id',
        'customer__username',
        'customer_name',
        'telegram_username',
        'phone',
        'tracking_number',
    )
    readonly_fields = ('total_amount', 'created_at')
    autocomplete_fields = ('customer',)
    inlines = (OrderItemInline,)
    actions = ('conduct_sales',)
    fieldsets = (
        ('Клиент', {
            'fields': ('customer', 'customer_name', 'telegram_username', 'phone'),
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

    class Media:
        # Media подключает JS live preview только на страницах админки заказа.
        js = ('orders/admin_order_item_preview_v2.js',)

    def get_urls(self):
        # get_urls добавляет admin endpoint, из которого JS получает цену и остаток товара.
        urls = super().get_urls()
        custom_urls = [
            path(
                'product-preview/<int:product_id>/',
                self.admin_site.admin_view(self.product_preview),
                name='orders_order_product_preview',
            ),
        ]
        return custom_urls + urls

    def product_preview(self, request, product_id):
        # Endpoint возвращает JSON для live preview позиции заказа.
        product = Product.objects.get(pk=product_id)

        return JsonResponse({
            'id': product.id,
            'name': str(product),
            'sale_price': str(product.sale_price),
            'stock_balance': product.stock_balance,
        })

    @admin.action(description='Провести продажу по выбранным заказам')
    def conduct_sales(self, request, queryset):
        # Admin action запускает бизнес-метод Order.conduct_sales() для выбранных заказов.
        success_count = 0

        for order in queryset:
            try:
                order.conduct_sales()
            except ValidationError as error:
                message = '; '.join(error.messages)
                self.message_user(request, f'Заказ #{order.pk}: {message}', messages.ERROR)
            else:
                success_count += 1

        if success_count:
            self.message_user(request, f'Проведено заказов: {success_count}', messages.SUCCESS)

    def get_readonly_fields(self, request, obj=None):
        # После проведения продажи фиксируем клиентские и финансовые данные заказа.
        if obj and obj.sales.exists():
            return (
                'customer',
                'customer_name',
                'telegram_username',
                'phone',
                'customer_comment',
                'total_amount',
                'created_at',
            )

        return self.readonly_fields


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    form = OrderItemAdminForm
    list_display = (
        'id',
        'order',
        'product',
        'quantity',
        'discount_percent',
        'unit_price',
        'unit_price_after_discount',
        'total_price',
    )
    list_filter = ('order__status',)
    search_fields = (
        'order__id',
        'product__sku',
        'product__name',
    )
    readonly_fields = ('unit_price', 'unit_price_after_discount', 'total_price')
    autocomplete_fields = ('order', 'product')

    def get_readonly_fields(self, request, obj=None):
        # Если по заказу уже есть продажи, позиция становится только для чтения.
        if obj and obj.order.sales.exists():
            return ('order', 'product', 'quantity', 'discount_percent', 'unit_price', 'unit_price_after_discount', 'total_price')

        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        # Нельзя удалить позицию, если по ее заказу уже проведена продажа.
        if obj and obj.order.sales.exists():
            return False

        return super().has_delete_permission(request, obj)
