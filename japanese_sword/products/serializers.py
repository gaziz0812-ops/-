from rest_framework import serializers

from .models import Product


# ModelSerializer строит JSON-представление на основе модели Product.
class ProductSerializer(serializers.ModelSerializer):
    # SerializerMethodField говорит DRF взять значение поля из метода get_stock_status().
    stock_status = serializers.SerializerMethodField()

    class Meta:
        # model связывает serializer с моделью Product.
        model = Product

        # fields перечисляет публичные поля, которые попадут в JSON-ответ API.
        fields = (
            'id',
            'sku',
            'name',
            'sale_price',
            'stock_status',
        )

    def get_stock_status(self, obj):
        # obj здесь конкретный Product, который DRF сейчас превращает в JSON.
        if obj.stock_balance > 1:
            return "В наличии"

        if obj.stock_balance == 1:
            return "Осталась 1 шт."

        return "Нет в наличии"


# Этот serializer используется для страницы одного товара: GET /api/products/<id>/
class ProductDetailSerializer(ProductSerializer):
    # Meta наследуется от ProductSerializer.Meta, чтобы не дублировать model = Product.
    class Meta(ProductSerializer.Meta):
        # В detail-ответ добавляем описание товара, которого нет в коротком списке.
        fields = ProductSerializer.Meta.fields + (
            'description',
        )
