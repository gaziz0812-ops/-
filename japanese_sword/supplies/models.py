from decimal import Decimal

from django.db import models


class Supply(models.Model):
    def recalculate_costs(self):
        items = list(self.items.all())
        if not items:
            return

        total_clean_weight = sum(item.unit_weight * item.quantity for item in items)
        if not total_clean_weight or not self.total_package_weight:
            return

        shipping_price_per_kg = self.total_shipping_cost / self.total_package_weight
        commission_multiplier = Decimal('1.00') + (self.cargo_commission_percent / Decimal('100.00'))

        for item in items:
            item_clean_weight = item.unit_weight * item.quantity
            item_package_weight = self.total_package_weight * item_clean_weight / total_clean_weight
            allocated_shipping_cost = item_package_weight * shipping_price_per_kg

            product_cost_rub = (
                (item.price_yuan * item.quantity + item.china_shipping_yuan)
                * commission_multiplier
                * self.yuan_rate
            )

            item.product_cost_rub = product_cost_rub
            item.allocated_shipping_cost = allocated_shipping_cost
            item.calculated_unit_cost = (
                product_cost_rub + allocated_shipping_cost
            ) / item.quantity

            item.save(update_fields=[
                'product_cost_rub',
                'allocated_shipping_cost',
                'calculated_unit_cost',
            ])


    supply_date = models.DateField('Дата поставки')
    yuan_rate = models.DecimalField('Курс юаня', max_digits=10, decimal_places=4)
    cargo_commission_percent = models.DecimalField(
        'Комиссия карго, %',
        max_digits=5,
        decimal_places=2,
        default=Decimal('3.00'),
    )
    total_shipping_cost = models.DecimalField('Общая доставка, руб.', max_digits=12, decimal_places=2)
    total_package_weight = models.DecimalField('Вес с упаковкой, кг', max_digits=10, decimal_places=3)
    order_url = models.URLField('Ссылка на заказ', blank=True)
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Поставка'
        verbose_name_plural = 'Поставки'

    def __str__(self):
        return f'Поставка #{self.pk} - {self.supply_date}'


class SupplyItem(models.Model):
    supply = models.ForeignKey(
        Supply,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Поставка',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='supply_items',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество')
    price_yuan = models.DecimalField('Цена за шт., юань', max_digits=10, decimal_places=2)
    china_shipping_yuan = models.DecimalField('Доставка по Китаю, юань', max_digits=10, decimal_places=2)
    unit_weight = models.DecimalField('Вес 1 шт., кг', max_digits=10, decimal_places=3)

    product_cost_rub = models.DecimalField('Цена товара, руб.', max_digits=12, decimal_places=2, editable=False, default=Decimal('0.00'))
    allocated_shipping_cost = models.DecimalField('Доставка позиции, руб.', max_digits=12, decimal_places=2, editable=False, default=Decimal('0.00'))
    calculated_unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2, editable=False, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Позиция поставки'
        verbose_name_plural = 'Позиции поставки'

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.sync_stock_movement()

    def delete(self, *args, **kwargs):
        self.delete_stock_movement()
        super().delete(*args, **kwargs)

    def sync_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.update_or_create(
            source_type='supply_item',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.INBOUND,
                'quantity': self.quantity,
            },
        )

    def delete_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.filter(
            source_type='supply_item',
            source_id=self.pk,
        ).delete()


class ManualSupply(models.Model):
    supply_date = models.DateField('Дата поставки')
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Ручная поставка'
        verbose_name_plural = 'Ручные поставки'

    def __str__(self):
        return f'Ручная поставка #{self.pk} - {self.supply_date}'


class ManualSupplyItem(models.Model):
    supply = models.ForeignKey(
        ManualSupply,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Ручная поставка',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='manual_supply_items',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество')
    unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2)
    cost_note = models.TextField('Примечание к себестоимости', blank=True)
    total_cost = models.DecimalField('Итоговая себестоимость, руб.', max_digits=12, decimal_places=2,
                                     editable=False, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Ручная позиция поставки'
        verbose_name_plural = 'Ручные позиции поставки'

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    def save(self, *args, **kwargs):
        self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)
        self.sync_stock_movement()

    def delete(self, *args, **kwargs):
        self.delete_stock_movement()
        super().delete(*args, **kwargs)

    def sync_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.update_or_create(
            source_type='manual_supply_item',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.INBOUND,
                'quantity': self.quantity,
            },
        )

    def delete_stock_movement(self):
        from stock.models import StockMovement

        StockMovement.objects.filter(
            source_type='manual_supply_item',
            source_id=self.pk,
        ).delete()
