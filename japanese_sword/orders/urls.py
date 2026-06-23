from django.urls import path

from .views import CustomerOrderListAPIView, OrderCreateAPIView


# Легенда комментариев:
# [DJANGO] имя/функция, которые ожидает Django.
# [OUR] наш view-класс или наше имя маршрута.

# [DJANGO] urlpatterns — специальное имя: Django ищет здесь список URL приложения.
urlpatterns = [
    # Этот URL возвращает заказы текущего Telegram-пользователя.
    # [DJANGO] path() связывает URL /api/orders/my/ с CustomerOrderListAPIView.
    path('my/', CustomerOrderListAPIView.as_view(), name='customer-order-list'),

    # Этот URL принимает POST /api/orders/ и передает запрос в OrderCreateAPIView.
    # [DJANGO] path() связывает URL с view; [OUR] name='order-create' — наше имя маршрута.
    path('', OrderCreateAPIView.as_view(), name='order-create'),
]
