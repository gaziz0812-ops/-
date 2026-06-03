from django.urls import include, path
from rest_framework.routers import DefaultRouter # роутер DRF сам создает URL для ViewSet

from .views import ProductViewSet


router = DefaultRouter()

# Регистрируем ProductViewSet на корне products.urls: /api/products/ и /api/products/<id>/.
router.register('', ProductViewSet, basename='product')


urlpatterns = [
    # Подключаем URL, которые автоматически создал DRF router.
    path('', include(router.urls)),
]
