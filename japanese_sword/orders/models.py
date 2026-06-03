from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction


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
        CANCELLED = 'cancelled', 'Отменен'

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
        verbose_name='Покупатель',
    )
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

    def clean(self):
        super().clean()

        # Если продажи уже проведены, заказ нельзя вернуть в рабочие/отмененные статусы.
        if self.pk and self.sales.exists() and self.status not in (self.Status.SOLD, self.Status.SHIPPED):
            raise ValidationError({
                'status': 'После проведения продажи заказ может быть только в статусе "Продажа проведена" или "Отправлен".'
            })

        old_status = (
            Order.objects
            .filter(pk=self.pk)
            .values_list('status', flat=True)
            .first()
        ) if self.pk else None

        # Отправленный заказ нельзя откатить назад, чтобы не ломать историю доставки.
        if old_status == self.Status.SHIPPED and self.status != self.Status.SHIPPED:
            raise ValidationError({
                'status': 'Отправленный заказ нельзя вернуть в предыдущий статус.'
            })

        # Для оплаченных и последующих статусов дата оплаты обязательна.
        if self.status in (self.Status.PAID, self.Status.SOLD, self.Status.SHIPPED) and not self.paid_at:
            raise ValidationError({
                'paid_at': 'Укажите дату и время оплаты для оплаченного заказа.'
            })

        # Отправленный заказ должен иметь дату отправки и трек-номер.
        if self.status == self.Status.SHIPPED:
            errors = {}

            if not self.shipped_at:
                errors['shipped_at'] = 'Укажите дату и время отправки.'

            if not self.tracking_number:
                errors['tracking_number'] = 'Укажите трек-номер отправления.'

            if errors:
                raise ValidationError(errors)

    def recalculate_total_amount(self):
        # self.items идет по related_name='items' из OrderItem.order.
        total = sum(item.total_price for item in self.items.all())

        self.total_amount = total
        self.save(update_fields=['total_amount'])

    def conduct_sales(self):
        # full_clean запускает clean(), чтобы бизнес-валидации работали не только через форму админки.
        self.full_clean()

        # Продажи можно проводить только после подтверждения оплаты заказа.
        if self.status != self.Status.PAID:
            raise ValidationError('Провести продажу можно только для оплаченного заказа.')

        # Если продажи уже есть, повторное проведение создало бы дубли списаний склада.
        if self.sales.exists():
            raise ValidationError('По этому заказу продажи уже проведены.')

        # Заказ без позиций нельзя превратить в продажи.
        items = list(self.items.select_related('product'))
        if not items:
            raise ValidationError('Нельзя провести продажу по заказу без товаров.')

        from sales.models import Sale

        # Вся цепочка создания Sale и FIFO-списаний должна пройти одной транзакцией.
        with transaction.atomic():
            for item in items:
                Sale.objects.create(
                    order=self,
                    order_item=item,
                    product=item.product,
                    customer=self.customer,
                    quantity=item.quantity,
                    discount_percent=item.discount_percent,
                )

            self.status = self.Status.SOLD
            self.save(update_fields=['status'])

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
    discount_percent = models.DecimalField(
        'Скидка, %',
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )

    unit_price = models.DecimalField(
        'Цена на момент заказа',
        max_digits=10,
        decimal_places=2,
        editable=False,
    )
    unit_price_after_discount = models.DecimalField(
        'Цена со скидкой',
        max_digits=10,
        decimal_places=2,
        editable=False,
        default=Decimal('0.00'),
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

    def clean(self):
        super().clean()

        if self.discount_percent < 0 or self.discount_percent > 100:
            raise ValidationError({
                'discount_percent': 'Скидка должна быть от 0 до 100%.'
            })

    def save(self, *args, **kwargs):
        self.ensure_order_has_no_sales()

        # Для новой позиции или при смене товара фиксируем текущую цену товара из каталога.
        if not self.pk or self.is_product_changed():
            self.unit_price = self.product.sale_price

        discount_multiplier = Decimal('1.00') - (self.discount_percent / Decimal('100.00'))
        self.unit_price_after_discount = self.unit_price * discount_multiplier
        self.total_price = self.unit_price_after_discount * self.quantity

        super().save(*args, **kwargs)

        # После сохранения позиции пересчитываем общую сумму заказа.
        self.order.recalculate_total_amount()

    def delete(self, *args, **kwargs):
        self.ensure_order_has_no_sales()

        order = self.order

        super().delete(*args, **kwargs)

        # После удаления позиции тоже пересчитываем сумму заказа.
        order.recalculate_total_amount()

    def __str__(self):
        return f'{self.product} x {self.quantity}'

    def ensure_order_has_no_sales(self):
        # Позиции нельзя менять после создания продаж, иначе история заказа и FIFO разъедутся.
        if self.order_id and self.order.sales.exists():
            raise ValidationError(
                'Позиции заказа нельзя изменять после проведения продажи.'
            )

    def is_product_changed(self):
        # Если в существующей позиции поменяли товар, цену нужно зафиксировать заново.
        if not self.pk:
            return False

        old_product_id = (
            OrderItem.objects
            .filter(pk=self.pk)
            .values_list('product_id', flat=True)
            .first()
        )

        return old_product_id != self.product_id
