from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from .forms import SaleAdminForm, SaleReturnAdminForm
from .models import Sale, SaleCostAllocation, SaleReturn


# Inline показывает в продаже, из каких партий FIFO списал товар.
class SaleCostAllocationInline(admin.TabularInline):
    model = SaleCostAllocation
    verbose_name = 'Партия продажи'
    verbose_name_plural = 'Партии продажи'
    extra = 0
    can_delete = False
    fields = ('stock_batch', 'quantity')
    readonly_fields = ('stock_batch', 'quantity')

    def has_add_permission(self, request, obj=None):
        # Партии продажи создаются кодом FIFO, вручную добавлять их нельзя.
        return False


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    # form подключает кастомную форму с data-атрибутами для JS-preview цены и остатка.
    form = SaleAdminForm
    list_display = (
        'display_sale_number',
        'order',
        'order_item',
        'product',
        'customer',
        'quantity',
        'discount_percent',
        'unit_sale_price',
        'total_sale_amount',
        'cost_price',
        'profit',
        'created_at',
    )
    list_filter = ('order__status', 'created_at')
    search_fields = ('id', 'order__id', 'order_item__id', 'product__sku', 'product__name', 'customer__username')
    readonly_fields = ('unit_sale_price', 'total_sale_amount', 'cost_price', 'profit', 'created_at')
    inlines = (SaleCostAllocationInline,)
    fieldsets = (
        ('Продажа', {
            'fields': ('order', 'order_item', 'product', 'customer', 'quantity', 'discount_percent', 'comment'),
        }),
        ('Расчёт', {
            'fields': ('unit_sale_price', 'total_sale_amount', 'profit'),
        }),
        ('Служебные данные', {
            'fields': ('created_at',),
        }),
    )

    class Media:
        # Media подключает JS-файл только на страницах админки этой модели.
        js = ('sales/admin_sale_calculator.js',)

    @admin.display(description='Номер продажи', ordering='id')
    def display_sale_number(self, obj):
        # obj здесь конкретная Sale из строки списка админки.
        return obj.id

    def has_delete_permission(self, request, obj=None):
        # Продажа — исторический факт, поэтому удаление через админку запрещено.
        return False

    def has_add_permission(self, request):
        # Продажи теперь создаются из заказа, а раздел Sale работает как журнал фактов продажи.
        return False

    def get_readonly_fields(self, request, obj=None):
        # При просмотре существующей продажи все бизнес-поля становятся readonly.
        if obj:
            return (
                'order',
                'order_item',
                'product',
                'customer',
                'quantity',
                'discount_percent',
                'comment',
                'unit_sale_price',
                'total_sale_amount',
                'cost_price',
                'profit',
                'created_at',
            )

        return self.readonly_fields


@admin.register(SaleReturn)
class SaleReturnAdmin(admin.ModelAdmin):
    form = SaleReturnAdminForm
    list_display = (
        'id',
        'order',
        'sale',
        'quantity',
        'refund_amount',
        'destination',
        'created_at',
    )
    list_filter = ('destination', 'created_at',)
    search_fields = (
        'id',
        'order__id',
        'sale__product__sku',
        'sale__product__name',
        'sale__customer__username',
    )
    readonly_fields = ('created_at',)
    autocomplete_fields = ('order',)
    fieldsets = (
        ('Возврат', {
            'fields': ('order', 'sale', 'quantity', 'refund_amount', 'destination', 'comment'),
        }),
        ('Служебные данные', {
            'fields': ('created_at',),
        }),
    )

    class Media:
        # JS показывает preview выбранной продажи при оформлении возврата.
        js = ('sales/admin_sale_return_preview_v2.js',)

    def get_urls(self):
        # get_urls расширяет стандартные URL админки кастомным endpoint для preview продажи.
        urls = super().get_urls()
        custom_urls = [
            path(
                'sale-preview/<int:sale_id>/',
                self.admin_site.admin_view(self.sale_preview),
                name='sales_salereturn_sale_preview',
            ),
            path(
                'sales-for-order/<int:order_id>/',
                self.admin_site.admin_view(self.sales_for_order),
                name='sales_salereturn_sales_for_order',
            ),
        ]
        return custom_urls + urls

    def sale_preview(self, request, sale_id):
        # Этот admin endpoint возвращает JSON с данными продажи для JS-preview.
        sale = Sale.objects.select_related('order', 'product', 'customer').get(pk=sale_id)

        return JsonResponse({
            'id': sale.id,
            'order': sale.order_id,
            'product': str(sale.product),
            'customer': str(sale.customer) if sale.customer else '',
            'quantity': sale.quantity,
            'discount_percent': str(sale.discount_percent),
            'unit_sale_price': str(sale.unit_sale_price),
            'total_sale_amount': str(sale.total_sale_amount),
            'created_at': sale.created_at.strftime('%d.%m.%Y %H:%M'),
        })

    def sales_for_order(self, request, order_id):
        # Endpoint возвращает продажи выбранного заказа, чтобы админ мог выбрать позицию возврата.
        sales = (
            Sale.objects
            .select_related('product')
            .filter(order_id=order_id)
            .order_by('id')
        )

        return JsonResponse({
            'sales': [
                {
                    'id': sale.id,
                    'text': f'Продажа #{sale.id} - {sale.product} x {sale.quantity}',
                }
                for sale in sales
            ]
        })

    def has_delete_permission(self, request, obj=None):
        # Возврат тоже исторический факт, поэтому удаление через админку запрещено.
        return False

    def get_readonly_fields(self, request, obj=None):
        # После создания возврат нельзя редактировать напрямую.
        if obj:
            return (
                'order',
                'sale',
                'quantity',
                'refund_amount',
                'destination',
                'comment',
                'created_at',
            )

        return self.readonly_fields
