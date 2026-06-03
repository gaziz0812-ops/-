from django.db import models
from django.db.models import Sum


# Модель Product описывает таблицу товаров в БД.
class Product(models.Model):
    sku = models.CharField('Артикул', max_length=15, unique=True)
    name = models.CharField('Название', max_length=255)

    # ForeignKey связывает товар с производителем; related_name дает обратный доступ manufacturer.products.
    manufacturer = models.ForeignKey(
        'manufacturers.Manufacturer',
        on_delete=models.PROTECT,
        related_name='products',
        verbose_name='Производитель',
    )
    description = models.TextField('Описание', blank=True)
    sale_price = models.DecimalField('Цена, руб.', max_digits=10, decimal_places=2)
    is_active = models.BooleanField('Активен', default=True)

    class Meta:
        verbose_name = 'Товар'
        verbose_name_plural = 'Товары'

    def __str__(self):
        return f'Арт.{self.sku} - {self.name}'

    # @property делает вычисляемый остаток доступным как product.stock_balance без скобок.
    @property
    def stock_balance(self):
        # self.stock_movements идет по related_name из StockMovement и берет движения текущего товара.
        totals = self.stock_movements.values('movement_type').annotate(
            total=Sum('quantity')
        )

        # Превращаем queryset со сгруппированными суммами в обычный словарь movement_type -> total.
        movement_totals = {item['movement_type']: item['total'] for item in totals}

        # get(..., 0) защищает от отсутствующего типа движения, or 0 защищает от None.
        inbound = movement_totals.get('inbound', 0) or 0
        returned = movement_totals.get('return', 0) or 0
        sale = movement_totals.get('sale', 0) or 0
        write_off = movement_totals.get('write_off', 0) or 0
        reserve = movement_totals.get('reserve', 0) or 0
        unreserve = movement_totals.get('unreserve', 0) or 0

        # Остаток считается из журнала движений, а не хранится отдельным полем в Product.
        return inbound + returned + unreserve - sale - write_off - reserve
