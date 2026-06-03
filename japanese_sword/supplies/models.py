from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models


# Supply хранит общие данные поставки, которые влияют на расчет себестоимости всех ее позиций.
class Supply(models.Model):
    # Наш метод: пересчитывает себестоимость всех SupplyItem внутри поставки.
    def recalculate_costs(self):
        # self.items идет по related_name='items' из SupplyItem.supply.
        items = list(self.items.all())
        if not items:
            return

        # Суммарный чистый вес нужен, чтобы распределить общий вес упаковки между позициями.
        total_clean_weight = sum(item.unit_weight * item.quantity for item in items)
        if not total_clean_weight or not self.total_package_weight:
            return

        # Стоимость доставки за кг считаем из общей доставки и общего веса с упаковкой.
        shipping_price_per_kg = self.total_shipping_cost / self.total_package_weight

        # Комиссию карго переводим из процентов в множитель: 3% -> 1.03.
        commission_multiplier = Decimal('1.00') + (self.cargo_commission_percent / Decimal('100.00'))

        for item in items:
            # Каждой позиции выделяем часть упаковочного веса пропорционально ее чистому весу.
            item_clean_weight = item.unit_weight * item.quantity
            item_package_weight = self.total_package_weight * item_clean_weight / total_clean_weight
            allocated_shipping_cost = item_package_weight * shipping_price_per_kg

            # Переводим цену товара из юаней в рубли с учетом доставки по Китаю и комиссии карго.
            product_cost_rub = (
                    (item.price_yuan * item.quantity + item.china_shipping_yuan)
                    * commission_multiplier
                    * self.yuan_rate
            )

            item.product_cost_rub = product_cost_rub
            item.allocated_shipping_cost = allocated_shipping_cost

            # calculated_unit_cost — итоговая себестоимость одной штуки в этой позиции поставки.
            item.calculated_unit_cost = (
                                                product_cost_rub + allocated_shipping_cost
                                        ) / item.quantity

            # update_fields обновляет только расчетные поля, а не всю строку SupplyItem.
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
        verbose_name = 'Поставку'
        verbose_name_plural = 'Поставки'

    def __str__(self):
        return f'Поставка #{self.pk} - {self.supply_date}'


# SupplyItem — конкретная строка товара внутри расчетной поставки.
class SupplyItem(models.Model):
    # CASCADE удалит позиции, если удалена сама поставка.
    supply = models.ForeignKey(
        Supply,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Поставка',
    )

    # PROTECT запрещает удалить товар, если он участвовал в поставке.
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

    product_cost_rub = models.DecimalField('Цена товара, руб.', max_digits=12, decimal_places=2,
                                           editable=False, default=Decimal('0.00'))
    allocated_shipping_cost = models.DecimalField('Доставка позиции, руб.', max_digits=12, decimal_places=2,
                                                  editable=False, default=Decimal('0.00'))
    calculated_unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2,
                                               editable=False, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Позиция поставки'
        verbose_name_plural = 'Позиции поставки'

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    def save(self, *args, **kwargs):
        # Если позиция уже существует, проверяем, не была ли ее партия использована в продаже.
        if self.pk:
            self.ensure_stock_batch_is_not_used()

        super().save(*args, **kwargs)

        # После сохранения позиции синхронизируем журнал движения и партию товара.
        self.sync_stock_movement()
        self.sync_stock_batch()

    def delete(self, *args, **kwargs):
        # Нельзя удалить позицию, если ее партия уже участвовала в продаже.
        self.ensure_stock_batch_is_not_used()
        self.delete_stock_movement()
        self.delete_stock_batch()
        super().delete(*args, **kwargs)

    def sync_stock_movement(self):
        from stock.models import StockMovement

        # Приходная позиция создает движение INBOUND в журнале склада.
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

    def sync_stock_batch(self):
        from stock.models import StockBatch

        # Позиция поставки создает или обновляет партию товара для FIFO.
        StockBatch.objects.update_or_create(
            source_type='supply_item',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'quantity': self.quantity,
                'remaining_quantity': self.quantity,
                'unit_cost': self.calculated_unit_cost,
            }
        )

    def delete_stock_batch(self):
        from stock.models import StockBatch

        StockBatch.objects.filter(
            source_type='supply_item',
            source_id=self.pk,
        ).delete()

    def get_stock_batch(self):
        from stock.models import StockBatch

        # Находим партию, которая была создана именно этой позицией поставки.
        return StockBatch.objects.filter(
            source_type='supply_item',
            source_id=self.pk,
        ).first()

    def ensure_stock_batch_is_not_used(self):
        batch = self.get_stock_batch()

        # Если партия уже участвовала в продажах, менять приход опасно для себестоимости и остатков.
        if batch and batch.sale_allocations.exists():
            raise ValidationError(
                'Эту позицию поставки нельзя изменить или удалить, потому что ее партия уже участвовала в продаже.'
            )


# ManualSupply хранит ручную поставку без расчета юаней, веса и доставки.
class ManualSupply(models.Model):
    supply_date = models.DateField('Дата поставки')
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Ручная поставка'
        verbose_name_plural = 'Ручные поставки'

    def __str__(self):
        return f'Ручная поставка #{self.pk} - {self.supply_date}'


# ManualSupplyItem — строка ручной поставки с уже известной себестоимостью.
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
        # Существующую ручную позицию нельзя менять, если ее партия уже участвовала в продаже.
        if self.pk:
            self.ensure_stock_batch_is_not_used()

        # total_cost считается автоматически из себестоимости за штуку и количества.
        self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)
        self.sync_stock_movement()
        self.sync_stock_batch()

    def delete(self, *args, **kwargs):
        self.ensure_stock_batch_is_not_used()
        self.delete_stock_movement()
        self.delete_stock_batch()
        super().delete(*args, **kwargs)

    def sync_stock_movement(self):
        from stock.models import StockMovement

        # Ручная позиция поставки тоже создает приходное движение INBOUND.
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

    def sync_stock_batch(self):
        from stock.models import StockBatch

        # Для ручной поставки партия создается с вручную указанной себестоимостью.
        StockBatch.objects.update_or_create(
            source_type='manual_supply_item',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'quantity': self.quantity,
                'remaining_quantity': self.quantity,
                'unit_cost': self.unit_cost,
            },
        )

    def delete_stock_batch(self):
        from stock.models import StockBatch

        StockBatch.objects.filter(
            source_type='manual_supply_item',
            source_id=self.pk,
        ).delete()

    def get_stock_batch(self):
        from stock.models import StockBatch

        return StockBatch.objects.filter(
            source_type='manual_supply_item',
            source_id=self.pk,
        ).first()

    def ensure_stock_batch_is_not_used(self):
        batch = self.get_stock_batch()

        # Защита от изменения партии, которая уже повлияла на продажи и прибыль.
        if batch and batch.sale_allocations.exists():
            raise ValidationError(
                'Эту позицию ручной поставки нельзя изменить или удалить, потому что ее партия уже участвовала в продаже.'
            )
