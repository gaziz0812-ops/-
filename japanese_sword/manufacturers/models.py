from django.db import models

class Manufacturer(models.Model):
    name = models.CharField(max_length=255, unique=True)  # имя производител, длина строки, уникальная строка
    contacts = models.TextField(blank=True)  # контакты (поле может быть пустым)
    notes = models.TextField(blank=True)  # блокнот (поле может быть пустым)

    def __str__(self):
        return self.name


