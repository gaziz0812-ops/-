from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db import transaction


class Sale(models.Model):
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='sales',
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sales',
    )
    quantity = models.PositiveIntegerField()
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    unit_sale_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    total_sale_amount = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    profit = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
        return f'Sale #{self.pk} - {self.product}'
