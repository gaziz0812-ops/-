from rest_framework import serializers

from .models import Product, ProductImage


# Легенда комментариев:
# [DRF] имя/метод/атрибут, который ожидает Django REST Framework.
# [OUR] наше поле/метод или наша бизнес-логика.


def get_media_url(image_field):
    # [OUR] Возвращаем относительный /media/... вместо http://127.0.0.1:8000/media/...
    # Так frontend-ngrok сможет проксировать картинки с другого устройства.
    if not image_field:
        return None

    return image_field.url


class ProductImageSerializer(serializers.ModelSerializer):
    # [DRF] SerializerMethodField берет значение из get_image(), а не из стандартного ImageField.
    image = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = (
            'id',
            'image',
            'sort_order',
        )

    def get_image(self, obj):
        # [OUR] obj здесь конкретная фотография товара ProductImage.
        return get_media_url(obj.image)


# ModelSerializer строит JSON-представление на основе модели Product.
# [OUR] Название класса наше; [DRF] ModelSerializer связывает serializer с моделью Product.
class ProductSerializer(serializers.ModelSerializer):
    # SerializerMethodField говорит DRF взять значение поля из метода get_stock_status().
    # [DRF] SerializerMethodField ищет метод get_<field_name>(), то есть get_stock_status().
    stock_status = serializers.SerializerMethodField()

    # [DRF] SerializerMethodField берет главное фото из get_image().
    image = serializers.SerializerMethodField()

    # [DRF] Meta — специальное имя: DRF сам читает model и fields.
    class Meta:
        # model связывает serializer с моделью Product.
        # [DRF] model — специальный атрибут Meta.
        model = Product

        # fields перечисляет публичные поля, которые попадут в JSON-ответ API.
        # [DRF] fields — специальный атрибут Meta.
        fields = (
            'id',
            'sku',
            'name',
            'sale_price',
            'stock_status',
            'image'
        )

    # [DRF] get_image() вызывается для поля image.
    def get_image(self, obj):
        # [OUR] obj здесь конкретный Product; возвращаем относительный путь к главному фото.
        return get_media_url(obj.image)

    # [DRF] get_stock_status() вызывается для поля stock_status.
    def get_stock_status(self, obj):
        # obj здесь конкретный Product, который DRF сейчас превращает в JSON.
        # [OUR] stock_balance — наше вычисляемое свойство модели Product.
        if obj.stock_balance > 1:
            return "В наличии"

        if obj.stock_balance == 1:
            return "Осталась 1 шт."

        return "Нет в наличии"


# Этот serializer используется для страницы одного товара: GET /api/products/<id>/
# [OUR] Название класса наше; наследуем короткий serializer и расширяем fields.
class ProductDetailSerializer(ProductSerializer):
    # [DRF] many=True говорит serializer, что у товара может быть много связанных ProductImage.
    # [OUR] images приходит из related_name='images' в модели ProductImage.
    images = ProductImageSerializer(many=True, read_only=True)

    # Meta наследуется от ProductSerializer.Meta, чтобы не дублировать model = Product.
    # [DRF] Meta(ProductSerializer.Meta) — расширение настроек родительского serializer.
    class Meta(ProductSerializer.Meta):
        # В detail-ответ добавляем описание товара, которого нет в коротком списке.
        # [DRF] fields остается специальным атрибутом; [OUR] добавляем 'description'.
        fields = ProductSerializer.Meta.fields + (
            'description',
            'images',
        )