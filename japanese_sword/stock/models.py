from django.db import models


class StockMovement(models.Model):
    class MovementType(models.TextChoices):
        INBOUND = 'inbound', 'Приход'
        SALE = 'sale', 'Продажа'
        RETURN = 'return', 'Возврат'
        WRITE_OFF = 'write_off', 'Списание'
        RESERVE = 'reserve', 'Резерв'
        UNRESERVE = 'unreserve', 'Снятие резерва'

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='stock_movements',
        verbose_name='Товар',
    )
    movement_type = models.CharField(
        'Тип движения',
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.IntegerField('Количество')
    source_type = models.CharField('Тип источника', max_length=50, blank=True)
    source_id = models.PositiveBigIntegerField('ID источника', null=True, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Движение склада'
        verbose_name_plural = 'Движения склада'

    def __str__(self):
        return f'{self.product} | {self.movement_type} | {self.quantity}'


class StockBatch(models.Model):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='stock_batches',
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField('Количество в партии')
    unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2)
    remaining_quantity = models.PositiveIntegerField('Остаток в партии')
    source_type = models.CharField('Тип источника', max_length=50)
    source_id = models.PositiveBigIntegerField('ID источника')
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'партию товара'
        verbose_name_plural = 'Партии товаров'
        ordering = ('created_at', 'id')

    def __str__(self):
        return f'{self.product} | осталось {self.remaining_quantity} из {self.quantity}'