from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db import transaction
from django.core.exceptions import ValidationError

class Sale(models.Model):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name='Товар',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name='Покупатель',
    )
    quantity = models.PositiveIntegerField('Количество')
    discount_percent = models.DecimalField(
        'Скидка, %',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    unit_sale_price = models.DecimalField('Цена за 1 шт. со скидкой', max_digits=10, decimal_places=2, editable=False)
    total_sale_amount = models.DecimalField('Сумма продажи', max_digits=10, decimal_places=2, editable=False)
    cost_price = models.DecimalField('Себестоимость за 1 шт.', max_digits=10, decimal_places=2)
    profit = models.DecimalField('Прибыль', max_digits=10, decimal_places=2, editable=False)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Продажа'
        verbose_name_plural = 'Продажи'

    def save(self, *args, **kwargs):
        discount_multiplier = Decimal('1.00') - (self.discount_percent / Decimal('100.00'))

        self.unit_sale_price = self.product.sale_price * discount_multiplier
        self.total_sale_amount = self.unit_sale_price * self.quantity
        self.profit = self.total_sale_amount - (self.cost_price * self.quantity)

        with transaction.atomic():
            super().save(*args, **kwargs)
            self.sync_stock_movement()

    def sync_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.update_or_create(
            source_type='sale',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.SALE,
                'quantity': self.quantity,
            },
        )

    def __str__(self):
        return f'Продажа #{self.pk} - {self.product}'

    def clean(self):
        super().clean()

        if self.product_id and self.quantity:
            available_quantity = self.product.stock_balance

            if self.pk:
                current_sale_quantity = (
                    Sale.objects
                    .filter(pk=self.pk)
                    .values_list('quantity', flat=True)
                    .first()
                ) or 0

                available_quantity += current_sale_quantity

            if self.quantity > available_quantity:
                raise ValidationError({
                    'quantity': f'Недостаточно товара на складе. Доступно: {available_quantity}'
                })


class SaleCostAllocation(models.Model):
    sale = models.ForeignKey(
        Sale,
        on_delete=models.CASCADE,
        related_name='cost_allocations',
        verbose_name='Продажа',
    )
    stock_batch = models.ForeignKey(
        'stock.StockBatch',
        on_delete=models.PROTECT,
        related_name='sale_allocations',
        verbose_name='Партия товара',
    )
    quantity = models.PositiveIntegerField('Количество')
    unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2)
    total_cost = models.DecimalField('Себестоимость списания, руб.', max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Списание себестоимости'
        verbose_name_plural = 'Списания себестоимости'

    def save(self, *args, **kwargs):
        self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Продажа #{self.sale_id} | {self.quantity} шт. из партии #{self.stock_batch_id}'