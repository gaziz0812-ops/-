import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from django.conf import settings

# Импортируем нашу модель пользователя и набор ролей из приложения users.
from .models import User, UserRole


# Эта функция проверяет initData от Telegram Mini App и возвращает данные пользователя.
def parse_telegram_init_data(init_data, max_age_seconds=86400):
    # initData — это сырая query-string строка от Telegram: user=...&auth_date=...&hash=...
    if not init_data:
        raise ValueError('Telegram initData не передан.')

    # parse_qsl разбирает query-string в пары ключ-значение.
    parsed_data = dict(parse_qsl(init_data, keep_blank_values=True))

    # hash — подпись Telegram, с которой мы будем сравнивать свой расчет.
    received_hash = parsed_data.pop('hash', None)

    # Без hash мы не можем доказать, что данные пришли от Telegram.
    if not received_hash:
        raise ValueError('В Telegram initData отсутствует hash.')

    # auth_date показывает, когда Telegram выдал эти данные.
    auth_date = parsed_data.get('auth_date')

    # Без auth_date нельзя проверить свежесть данных.
    if not auth_date:
        raise ValueError('В Telegram initData отсутствует auth_date.')

    # Старые initData лучше не принимать, чтобы украденная строка не работала бесконечно.
    if int(time.time()) - int(auth_date) > max_age_seconds:
        raise ValueError('Telegram initData устарел.')

    # Telegram требует собрать строку из всех полей, кроме hash, отсортировав их по ключу.
    data_check_string = '\n'.join(
        f'{key}={value}'
        for key, value in sorted(parsed_data.items())
    )

    # Сначала создаем секретный ключ из bot token и константы WebAppData.
    secret_key = hmac.new(
        b'WebAppData',
        settings.TELEGRAM_BOT_TOKEN.encode(),
        hashlib.sha256,
    ).digest()

    # Затем считаем hash от data_check_string уже через полученный secret_key.
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256,
    ).hexdigest()

    # compare_digest безопасно сравнивает подписи.
    if not hmac.compare_digest(calculated_hash, received_hash):
        raise ValueError('Telegram initData имеет неверную подпись.')

    # Внутри initData поле user хранится как JSON-строка.
    user_raw = parsed_data.get('user')

    # Если user нет, мы не можем связать заказ с Telegram-пользователем.
    if not user_raw:
        raise ValueError('В Telegram initData отсутствует user.')

    # Превращаем JSON-строку user в обычный Python-словарь.
    return json.loads(user_raw)


# Это наша обычная Python-функция: Django сам ее не вызывает, мы вызываем ее из serializer заказов.
def get_or_create_telegram_user(telegram_data):
    # Telegram ID — главный стабильный идентификатор пользователя в Telegram.
    telegram_id = telegram_data.get('id')

    # Если Telegram ID не пришел, мы не можем надежно связать заказ с пользователем.
    if not telegram_id:
        return None

    # Username в Telegram может отсутствовать, поэтому делаем технический username через telegram_id.
    username = telegram_data.get('username') or f'tg_{telegram_id}'

    # Имя и фамилия могут прийти из Telegram, но могут быть пустыми.
    first_name = telegram_data.get('first_name', '')
    last_name = telegram_data.get('last_name', '')

    # update_or_create ищет пользователя по telegram_id; если нашел — обновляет, если не нашел — создает.
    user, created = User.objects.update_or_create(
        telegram_id=telegram_id,
        defaults={
            # username нужен стандартной модели Django User.
            'username': username,

            # first_name и last_name — стандартные поля AbstractUser.
            'first_name': first_name,
            'last_name': last_name,

            # Все пользователи из Telegram Mini App по умолчанию считаются покупателями.
            'role': UserRole.CUSTOMER,
        },
    )

    # Возвращаем объект User, чтобы позже привязать его к Order.customer.
    return user