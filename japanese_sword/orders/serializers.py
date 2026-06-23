from django.db import transaction
from rest_framework import serializers

from products.models import Product

from .notifications import (
    send_customer_order_created_notification,
    send_new_order_notification,
)
from .models import Order, OrderItem

# Эти сервисы проверяют Telegram initData и превращают проверенные Telegram-данные в User.
from users.services import get_or_create_telegram_user, parse_telegram_init_data


# Легенда комментариев:
# [DRF] имя/метод/атрибут, который ожидает Django REST Framework.
# [OUR] наше имя, наша переменная или наша бизнес-логика.
# [DJANGO] механизм Django.
# [PY] обычный Python.


# Этот serializer описывает одну товарную строку, которую клиент отправляет в заказ.
# [OUR] Название класса наше; [DRF] наследование от serializers.Serializer задает правила входного JSON.
class OrderItemCreateSerializer(serializers.Serializer):
    # PrimaryKeyRelatedField принимает id товара и превращает его в объект Product.
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True)
    )

    # IntegerField принимает количество товара из JSON.
    quantity = serializers.IntegerField(min_value=1)

    # [DRF] validate() — специальный hook DRF: вызывается после проверки отдельных полей.
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
# [OUR] Название класса наше; [DRF] ModelSerializer строит JSON на основе модели OrderItem.
class OrderItemReadSerializer(serializers.ModelSerializer):
    # source='product.sku' берет артикул из связанного товара OrderItem.product.
    sku = serializers.CharField(source='product.sku', read_only=True)

    # source='product.name' берет название из связанного товара OrderItem.product.
    name = serializers.CharField(source='product.name', read_only=True)

    # [DRF] Meta — специальный вложенный класс, из которого DRF читает настройки serializer.
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
# [OUR] Название класса наше; [DRF] ModelSerializer связывает JSON с моделью Order.
class OrderCreateSerializer(serializers.ModelSerializer):
    # telegram_init_data принимает сырую подписанную строку Telegram Mini App; в модели Order такого поля нет.
    telegram_init_data = serializers.CharField(write_only=True, required=False)

    # items — вложенный список товаров внутри заказа.
    items = OrderItemCreateSerializer(many=True)

    # [DRF] Meta — специальное имя: DRF сам ищет здесь model, fields и read_only_fields.
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

    # [DRF] validate_<field>() — специальный hook DRF для проверки конкретного поля items.
    def validate_items(self, items):
        # Заказ без товаров создавать нельзя.
        if not items:
            raise serializers.ValidationError('Добавьте хотя бы один товар в заказ.')

        return items

    # [DRF] create() — специальный hook DRF: вызывается при serializer.save() для создания объекта.
    def create(self, validated_data):
        # Забираем initData отдельно, потому что у модели Order нет поля telegram_init_data.
        telegram_init_data = validated_data.pop('telegram_init_data', None)

        # Забираем вложенные товары отдельно, потому что Order не имеет обычного поля items.
        items_data = validated_data.pop('items')

        # atomic делает создание заказа и всех позиций одной транзакцией.
        # [DJANGO] transaction.atomic() делает создание Order и OrderItem одной транзакцией БД.
        with transaction.atomic():
            # Если frontend прислал initData, сначала проверяем подпись Telegram, потом создаем/находим User.
            if telegram_init_data:
                try:
                    # [OUR] parse_telegram_init_data() — наша функция проверки подписи Telegram.
                    telegram_user_data = parse_telegram_init_data(telegram_init_data)
                except ValueError as error:
                    # [DRF] ValidationError превратится в HTTP 400 Bad Request.
                    raise serializers.ValidationError({
                        'telegram_init_data': str(error)
                    })

                # [OUR] get_or_create_telegram_user() — наша функция связи Telegram user с users.User.
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
            send_customer_order_created_notification(order)

        return order

    # [DRF] to_representation() — специальный hook DRF: меняет JSON-ответ после создания объекта.
    def to_representation(self, instance):
        # Сначала DRF собирает обычный JSON заказа через стандартную логику ModelSerializer.
        representation = super().to_representation(instance)

        # Для ответа API заменяем входной формат items на подробный формат позиций заказа.
        representation['items'] = OrderItemReadSerializer(
            instance.items.select_related('product'),
            many=True,
        ).data

        return representation


# Этот serializer показывает покупателю уже созданный заказ.
# [OUR] Название класса наше; [DRF] ModelSerializer строит JSON на основе модели Order.
class CustomerOrderSerializer(serializers.ModelSerializer):
    # items берутся через related_name='items' из OrderItem.order.
    # [DRF] read_only=True означает, что через этот serializer позиции нельзя менять, только читать.
    items = OrderItemReadSerializer(many=True, read_only=True)

    # get_status_display берет русское название статуса из TextChoices модели Order.Status.
    # [DRF] source указывает, откуда взять значение для поля JSON.
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # [DRF] Meta — настройки serializer: какая модель и какие поля попадут в JSON.
    class Meta:
        # model связывает serializer с моделью Order.
        model = Order

        # fields перечисляет данные, которые покупатель увидит в ответе API.
        fields = (
            'id',
            'status',
            'status_display',
            'total_amount',
            'paid_at',
            'shipped_at',
            'tracking_number',
            'created_at',
            'items',
        )
