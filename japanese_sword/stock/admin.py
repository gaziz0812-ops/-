from django.contrib import admin, messages

from .models import (
    StockBatch,
    StockMovement,
    StockReservation,
    StockReservationAllocation,
    StockWriteOff,
    StockWriteOffAllocation,
)


# Словарь переводит технический source_type из БД в человекочитаемый текст для админки.
SOURCE_TYPE_NAMES = {
    'sale': 'Продажа',
    'supply_item': 'Позиция поставки',
    'manual_supply_item': 'Ручная позиция поставки',
    'sale_return': 'Возврат',
    'sale_return_write_off': 'Списание возврата',
    'stock_write_off': 'Списание',
    'stock_reservation': 'Резерв',
    'stock_reservation_release': 'Снятие резерва',
}


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    # StockMovement — журнал, поэтому добавление и удаление вручную запрещены ниже.
    list_display = (
        'id',
        'product',
        'movement_type',
        'quantity',
        'display_source_type',
        'source_id',
        'created_at'
    )
    list_filter = ('movement_type', 'source_type', 'created_at')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = (
        'product',
        'movement_type',
        'quantity',
        'display_source_type',
        'source_id',
        'created_at',
    )
    fieldsets = (
        ('Движение', {
            'fields': ('product', 'movement_type', 'quantity'),
        }),
        ('Источник', {
            'fields': ('display_source_type', 'source_id'),
        }),
        ('Служебные данные', {
            'fields': ('created_at',),
        }),
    )

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        # obj здесь конкретная запись StockMovement или StockBatch из админки.
        return SOURCE_TYPE_NAMES.get(obj.source_type, obj.source_type)

    # Специальный метод Django admin: запрещает кнопку "Добавить".
    def has_add_permission(self, request):
        return False

    # Просмотр изменения оставлен, но все поля readonly.
    def has_change_permission(self, request, obj=None):
        return True

    # Специальный метод Django admin: запрещает удаление движений склада.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    # Партии показываем как справочник FIFO, но не создаем руками.
    list_display = (
        'id',
        'product',
        'quantity',
        'remaining_quantity',
        'unit_cost',
        'display_source_type',
        'source_id',
        'created_at',
    )
    list_filter = ('created_at', 'source_type')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = (
        'product',
        'quantity',
        'remaining_quantity',
        'unit_cost',
        'display_source_type',
        'source_id',
        'created_at',
    )
    fieldsets = (
        ('Партия', {
            'fields': ('product', 'quantity', 'remaining_quantity', 'unit_cost'),
        }),
        ('Источник', {
            'fields': ('display_source_type', 'source_id'),
        }),
        ('Служебные данные', {
            'fields': ('created_at',),
        }),
    )

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        return SOURCE_TYPE_NAMES.get(obj.source_type, obj.source_type)

    # Партии создаются поставками, возвратами и складскими операциями, не вручную.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


class StockWriteOffAllocationInline(admin.TabularInline):
    # Inline показывает, из каких партий было сделано списание.
    model = StockWriteOffAllocation
    verbose_name = 'Списание из партии'
    verbose_name_plural = 'Списания из партий'
    extra = 0
    can_delete = False
    fields = ('stock_batch', 'quantity')
    readonly_fields = ('stock_batch', 'quantity')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StockWriteOff)
class StockWriteOffAdmin(admin.ModelAdmin):
    # Списания можно создавать, но после создания редактирование и удаление запрещены.
    list_display = (
        'id',
        'product',
        'quantity',
        'reason',
        'created_at',
    )
    list_filter = ('reason', 'created_at')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = ('created_at',)
    inlines = (StockWriteOffAllocationInline,)
    fieldsets = (
        ('Списание', {
            'fields': ('product', 'quantity', 'reason', 'comment'),
        }),
        ('Служебные данные', {
            'fields': ('created_at',),
        }),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # obj есть при открытии уже созданного списания; тогда все бизнес-поля readonly.
        if obj:
            return (
                'product',
                'quantity',
                'reason',
                'comment',
                'created_at',
            )

        return self.readonly_fields


class StockReservationAllocationInline(admin.TabularInline):
    # Inline показывает, какие партии затронул резерв.
    model = StockReservationAllocation
    verbose_name = 'Резерв из партии'
    verbose_name_plural = 'Резервы из партий'
    extra = 0
    can_delete = False
    readonly_fields = ('stock_batch', 'quantity', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StockReservation)
class StockReservationAdmin(admin.ModelAdmin):
    # Резерв создается вручную, а снимается через admin action.
    list_display = (
        'id',
        'product',
        'quantity',
        'status',
        'created_at',
        'released_at',
    )
    list_filter = ('status', 'created_at', 'released_at')
    search_fields = ('product__sku', 'product__name')
    readonly_fields = ('status', 'created_at', 'released_at')
    inlines = (StockReservationAllocationInline,)
    actions = ('release_reservations',)
    fieldsets = (
        ('Резерв', {
            'fields': ('product', 'quantity', 'comment'),
        }),
        ('Служебные данные', {
            'fields': ('status', 'created_at', 'released_at'),
        }),
    )

    @admin.action(description='Снять выбранные резервы')
    def release_reservations(self, request, queryset):
        # queryset — выбранные в админке резервы.
        released_count = 0

        for reservation in queryset:
            if reservation.status == StockReservation.Status.RELEASED:
                continue

            reservation.release()
            released_count += 1

        self.message_user(
            request,
            f'Снято резервов: {released_count}',
            messages.SUCCESS,
        )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        # Созданный резерв нельзя редактировать напрямую; его можно только снять.
        if obj:
            return (
                'product',
                'quantity',
                'status',
                'comment',
                'created_at',
                'released_at',
            )

        return self.readonly_fields
