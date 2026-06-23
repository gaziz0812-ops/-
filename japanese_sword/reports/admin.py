from django.contrib import admin
from django.db.models import Avg, Count, Sum
from django.template.response import TemplateResponse
from django.urls import path
from django.utils.dateparse import parse_date

from sales.models import Sale, SaleReturn
from orders.models import Order

# [OUR] Сохраняем стандартный метод admin.site.get_urls, чтобы не потерять обычные URL админки.
original_get_urls = admin.site.get_urls


# [OUR] Страница отчета по продажам внутри Django admin.
def sales_summary_view(request):
    date_from_raw = request.GET.get('date_from', '')
    date_to_raw = request.GET.get('date_to', '')

    date_from = parse_date(date_from_raw) if date_from_raw else None
    date_to = parse_date(date_to_raw) if date_to_raw else None

    sales = Sale.objects.select_related('product')

    if date_from:
        sales = sales.filter(created_at__date__gte=date_from)

    if date_to:
        sales = sales.filter(created_at__date__lte=date_to)

    returns = SaleReturn.objects.all()

    if date_from:
        returns = returns.filter(created_at__date__gte=date_from)

    if date_to:
        returns = returns.filter(created_at__date__lte=date_to)

    # [OUR] Берем заказы отдельно от продаж: заказ может существовать еще до проведения продажи.
    orders = Order.objects.all()

    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)

    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)

    summary = sales.aggregate(
        sales_count=Count('id'),
        revenue=Sum('total_sale_amount'),
        profit=Sum('profit'),
        average_order=Avg('total_sale_amount'),
        sold_items=Sum('quantity'),
    )

    returns_summary = returns.aggregate(
        refund_amount=Sum('refund_amount'),
        returns_count=Count('id'),
    )

    # [OUR] Группируем заказы по статусам: new, paid, sold, shipped и т.д.
    orders_by_status = {
        item['status']: item['count']
        for item in orders.values('status').annotate(count=Count('id'))
    }

    # [OUR] Общая статистика по заказам за выбранный период.
    orders_summary = orders.aggregate(
        orders_count=Count('id'),
        orders_amount=Sum('total_amount'),
    )

    top_products = (
        sales
        .values('product__sku', 'product__name')
        .annotate(
            sold_quantity=Sum('quantity'),
            revenue=Sum('total_sale_amount'),
            profit=Sum('profit'),
        )
        .order_by('-revenue')[:10]
    )

    revenue = summary['revenue'] or 0
    refund_amount = returns_summary['refund_amount'] or 0
    net_revenue = revenue - refund_amount

    context = {
        **admin.site.each_context(request),
        'title': 'Сводка продаж',
        'date_from': date_from_raw,
        'date_to': date_to_raw,
        'summary': {
            'sales_count': summary['sales_count'] or 0,
            'revenue': revenue,
            'refund_amount': refund_amount,
            'net_revenue': net_revenue,
            'returns_count': returns_summary['returns_count'] or 0,
            'profit': summary['profit'] or 0,
            'average_order': summary['average_order'] or 0,
            'sold_items': summary['sold_items'] or 0,
        },
        'orders_summary': {
            'orders_count': orders_summary['orders_count'] or 0,
            'orders_amount': orders_summary['orders_amount'] or 0,
            'new': orders_by_status.get(Order.Status.NEW, 0),
            'in_progress': orders_by_status.get(Order.Status.IN_PROGRESS, 0),
            'waiting_payment': orders_by_status.get(Order.Status.WAITING_PAYMENT, 0),
            'paid': orders_by_status.get(Order.Status.PAID, 0),
            'sold': orders_by_status.get(Order.Status.SOLD, 0),
            'shipped': orders_by_status.get(Order.Status.SHIPPED, 0),
            'cancelled': orders_by_status.get(Order.Status.CANCELLED, 0),
        },
        'top_products': top_products,
    }

    return TemplateResponse(
        request,
        'admin/reports/sales_summary.html',
        context,
    )


# [OUR] Добавляет наш URL отчета к стандартным URL Django admin.
def get_reports_urls():
    urls = original_get_urls()

    custom_urls = [
        path(
            'reports/sales-summary/',
            admin.site.admin_view(sales_summary_view),
            name='reports_sales_summary',
        ),
    ]

    return custom_urls + urls


# [DJANGO] Подменяем get_urls у admin.site, чтобы админка знала про нашу страницу отчета.
admin.site.get_urls = get_reports_urls