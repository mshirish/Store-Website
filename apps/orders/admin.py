from django.contrib import admin
from django.utils import timezone

from .models import Order, OrderItem, Payment, OrderStatus, STATUS_TRANSITIONS


# ── Inlines ───────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        'product_name',
        'unit_price_snapshot',
        'quantity',
        'line_total',
        'cake_size',
        'cake_flavor_name',
        'cake_inscription',
        'cake_special_requests',
        'catering_option_label',
        'catering_serves_note',
        'catering_variant_choice',
        'catering_special_requests',
    )

    def has_add_permission(self, request, obj=None):
        return False


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    can_delete = False
    readonly_fields = (
        'amount',
        'gateway',
        'gateway_reference',
        'status',
        'created_at',
        'captured_at',
    )

    def has_add_permission(self, request, obj=None):
        return False


# ── Admin actions ─────────────────────────────────────────────────────────────

@admin.action(description='Advance order status (one step forward)')
def advance_status(modeladmin, request, queryset):
    for order in queryset:
        next_status = STATUS_TRANSITIONS.get(order.status)
        if next_status:
            order.status = next_status
            order.save(update_fields=['status', 'updated_at'])


@admin.action(description='Mark balance as paid (offline cash/card)')
def mark_balance_paid(modeladmin, request, queryset):
    now = timezone.now()
    for order in queryset.filter(balance_paid_at__isnull=True):
        order.balance_paid_at = now
        order.balance_paid_by = request.user
        order.save(update_fields=['balance_paid_at', 'balance_paid_by', 'updated_at'])


@admin.action(description='Cancel selected orders')
def cancel_orders(modeladmin, request, queryset):
    for order in queryset.exclude(
        status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED]
    ):
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=['status', 'updated_at'])


# ── Order admin ───────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'status',
        'fulfillment_type',
        'pickup_date',
        'order_total',
        'advance_amount',
        'balance_amount',
        'balance_paid_at',
        'created_at',
    )
    list_filter = ('status', 'fulfillment_type', 'pickup_date')
    search_fields = ('customer__email', 'customer__first_name', 'customer__last_name')
    date_hierarchy = 'pickup_date'
    actions = [advance_status, mark_balance_paid, cancel_orders]
    inlines = [OrderItemInline, PaymentInline]

    readonly_fields = (
        'customer',
        'order_total',
        'advance_amount',
        'balance_amount',
        'pickup_window_start',
        'pickup_window_end',
        'balance_paid_at',
        'balance_paid_by',
        'created_at',
        'updated_at',
    )

    fieldsets = (
        ('Customer & Status', {
            'fields': ('customer', 'contact_phone', 'status', 'fulfillment_type'),
            'description': 'Call contact_phone to coordinate pickup timing for catering orders.',
        }),
        ('Pickup', {
            'fields': ('pickup_date', 'pickup_window_start', 'pickup_window_end'),
        }),
        ('Financials', {
            'fields': ('order_total', 'advance_amount', 'balance_amount'),
        }),
        ('Offline Balance Payment', {
            'fields': ('balance_paid_at', 'balance_paid_by'),
        }),
        ('Notes', {
            'fields': ('notes',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('customer', 'balance_paid_by')
