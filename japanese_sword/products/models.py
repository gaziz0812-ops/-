from django.db import models
from django.db.models import Sum


class Product(models.Model):
    # название само за себя говорит + длина строки и уникальность строки
    sku = models.CharField(max_length=64, unique=True)
    # название продукта + длина строки
    name = models.CharField(max_length=255)
    manufacturer = models.ForeignKey(
        'manufacturers.Manufacturer',  # привязываю к родителю manufacturers
        on_delete=models.PROTECT,  # запрещаю удалять мануфактуру пока под ним есть
        related_name='products',  # чтоб из мануфактуры получить список всех товаров
    )
    description = models.TextField(blank=True)  # характеристики
    sale_price = models.DecimalField(max_digits=10, decimal_places=2)  # цена
    is_active = models.BooleanField(default=True)  # активен продукт или нет

    # строковое отображение из выпадающего списка который будет ссылаться на продукт
    def __str__(self):
        return f"{self.sku} - {self.name}"

    @property  # декоратор превращающий метод в атрибут
    def stock_balance(self):
        # получаем из связанной модели stock_movements все записи текущего товара,
        # группируем по типу движения, суммируем кол-во по каждой группе
        totals = self.stock_movements.values('movement_type').annotate(
            total=Sum('quantity')
        )
        # превращаем результат (список словарей) в обычный словарь, где ключ - тип движения,
        # а значение - суммарное кол-во по этому типу
        movement_totals = {item['movement_type']: item['total'] for item in totals}

        # получаем сумму поступлений (inbound), если нет - 0 (None -> 0)
        inbound = movement_totals.get('inbound', 0) or 0
        # сумма возвратов (return), по умолчанию 0
        returned = movement_totals.get('return', 0) or 0
        # сумма продаж (sale), по умолчанию 0
        sale = movement_totals.get('sale', 0) or 0
        # сумма списаний (write_off), по умолчанию 0
        write_off = movement_totals.get('write_off', 0) or 0
        # сумма забронированных товаров (reserve), по умолчанию 0
        reserve = movement_totals.get('reserve', 0) or 0
        # сумма снятий с резерва (unreserve), по умолчанию 0
        unreserve = movement_totals.get('unreserve', 0) or 0

        # расчёт остатка: приход + возвраты + снятие резерва
        # минус продажи, минус списания, минус текущий резерв
        return inbound + returned + unreserve - sale - write_off - reserve
