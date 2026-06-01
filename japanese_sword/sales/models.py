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
    cost_price = models.DecimalField(
        'Себестоимость за 1 шт.',
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00'),
    )
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
        self.cost_price = Decimal('0.00')
        self.profit = Decimal('0.00')

        with transaction.atomic():
            super().save(*args, **kwargs)
            total_cost = self.sync_cost_allocations()
            self.cost_price = total_cost / self.quantity
            self.profit = self.total_sale_amount - total_cost
            super().save(update_fields=['cost_price', 'profit'])
            self.sync_stock_movement()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.restore_cost_allocations()
            self.delete_stock_movement()
            super().delete(*args, **kwargs)

    def sync_cost_allocations(self):
        from stock.models import StockBatch

        self.restore_cost_allocations()

        remaining_quantity = self.quantity
        total_cost = Decimal('0.00')
        batches = StockBatch.objects.select_for_update().filter(
            product=self.product,
            remaining_quantity__gt=0,
        ).order_by('created_at', 'id')

        for batch in batches:
            if remaining_quantity <= 0:
                break

            quantity_from_batch = min(batch.remaining_quantity, remaining_quantity)
            batch.remaining_quantity -= quantity_from_batch
            batch.save(update_fields=['remaining_quantity'])

            allocation = SaleCostAllocation.objects.create(
                sale=self,
                stock_batch=batch,
                quantity=quantity_from_batch,
                unit_cost=batch.unit_cost,
            )
            total_cost += allocation.total_cost
            remaining_quantity -= quantity_from_batch

        if remaining_quantity > 0:
            raise ValidationError({
                'quantity': 'Недостаточно товара в партиях для FIFO-списания.'
            })

        return total_cost

    def restore_cost_allocations(self):
        from stock.models import StockBatch

        allocations = self.cost_allocations.select_related('stock_batch')
        for allocation in allocations:
            batch = StockBatch.objects.select_for_update().get(pk=allocation.stock_batch_id)
            batch.remaining_quantity += allocation.quantity
            batch.save(update_fields=['remaining_quantity'])

        allocations.delete()

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

    def delete_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.filter(
            source_type='sale',
            source_id=self.pk,
        ).delete()

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


class SaleReturn(models.Model):
    class Destination(models.TextChoices):
        BACK_TO_STOCK = 'back_to_stock', 'Вернуть на продажу'
        WRITE_OFF = 'write_off', 'Списать'

    sale = models.ForeignKey(
        Sale,
        on_delete=models.PROTECT,
        related_name='returns',
        verbose_name='Продажа'
    )
    quantity = models.PositiveIntegerField('Количество')
    refund_amount = models.DecimalField('Сумма возврата', max_digits=12, decimal_places=2)
    destination = models.CharField(
        'Куда определить товар',
        max_length=20,
        choices=Destination.choices,
    )
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Возврат'
        verbose_name_plural = 'Возвраты'

    def clean(self):
        super().clean()

        if self.sale_id and self.quantity:
            available_quantity = self.get_available_quantity_to_return()

            if self.pk:
                current_return_quantity = (
                    SaleReturn.objects
                    .filter(pk=self.pk)
                    .values_list('quantity', flat=True)
                    .first()
                ) or 0

                available_quantity += current_return_quantity

            if self.quantity > available_quantity:
                raise ValidationError({
                    'quantity': f'Нельзя вернуть больше доступного количества. Доступно к возврату: {available_quantity}'
                })

    def get_available_quantity_to_return(self):
        already_returned_quantity = (
            self.sale.returns
            .exclude(pk=self.pk)
            .aggregate(total=models.Sum('quantity'))
            .get('total')
        ) or 0

        return self.sale.quantity - already_returned_quantity

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.full_clean()
            super().save(*args, **kwargs)
            self.sync_stock_movements()

            if self.destination == self.Destination.BACK_TO_STOCK:
                self.restore_sale_batches()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.delete_stock_movements()
            super().delete(*args, **kwargs)

    def sync_stock_movements(self):
        from stock.models import StockMovement

        StockMovement.objects.update_or_create(
            source_type='sale_return',
            source_id=self.pk,
            defaults={
                'product': self.sale.product,
                'movement_type': StockMovement.MovementType.RETURN,
                'quantity': self.quantity,
            },
        )

        if self.destination == self.Destination.WRITE_OFF:
            StockMovement.objects.update_or_create(
                source_type='sale_return_write_off',
                source_id=self.pk,
                defaults={
                    'product': self.sale.product,
                    'movement_type': StockMovement.MovementType.WRITE_OFF,
                    'quantity': self.quantity,
                },
            )
        else:
            StockMovement.objects.filter(
                source_type='sale_return_write_off',
                source_id=self.pk,
            ).delete()

    def restore_sale_batches(self):
        remaining_quantity = self.quantity

        for allocation in self.sale.cost_allocations.select_related('stock_batch').order_by('created_at', 'id'):
            if remaining_quantity <= 0:
                break

            quantity_to_restore = min(allocation.quantity, remaining_quantity)
            batch = allocation.stock_batch
            batch.remaining_quantity += quantity_to_restore
            batch.save(update_fields=['remaining_quantity'])
            remaining_quantity -= quantity_to_restore

    def delete_stock_movements(self):
        from stock.models import StockMovement

        StockMovement.objects.filter(
            source_type__in=['sale_return', 'sale_return_write_off'],
            source_id=self.pk,
        ).delete()

    def __str__(self):
        return f'Возврат #{self.pk} по продаже #{self.sale_id}'
