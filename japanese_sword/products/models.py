from django.db import models


class Product(models.Model):
    sku = models.CharField(max_length=64, unique=True)  # номер артикула
    name = models.CharField(max_length=255)  # название артикула
    manufacturer = models.ForeignKey(  # переменная для связи продуктов с родительским Manufacturer
        'manufacturers.Manufacturer',  # ссылка на класс мануфактуры
        on_delete=models.PROTECT,  # запрещает удалять производителя если от него есть продукты
        related_name='products',  # обратная связь
    )
    description = models.TextField(blank=True)  # характеристики продукта
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)  # цена (максимум 10 цифр и 2 точки)
    is_active = models.BooleanField(default=True)  # Продукт по дефолту активен, учтен в остатках и в каталоге

    def __str__(self):
        return f"{self.sku} - {self.name}"


