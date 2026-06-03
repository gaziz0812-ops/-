from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db import transaction
from django.core.exceptions import ValidationError


# Sale хранит факт продажи и запускает списание партий по FIFO.
class Sale(models.Model):
    # ForeignKey связывает продажу с товаром; related_name дает доступ product.sales.
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='sales',
        verbose_name='Товар',
    )

    # settings.AUTH_USER_MODEL связывает продажу с текущей кастомной моделью пользователя.
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name='Покупатель',
    )
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sales',
        verbose_name='Заказ',
    )
    order_item = models.OneToOneField(
        'orders.OrderItem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='sale',
        verbose_name='Позиция заказа',
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
        verbose_name = 'Продажу'
        verbose_name_plural = 'Продажи'

    # Переопределяем Django save(), чтобы при сохранении продажи пересчитать деньги и склад.
    def save(self, *args, **kwargs):
        if self.order_item_id:
            # Продажа из заказа берет историческую цену и количество из OrderItem.
            self.order = self.order_item.order
            self.product = self.order_item.product
            self.customer = self.order_item.order.customer
            self.quantity = self.order_item.quantity
            self.discount_percent = self.order_item.discount_percent
            self.unit_sale_price = self.order_item.unit_price_after_discount
            self.total_sale_amount = self.order_item.total_price
        else:
            # Старые ручные продажи временно используют прежнюю логику цены из карточки товара.
            discount_multiplier = Decimal('1.00') - (self.discount_percent / Decimal('100.00'))
            self.unit_sale_price = self.product.sale_price * discount_multiplier
            self.total_sale_amount = self.unit_sale_price * self.quantity

        # Временные значения нужны для первого сохранения, пока FIFO еще не посчитал себестоимость.
        self.cost_price = Decimal('0.00')
        self.profit = Decimal('0.00')

        # atomic делает продажу, списание партий и движение склада одной транзакцией БД.
        with transaction.atomic():
            # Первый super().save() создает продажу в БД и дает ей self.pk.
            super().save(*args, **kwargs)

            # sync_cost_allocations списывает партии FIFO и возвращает общую себестоимость продажи.
            total_cost = self.sync_cost_allocations()
            self.cost_price = total_cost / self.quantity
            self.profit = self.total_sale_amount - total_cost

            # Второй save обновляет только поля, которые стали известны после FIFO.
            super().save(update_fields=['cost_price', 'profit'])
            self.sync_stock_movement()

    # Переопределенный delete() технически откатывает склад, но в админке удаление продаж запрещено.
    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.restore_cost_allocations()
            self.delete_stock_movement()
            super().delete(*args, **kwargs)

    def sync_cost_allocations(self):
        from stock.models import StockBatch

        # Сначала возвращаем старые списания этой продажи, чтобы пересчитать FIFO заново без дублей.
        self.restore_cost_allocations()

        remaining_quantity = self.quantity
        total_cost = Decimal('0.00')

        # select_for_update блокирует партии на время транзакции, чтобы параллельные продажи не списали одно и то же.
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

            # SaleCostAllocation запоминает, сколько товара эта продажа взяла из конкретной партии.
            allocation = SaleCostAllocation.objects.create(
                sale=self,
                stock_batch=batch,
                quantity=quantity_from_batch,
                unit_cost=batch.unit_cost,
            )
            total_cost += allocation.total_cost
            remaining_quantity -= quantity_from_batch

        if remaining_quantity > 0:
            # Если партий не хватило, вся transaction.atomic() откатит продажу и изменения склада.
            raise ValidationError({
                'quantity': 'Недостаточно товара в партиях для FIFO-списания.'
            })

        return total_cost

    def restore_cost_allocations(self):
        from stock.models import StockBatch

        # cost_allocations — related_name из SaleCostAllocation.sale; это все партии текущей продажи.
        allocations = self.cost_allocations.select_related('stock_batch')
        for allocation in allocations:
            batch = StockBatch.objects.select_for_update().get(pk=allocation.stock_batch_id)
            batch.remaining_quantity += allocation.quantity
            batch.save(update_fields=['remaining_quantity'])

        allocations.delete()

    def sync_stock_movement(self):
        from stock.models import StockMovement

        # update_or_create не дает задвоить движение: одна продажа -> одно движение склада.
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

        # source_type + source_id находят движение, созданное именно этой продажей.
        StockMovement.objects.filter(
            source_type='sale',
            source_id=self.pk,
        ).delete()

    def __str__(self):
        return f'Продажа #{self.pk} - {self.product}'

    def clean(self):
        super().clean()

        # product_id — технический id ForeignKey; проверяем, что товар уже выбран.
        if self.product_id and self.quantity:
            available_quantity = self.product.stock_balance

            if self.pk:
                # При редактировании старую величину продажи временно возвращаем в доступный остаток.
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


# SaleCostAllocation — техническая память продажи: из каких партий списали товар.
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

    # total_cost не вводится руками, а считается из количества и себестоимости партии.
    def save(self, *args, **kwargs):
        self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Продажа #{self.sale_id} | {self.quantity} шт. из партии #{self.stock_batch_id}'


# SaleReturn хранит возврат по конкретной продаже.
class SaleReturn(models.Model):
    # TextChoices ограничивает варианты назначения возврата и дает русские подписи в админке.
    class Destination(models.TextChoices):
        BACK_TO_STOCK = 'back_to_stock', 'Вернуть на продажу'
        WRITE_OFF = 'write_off', 'Списать'

    # Возврат всегда оформляется на основании существующей продажи.
    order = models.ForeignKey(
        'orders.Order',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='returns',
        verbose_name='Заказ',
    )
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

        if self.order_id and self.sale_id and self.sale.order_id != self.order_id:
            raise ValidationError({
                'sale': 'Выбранная продажа не относится к указанному заказу.'
            })

        if self.sale_id and self.quantity:
            # Проверяем, сколько товара по этой продаже еще можно вернуть.
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
        # Суммируем уже оформленные возвраты по этой продаже, кроме текущего редактируемого возврата.
        already_returned_quantity = (
                                        self.sale.returns
                                        .exclude(pk=self.pk)
                                        .aggregate(total=models.Sum('quantity'))
                                        .get('total')
                                    ) or 0

        return self.sale.quantity - already_returned_quantity

    def save(self, *args, **kwargs):
        with transaction.atomic():
            if self.sale_id and not self.order_id:
                self.order = self.sale.order

            # full_clean запускает clean() перед сохранением, чтобы не вернуть больше проданного.
            self.full_clean()
            super().save(*args, **kwargs)
            self.sync_stock_movements()

            if self.destination == self.Destination.BACK_TO_STOCK:
                # Если товар возвращается на продажу, возвращаем количество в партии продажи.
                self.restore_sale_batches()

    def delete(self, *args, **kwargs):
        with transaction.atomic():
            self.delete_stock_movements()
            super().delete(*args, **kwargs)

    def sync_stock_movements(self):
        from stock.models import StockMovement

        # Основное движение возврата увеличивает расчетный остаток товара.
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
            # Если возврат списан, второе движение сразу вычитает товар из остатка.
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
        # Возвращаем товар в те партии, из которых он был продан.
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
