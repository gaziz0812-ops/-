from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


# Регистрируем кастомную модель User в админке вместо стандартного пользователя Django.
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    # list_display определяет колонки в списке пользователей.
    list_display = ('id', 'username', 'email', 'role', 'telegram_id', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')

    # UserAdmin.fieldsets — стандартные блоки формы пользователя; добавляем к ним Telegram и роль.
    fieldsets = UserAdmin.fieldsets + (
        ('Telegram и роль', {'fields': ('telegram_id', 'role')}),
    )
