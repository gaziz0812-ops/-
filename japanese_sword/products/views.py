# Decimal нужен для безопасной работы с денежными значениями
# InvalidOperation возникает, если строку нельзя преобразовать в Decimal
from decimal import Decimal, InvalidOperation

# ValidationError DRF возвращает клиенту HTTP 400 Bad Request
from rest_framework.exceptions import ValidationError

# filters содержит готовые DRF-фильтры для поиска и сортировки.
# viewsets содержит готовые DRF-классы для API-представлений.
from rest_framework import filters, viewsets

from .models import Product
from .serializers import ProductDetailSerializer, ProductSerializer


# ReadOnlyModelViewSet дает публичному API только чтение: список товаров и один товар.
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    # Специальный метод DRF: возвращает queryset товаров для текущего HTTP-запроса
    def get_queryset(self):
        # Базовый queryset: публичный каталог показывает только активные товары
        queryset = Product.objects.filter(is_active=True)

        # query_params читает параметры URL после знака ? и после разделителей &.
        stock = self.request.query_params.get('stock')
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')

        # stock=available показывает товары с остатком, stock=out — товары без остатка
        if stock in ('available', 'out'):
            product_ids = [
                product.id
                for product in queryset
                if (
                    product.stock_balance > 0
                    if stock == 'available'
                    else product.stock_balance <= 0
                )
            ]

            # id__in оставляет в queryset только товары, id которых есть в списке product_ids
            queryset = queryset.filter(id__in=product_ids)

        # min_price приходит из URL строкой, поэтому преобразуем его в Decimal
        if min_price:
            try:
                min_price = Decimal(min_price)
            except InvalidOperation:
                raise ValidationError({
                    'min_price': 'Минимальная цена должна быть числом.'
                })

        # max_price приходит из URL строкой, поэтому преобразуем его в Decimal
        if max_price:
            try:
                max_price = Decimal(max_price)
            except InvalidOperation:
                raise ValidationError({
                    'max_price': 'Максимальная цена должна быть числом.'
                })

        # Если переданы обе цены, минимальная не должна быть больше максимальной
        if min_price and max_price and min_price > max_price:
            raise ValidationError({
                'max_price': 'Максимальная цена должна быть больше или равна минимальной.'
            })

        # sale_price__gte означает "цена больше или равна min_price"
        if min_price:
            queryset = queryset.filter(sale_price__gte=min_price)

        # sale_price__lte означает "цена меньше или равна max_price"
        if max_price:
            queryset = queryset.filter(sale_price__lte=max_price)

        # DRF ждет, что get_queryset вернет итоговый queryset для serializer
        return queryset

    # Специальный метод DRF: выбирает serializer в зависимости от действия ViewSet.
    def get_serializer_class(self):
        # self.action — специальный атрибут DRF: list для списка, retrieve для одного объекта.
        if self.action == 'retrieve':
            return ProductDetailSerializer

        # Для списка товаров оставляем короткий публичный serializer.
        return ProductSerializer

    # Специальный атрибут DRF: каким serializer превращать Product в JSON.  Если есть get_serializer, то превращается
    # в атрибут по сериализатор по умолчанию
    serializer_class = ProductSerializer

    # Специальный атрибут DRF: эти backend-классы дополнительно обрабатывают queryset.
    filter_backends = (filters.SearchFilter, filters.OrderingFilter,)

    # Специальный атрибут SearchFilter: поля, по которым работает ?search=
    search_fields = ('sku', 'name')

    # Специальный атрибут OrderingFilter: поля, по которым разрешена сортировка
    ordering_fields = ('name', 'sale_price')

    # Специальный атрибут OrderingFilter: сортировка по умолчанию
    ordering = ('name',)
