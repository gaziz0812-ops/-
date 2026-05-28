from django.contrib.auth.models import AbstractUser
from django.db import models

# класс для установки списка допустимых значений для поля
class UserRole(models.TextChoices):
    # первое значение для хранения в БД, второе для человека
    ADMIN = 'admin', 'Admin'
    MANAGER = 'manager', 'Manager'
    CUSTOMER = 'customer', 'Customer'

# класс кастомного юзера
class User(AbstractUser):
    # TG ID (может быть пустым)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    # строка с выбором роли. По дефолту - customer
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
    )

    def __str__(self):
        return self.username