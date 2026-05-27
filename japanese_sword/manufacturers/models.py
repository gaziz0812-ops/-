from django.db import models

class Manufacturer(models.Model):
    name = models.CharField(max_length=255, unique=True)  # имя производител = 255 длина строки, уникальная строка
    contacts = models.TextField(blank=True)  # контакты = поле может быть пустым
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


