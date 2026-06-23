from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from users.services import get_or_create_telegram_user, parse_telegram_init_data

from .models import Order
from .serializers import CustomerOrderSerializer, OrderCreateSerializer


# Легенда комментариев:
# [DRF] имя/метод/атрибут, который ожидает Django REST Framework.
# [DJANGO] механизм Django.
# [OUR] наше имя, наша бизнес-логика.

# Для публичного API заказа CSRF отключаем: позже безопасность будет через проверку Telegram initData.
# [DJANGO] method_decorator применяет csrf_exempt к class-based view.
@method_decorator(csrf_exempt, name='dispatch')

# CreateAPIView дает endpoint только для создания объекта через POST.
# [OUR] Название класса наше; [DRF] CreateAPIView уже умеет принимать POST и вызывать serializer.save().
class OrderCreateAPIView(generics.CreateAPIView):
    # queryset нужен DRF как базовый набор объектов модели Order.
    # [DRF] queryset — специальный атрибут view-класса.
    queryset = Order.objects.all()

    # serializer_class говорит DRF, каким serializer проверять JSON и создавать Order.
    # [DRF] serializer_class — специальный атрибут view-класса.
    serializer_class = OrderCreateSerializer


# Этот endpoint возвращает заказы текущего Telegram-пользователя.
# [OUR] Название класса наше; [DRF] ListAPIView умеет отвечать на GET списком объектов.
class CustomerOrderListAPIView(generics.ListAPIView):
    # serializer_class говорит DRF, каким serializer превратить Order в JSON.
    # [DRF] serializer_class — специальный атрибут view-класса.
    serializer_class = CustomerOrderSerializer

    # get_queryset вызывается DRF при GET-запросе, чтобы понять, какие заказы отдавать.
    # [DRF] get_queryset() — hook, который мы переопределяем под нашу бизнес-логику.
    def get_queryset(self):
        # telegram_init_data придет из URL query params:
        # /api/orders/my/?telegram_init_data=...
        telegram_init_data = self.request.query_params.get('telegram_init_data')

        if not telegram_init_data:
            raise ValidationError({
                'telegram_init_data': 'Telegram initData не передан.'
            })

        try:
            telegram_user_data = parse_telegram_init_data(telegram_init_data)
        except ValueError as error:
            raise ValidationError({
                'telegram_init_data': str(error)
            })

        user = get_or_create_telegram_user(telegram_user_data)

        if not user:
            return Order.objects.none()

        # Возвращаем только заказы текущего Telegram-пользователя.
        # [ORM] filter(customer=user) превращается в SQL WHERE customer_id = user.id.
        return (
            Order.objects
            .filter(customer=user)
            .prefetch_related('items__product')
            .order_by('-created_at')
        )
