from django.contrib import admin, messages

from .models import (
    StockBatch,
    StockMovement,
    StockReservation,
    StockReservationAllocation,
    StockWriteOff,
    StockWriteOffAllocation,
)


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

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        return SOURCE_TYPE_NAMES.get(obj.source_type, obj.source_type)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
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

    @admin.display(description='Тип источника')
    def display_source_type(self, obj):
        return SOURCE_TYPE_NAMES.get(obj.source_type, obj.source_type)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return False


class StockWriteOffAllocationInline(admin.TabularInline):
    model = StockWriteOffAllocation
    verbose_name = 'Списание из партии'
    verbose_name_plural = 'Списания из партий'
    extra = 0
    can_delete = False
    readonly_fields = ('stock_batch', 'quantity', 'unit_cost', 'total_cost', 'created_at')

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(StockWriteOff)
class StockWriteOffAdmin(admin.ModelAdmin):
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
