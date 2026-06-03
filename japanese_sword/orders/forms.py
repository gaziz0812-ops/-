from django import forms

from .models import OrderItem


class OrderItemAdminForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = '__all__'
        labels = {
            'discount_percent': 'Скидка, %',
        }
