from django.db import transaction
from rest_framework import serializers

from products.models import Product

from .notifications import send_new_order_notification
from .models import Order, OrderItem

# Эти сервисы проверяют Telegram initData и превращают проверенные Telegram-данные в User.
from users.services import get_or_create_telegram_user, parse_telegram_init_data


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


# Этот serializer описывает, как позиция заказа выглядит в JSON-ответе API.
class OrderItemReadSerializer(serializers.ModelSerializer):
    # source='product.sku' берет артикул из связанного товара OrderItem.product.
    sku = serializers.CharField(source='product.sku', read_only=True)

    # source='product.name' берет название из связанного товара OrderItem.product.
    name = serializers.CharField(source='product.name', read_only=True)

    class Meta:
        # model связывает serializer с моделью OrderItem.
        model = OrderItem

        # fields перечисляет поля позиции заказа, которые клиент увидит в ответе API.
        fields = (
            'product',
            'sku',
            'name',
            'quantity',
            'unit_price',
            'unit_price_after_discount',
            'total_price',
        )


# Этот serializer принимает данные клиента и список товаров для создания Order.
class OrderCreateSerializer(serializers.ModelSerializer):
    # telegram_init_data принимает сырую подписанную строку Telegram Mini App; в модели Order такого поля нет.
    telegram_init_data = serializers.CharField(write_only=True, required=False)

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
            'telegram_init_data',
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
        # Забираем initData отдельно, потому что у модели Order нет поля telegram_init_data.
        telegram_init_data = validated_data.pop('telegram_init_data', None)

        # Забираем вложенные товары отдельно, потому что Order не имеет обычного поля items.
        items_data = validated_data.pop('items')

        # atomic делает создание заказа и всех позиций одной транзакцией.
        with transaction.atomic():
            # Если frontend прислал initData, сначала проверяем подпись Telegram, потом создаем/находим User.
            if telegram_init_data:
                try:
                    telegram_user_data = parse_telegram_init_data(telegram_init_data)
                except ValueError as error:
                    raise serializers.ValidationError({
                        'telegram_init_data': str(error)
                    })

                validated_data['customer'] = get_or_create_telegram_user(telegram_user_data)

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


    def to_representation(self, instance):
        # Сначала DRF собирает обычный JSON заказа через стандартную логику ModelSerializer.
        representation = super().to_representation(instance)

        # Для ответа API заменяем входной формат items на подробный формат позиций заказа.
        representation['items'] = OrderItemReadSerializer(
            instance.items.select_related('product'),
            many=True,
        ).data

        return representation
