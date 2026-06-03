from decimal import Decimal

from django.db import models


# Order хранит заказ/заявку клиента, но сам не списывает склад.
class Order(models.Model):
    # TextChoices ограничивает статусы заказа заранее известным набором значений.
    class Status(models.TextChoices):
        NEW = 'new', 'Новый'
        IN_PROGRESS = 'in_progress', 'В работе'
        WAITING_PAYMENT = 'waiting_payment', 'Ожидает оплату'
        PAID = 'paid', 'Оплачен'
        SOLD = 'sold', 'Продажа проведена'
        SHIPPED = 'shipped', 'Отправлен'
        COMPLETED = 'completed', 'Завершен'
        CANCELLED = 'cancelled', 'Отменен'

    customer_name = models.CharField('Имя клиента', max_length=255, blank=True)
    telegram_username = models.CharField('Telegram username', max_length=255, blank=True)
    phone = models.CharField('Телефон', max_length=50, blank=True)

    status = models.CharField(
        'Статус',
        max_length=30,
        choices=Status.choices,
        default=Status.NEW,
    )

    customer_comment = models.TextField('Комментарий клиента', blank=True)
    internal_comment = models.TextField('Внутренний комментарий', blank=True)

    total_amount = models.DecimalField(
        'Сумма заказа',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        editable=False,
    )

    paid_at = models.DateTimeField('Дата оплаты', null=True, blank=True)
    shipped_at = models.DateTimeField('Дата отправки', null=True, blank=True)
    tracking_number = models.CharField('Трек-номер', max_length=255, blank=True)
    created_at = models.DateTimeField('Создано', auto_now_add=True)

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'

    def recalculate_total_amount(self):
        # self.items идет по related_name='items' из OrderItem.order.
        total = sum(item.total_price for item in self.items.all())

        self.total_amount = total
        self.save(update_fields=['total_amount'])

    def __str__(self):
        return f'Заказ #{self.pk}'


# OrderItem хранит конкретную строку товара внутри заказа.
class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ',
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
        verbose_name='Товар',
    )
    quantity = models.PositiveIntegerField('Количество')

    unit_price = models.DecimalField(
        'Цена на момент заказа',
        max_digits=10,
        decimal_places=2,
        editable=False,
    )
    total_price = models.DecimalField(
        'Сумма позиции',
        max_digits=12,
        decimal_places=2,
        editable=False,
    )

    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'

    def save(self, *args, **kwargs):
        # Для новой позиции фиксируем текущую цену товара из каталога.
        if not self.pk:
            self.unit_price = self.product.sale_price

        self.total_price = self.unit_price * self.quantity

        super().save(*args, **kwargs)

        # После сохранения позиции пересчитываем общую сумму заказа.
        self.order.recalculate_total_amount()

    def delete(self, *args, **kwargs):
        order = self.order

        super().delete(*args, **kwargs)

        # После удаления позиции тоже пересчитываем сумму заказа.
        order.recalculate_total_amount()

    def __str__(self):
        return f'{self.product} x {self.quantity}'