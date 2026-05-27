from django.contrib.auth.models import AbstractUser
from django.db import models


class UserRole(models.TextChoices):
    ADMIN = 'admin', 'Admin'
    MANAGER = 'manager', 'Manager'
    CUSTOMER = 'customer', 'Customer'


class User(AbstractUser):
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CUSTOMER,
    )

    def __str__(self):
        return self.username