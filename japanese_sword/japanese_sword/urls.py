from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Подключаем публичный API каталога товаров.
    path('api/products/', include('products.urls')),
]

