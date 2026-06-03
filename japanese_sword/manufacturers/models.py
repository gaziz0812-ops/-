from django.db import models


# Manufacturer — справочник производителей для товаров.
class Manufacturer(models.Model):
    name = models.CharField('Название', max_length=255, unique=True)
    contacts = models.TextField('Контакты', blank=True)
    notes = models.TextField('Заметки', blank=True)

    class Meta:
        # verbose_name и verbose_name_plural задают русские названия модели в админке.
        verbose_name = 'Производителя'
        verbose_name_plural = 'Производители'

    def __str__(self):
        # __str__ определяет, как производитель отображается в списках и ForeignKey-полях.
        return self.name
