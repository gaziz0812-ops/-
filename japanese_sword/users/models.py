from django.contrib.auth.models import AbstractUser
from django.db import models


# UserRole — набор допустимых ролей пользователя; в БД хранится первое значение, в админке видно второе.
class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Администратор'
    MANAGER = 'manager', 'Менеджер'
    CUSTOMER = 'customer', 'Покупатель'


# User расширяет стандартного Django-пользователя через AbstractUser.
class User(AbstractUser):
    # telegram_id понадобится для связи пользователя сайта/CRM с аккаунтом Telegram.
    telegram_id = models.BigIntegerField('Telegram ID', unique=True, null=True, blank=True)

    # choices ограничивает роль одним из значений UserRole.
    role = models.CharField(
        'Роль',
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
    )

    class Meta:
        verbose_name = 'Пользователя'
        verbose_name_plural = 'Пользователи'

    def __str__(self):
        return self.username
