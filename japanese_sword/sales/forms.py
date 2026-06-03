from django import forms

from .models import Sale, SaleReturn


# Кастомный Select добавляет в option товара данные для JS: цену и остаток.
class ProductPriceSelect(forms.Select):
    price_map = {}
    stock_balance_map = {}

    # create_option — метод Django forms, который создает HTML option для select.
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)

        if value:
            product = getattr(value, 'instance', None)
            sale_price = product.sale_price if product else self.price_map.get(str(value), '')
            stock_balance = product.stock_balance if product else self.stock_balance_map.get(str(value), '')

            # data-* атрибуты потом читает JS в админке продажи.
            option['attrs']['data-sale-price'] = str(sale_price)
            option['attrs']['data-stock-balance'] = str(stock_balance)

        return option


# SaleAdminForm настраивает форму продажи в Django admin.
class SaleAdminForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = '__all__'

        # Для поля product используем кастомный Select с data-sale-price и data-stock-balance.
        widgets = {
            'product': ProductPriceSelect,
        }
        labels = {
            'discount_percent': 'Discount, %',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # При просмотре readonly-продажи поля product может не быть в форме.
        product_field = self.fields.get('product')
        if not product_field:
            return

        # price_map заранее готовит цены товаров для HTML option.
        product_field.widget.price_map = {
            str(product.pk): str(product.sale_price)
            for product in product_field.queryset
        }

        # stock_balance_map заранее готовит остатки товаров для HTML option.
        product_field.widget.stock_balance_map = {
            str(product.pk): str(product.stock_balance)
            for product in product_field.queryset
        }


class SaleReturnAdminForm(forms.ModelForm):
    class Meta:
        model = SaleReturn
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        sale_field = self.fields.get('sale')
        if not sale_field:
            return

        order_id = self.data.get('order') or getattr(self.instance, 'order_id', None)

        if order_id:
            # Если выбран заказ, список продаж ограничивается продажами этого заказа.
            sale_field.queryset = Sale.objects.filter(order_id=order_id)
        else:
            # Без заказа поле продажи оставляем пустым, чтобы не выбирать позицию вслепую.
            sale_field.queryset = Sale.objects.none()
