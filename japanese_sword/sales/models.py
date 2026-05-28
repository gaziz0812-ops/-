from django.conf import settings
from django.db import models


class Sale(models.Model):
    product = models.ForeignKey(
        'products.Product',  # привязываю продаж к продуктам
        on_delete=models.PROTECT,  # запрещаю удалять товар если была продажа
        related_name='sales',  # чтоб из продуктов получить список проданных товаров
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,  # кому продал (указывается юзер)
        on_delete=models.SET_NULL,  #
        null=True,
        blank=True,
        related_name='sales',
    )
    quantity = models.PositiveIntegerField()  # сколько едениц продал (только плюсовое значение)
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)  # цена на момент продажи
    cost_price = models.DecimalField(max_digits=10, decimal_places=2)  # себестоимость
    profit = models.DecimalField(max_digits=10, decimal_places=2, editable=False)  # прибыль (не редактируется)
    comment = models.TextField(blank=True)  # комментарий
    created_at = models.DateTimeField(auto_now_add=True)  # когда продал


    def save(self, *args, **kwargs):
        self.profit = (self.sale_price - self.cost_price) * self.quantity
        super().save(*args, **kwargs)


    def __str__(self):
        return f'Sale #{self.pk} - {self.product}'