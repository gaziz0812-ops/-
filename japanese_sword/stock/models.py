from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone


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


class StockWriteOff(models.Model):
    class Reason(models.TextChoices):
        DEFECT = 'defect', 'Брак'
        DAMAGE = 'damage', 'Повреждение'
        LOSS = 'loss', 'Утеря'
        INVENTORY_SHORTAGE = 'inventory_shortage', 'Недостача при инвентаризации'
        OTHER = 'other', 'Другое'

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='write_offs',
        verbose_name='Товар'
    )
    quantity = models.PositiveIntegerField('Количество')
    reason = models.CharField(
        'Причина',
        max_length=30,
        choices=Reason.choices,
    )
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'списание'
        verbose_name_plural = 'Списания'

    def __str__(self):
        return f'Списание #{self.pk} - {self.product} x {self.quantity}'

    def clean(self):
        super().clean()

        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Количество должно быть больше нуля.'
            })

        if self.product_id and self.quantity and not self.pk:
            available_quantity = self.product.stock_balance

            if self.quantity > available_quantity:
                raise ValidationError({
                    'quantity': f'Недостаточно товара для списания. Доступно: {available_quantity}'
                })

    def save(self, *args, **kwargs):
        if self.pk:
            self.ensure_is_not_changed()
            super().save(*args, **kwargs)
            return

        with transaction.atomic():
            self.full_clean()
            super().save(*args, **kwargs)
            self.sync_batch_allocations()
            self.sync_stock_movement()

    def delete(self, *args, **kwargs):
        raise ValidationError('Списание нельзя удалить. Если товар нужно вернуть, оформите новую приемку.')

    def ensure_is_not_changed(self):
        original = StockWriteOff.objects.get(pk=self.pk)
        fields = ('product_id', 'quantity', 'reason', 'comment')

        for field in fields:
            if getattr(original, field) != getattr(self, field):
                raise ValidationError('Списание нельзя изменить после создания.')

    def sync_batch_allocations(self):
        remaining_quantity = self.quantity
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

            StockWriteOffAllocation.objects.create(
                write_off=self,
                stock_batch=batch,
                quantity=quantity_from_batch,
                unit_cost=batch.unit_cost,
            )
            remaining_quantity -= quantity_from_batch

        if remaining_quantity > 0:
            raise ValidationError({
                'quantity': 'Недостаточно товара в партиях для FIFO-списания.'
            })

    def sync_stock_movement(self):
        StockMovement.objects.update_or_create(
            source_type='stock_write_off',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.WRITE_OFF,
                'quantity': self.quantity,
            },
        )


class StockWriteOffAllocation(models.Model):
    write_off = models.ForeignKey(
        StockWriteOff,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name='Списание',
    )
    stock_batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name='write_off_allocations',
        verbose_name='Партия товара',
    )
    quantity = models.PositiveIntegerField('Количество')
    unit_cost = models.DecimalField('Себестоимость 1 шт., руб.', max_digits=12, decimal_places=2)
    total_cost = models.DecimalField('Себестоимость списания, руб.', max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Списание из партии'
        verbose_name_plural = 'Списания из партий'

    def save(self, *args, **kwargs):
        self.total_cost = self.unit_cost * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f'Списание #{self.write_off_id} | {self.quantity} шт. из партии #{self.stock_batch_id}'


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'active', 'Активен'
        RELEASED = 'released', 'Снят'

    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='reservations',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество')
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    comment = models.TextField('Комментарий', blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)
    released_at = models.DateTimeField('Снято', null=True, blank=True)

    class Meta:
        verbose_name = 'резерв'
        verbose_name_plural = 'Резервы'

    def __str__(self):
        return f'Резерв #{self.pk} - {self.product} x {self.quantity}'

    def clean(self):
        super().clean()

        if self.quantity is not None and self.quantity <= 0:
            raise ValidationError({
                'quantity': 'Количество должно быть больше нуля.'
            })

        if self.product_id and self.quantity and not self.pk:
            available_quantity = self.product.stock_balance

            if self.quantity > available_quantity:
                raise ValidationError({
                    'quantity': f'Недостаточно товара для резерва. Доступно: {available_quantity}'
                })

    def save(self, *args, **kwargs):
        if self.pk:
            self.ensure_is_not_changed()
            super().save(*args, **kwargs)
            return

        with transaction.atomic():
            self.full_clean()
            super().save(*args, **kwargs)
            self.sync_batch_allocations()
            self.sync_stock_movement()

    def delete(self, *args, **kwargs):
        raise ValidationError('Резерв нельзя удалить. Чтобы вернуть товар в доступный остаток, снимите резерв.')

    def release(self):
        if self.status == self.Status.RELEASED:
            return

        with transaction.atomic():
            reservation = StockReservation.objects.select_for_update().get(pk=self.pk)

            if reservation.status == self.Status.RELEASED:
                return

            reservation.restore_batch_allocations()
            reservation.status = self.Status.RELEASED
            reservation.released_at = timezone.now()
            super(StockReservation, reservation).save(update_fields=['status', 'released_at'])
            reservation.sync_release_stock_movement()

            self.status = reservation.status
            self.released_at = reservation.released_at

    def ensure_is_not_changed(self):
        original = StockReservation.objects.get(pk=self.pk)
        fields = ('product_id', 'quantity', 'status', 'comment', 'released_at')

        for field in fields:
            if getattr(original, field) != getattr(self, field):
                raise ValidationError('Резерв нельзя изменить после создания. Его можно только снять.')

    def sync_batch_allocations(self):
        remaining_quantity = self.quantity
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

            StockReservationAllocation.objects.create(
                reservation=self,
                stock_batch=batch,
                quantity=quantity_from_batch,
            )
            remaining_quantity -= quantity_from_batch

        if remaining_quantity > 0:
            raise ValidationError({
                'quantity': 'Недостаточно товара в партиях для FIFO-резерва.'
            })

    def restore_batch_allocations(self):
        allocations = self.allocations.select_related('stock_batch')

        for allocation in allocations:
            batch = StockBatch.objects.select_for_update().get(pk=allocation.stock_batch_id)
            batch.remaining_quantity += allocation.quantity
            batch.save(update_fields=['remaining_quantity'])

    def sync_stock_movement(self):
        StockMovement.objects.update_or_create(
            source_type='stock_reservation',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.RESERVE,
                'quantity': self.quantity,
            },
        )

    def sync_release_stock_movement(self):
        StockMovement.objects.update_or_create(
            source_type='stock_reservation_release',
            source_id=self.pk,
            defaults={
                'product': self.product,
                'movement_type': StockMovement.MovementType.UNRESERVE,
                'quantity': self.quantity,
            },
        )


class StockReservationAllocation(models.Model):
    reservation = models.ForeignKey(
        StockReservation,
        on_delete=models.CASCADE,
        related_name='allocations',
        verbose_name='Резерв',
    )
    stock_batch = models.ForeignKey(
        StockBatch,
        on_delete=models.PROTECT,
        related_name='reservation_allocations',
        verbose_name='Партия товара',
    )
    quantity = models.PositiveIntegerField('Количество')
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Резерв из партии'
        verbose_name_plural = 'Резервы из партий'

    def __str__(self):
        return f'Резерв #{self.reservation_id} | {self.quantity} шт. из партии #{self.stock_batch_id}'
