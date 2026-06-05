from django.db import transaction
from rest_framework import serializers

from products.models import Product

from .notifications import send_new_order_notification
from .models import Order, OrderItem


# Этот serializer описывает одну товарную строку, которую клиент отправляет в заказ.
class OrderItemCreateSerializer(serializers.Serializer):
    # PrimaryKeyRelatedField принимает id товара и превращает его в объект Product.
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True)
    )

    # IntegerField принимает количество товара из JSON.
    quantity = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        # attrs содержит уже проверенные данные строки заказа.
        product = attrs['product']
        quantity = attrs['quantity']

        # stock_balance — наше свойство Product, которое считает остаток по движениям склада.
        if quantity > product.stock_balance:
            raise serializers.ValidationError(
                f'Недостаточно товара на складе. Доступно: {product.stock_balance}'
            )

        return attrs


# Этот serializer принимает данные клиента и список товаров для создания Order.
class OrderCreateSerializer(serializers.ModelSerializer):
    # items — вложенный список товаров внутри заказа.
    items = OrderItemCreateSerializer(many=True)

    class Meta:
        # model связывает serializer с моделью Order.
        model = Order

        # fields описывает, какие данные API принимает и возвращает.
        fields = (
            'id',
            'customer_name',
            'telegram_username',
            'phone',
            'customer_comment',
            'total_amount',
            'status',
            'items',
        )

        # read_only_fields запрещает клиенту самому задавать служебные поля.
        read_only_fields = (
            'id',
            'total_amount',
            'status',
        )

    def validate_items(self, items):
        # Заказ без товаров создавать нельзя.
        if not items:
            raise serializers.ValidationError('Добавьте хотя бы один товар в заказ.')

        return items

    def create(self, validated_data):
        # Забираем вложенные товары отдельно, потому что Order не имеет обычного поля items.
        items_data = validated_data.pop('items')

        # atomic делает создание заказа и всех позиций одной транзакцией.
        with transaction.atomic():
            order = Order.objects.create(**validated_data)

            for item_data in items_data:
                OrderItem.objects.create(
                    order=order,
                    product=item_data['product'],
                    quantity=item_data['quantity'],
                )

            # Уведомление отправляем после создания всех позиций, чтобы в сообщении была полная сумма заказа.
            send_new_order_notification(order)

        return order

    