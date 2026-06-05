from urllib.parse import urlencode
from urllib.request import urlopen

from django.conf import settings


# Эта функция отправляет обычное текстовое сообщение через Telegram Bot API.
def send_telegram_message(text):
    # Если токен или chat_id не настроены, уведомление тихо пропускаем.
    if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_ADMIN_CHAT_ID:
        return

    # urlencode безопасно превращает параметры в query string для URL.
    query = urlencode({
        'chat_id': settings.TELEGRAM_ADMIN_CHAT_ID,
        'text': text,
    })

    # Telegram Bot API принимает запрос sendMessage и отправляет сообщение в указанный chat_id.
    url = f'https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage?{query}'

    # urlopen делает HTTP-запрос к Telegram; timeout не дает Django зависнуть надолго.
    with urlopen(url, timeout=5) as response:
        response.read()


# Эта функция собирает текст уведомления о новом заказе.
def send_new_order_notification(order):
    # select_related подтягивает товар каждой позиции, чтобы не делать лишние запросы к БД.
    items = order.items.select_related('product')

    lines = [
        f'Новый заказ #{order.id}',
        f'Клиент: {order.customer_name or "-"}',
        f'Telegram: {order.telegram_username or "-"}',
        f'Телефон: {order.phone or "-"}',
        '',
        'Товары:',
    ]

    for item in items:
        lines.append(
            f'- {item.product} x {item.quantity} = {item.total_price} руб.'
        )

    lines.extend([
        '',
        f'Сумма: {order.total_amount} руб.',
    ])

    # "\n".join(lines) склеивает список строк в один текст сообщения.
    send_telegram_message('\n'.join(lines))