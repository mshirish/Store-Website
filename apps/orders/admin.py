from django.contrib import admin, messages
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone

from .models import Order, OrderItem, Payment, OrderStatus, PaymentStatus, STATUS_TRANSITIONS

# States from which a pickup can legitimately be completed (advance already paid).
COMPLETABLE_STATUSES = frozenset([
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
])


# ── Inlines ───────────────────────────────────────────────────────────────────

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = (
        'product',
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
        'stripe_payment_intent_id',
        'status',
        'created_at',
        'captured_at',
    )

    def has_add_permission(self, request, obj=None):
        return False


# ── Admin actions ─────────────────────────────────────────────────────────────

@admin.action(description='Advance order status (one step forward)')
def advance_status(modeladmin, request, queryset):
    from apps.orders.emails import send_order_ready_email
    for order in queryset:
        next_status = STATUS_TRANSITIONS.get(order.status)
        if next_status:
            order.status = next_status
            order.save(update_fields=['status', 'updated_at'])
            if next_status == OrderStatus.READY:
                try:
                    send_order_ready_email(order)
                except Exception:
                    pass


@admin.action(description='Complete pickup — record balance paid + mark completed')
def complete_pickup(modeladmin, request, queryset):
    now = timezone.now()
    done = 0
    skipped = []
    for order in queryset:
        if order.status not in COMPLETABLE_STATUSES:
            skipped.append(str(order.pk))
            continue
        with transaction.atomic():
            update_fields = ['status', 'updated_at']
            if not order.balance_paid_at:
                order.balance_paid_at = now
                order.balance_paid_by = request.user
                update_fields += ['balance_paid_at', 'balance_paid_by']
            order.status = OrderStatus.COMPLETED
            order.save(update_fields=update_fields)
        done += 1
    if done:
        modeladmin.message_user(request, f'{done} order(s) completed and balance recorded.')
    if skipped:
        modeladmin.message_user(
            request,
            f'Skipped {len(skipped)} order(s) not in a completable state (#{", #".join(skipped)}).',
            level=messages.WARNING,
        )


@admin.action(description='Mark balance as paid (offline cash/card)')
def mark_balance_paid(modeladmin, request, queryset):
    now = timezone.now()
    for order in queryset.filter(balance_paid_at__isnull=True):
        order.balance_paid_at = now
        order.balance_paid_by = request.user
        order.save(update_fields=['balance_paid_at', 'balance_paid_by', 'updated_at'])


@admin.action(description='Cancel selected orders')
def cancel_orders(modeladmin, request, queryset):
    from apps.orders.emails import send_order_cancelled_email
    # exclude already-terminal statuses so we never double-cancel or double-email
    for order in queryset.exclude(status__in=[OrderStatus.COMPLETED, OrderStatus.CANCELLED]):
        # Neutralize any open Stripe sessions before cancelling so the webhook
        # cannot revive the order if a session completes within its TTL.
        order.payments.filter(status=PaymentStatus.PENDING).update(
            status=PaymentStatus.FAILED
        )
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=['status', 'updated_at'])
        try:
            send_order_cancelled_email(order)
        except Exception:
            pass


# ── Order admin ───────────────────────────────────────────────────────────────

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'customer',
        'contact_phone',
        'status',
        'pickup_date',
        'pickup_window',
        'order_total',
        'balance_is_paid',
        'created_at',
    )
    list_filter = ('status', 'fulfillment_type', 'pickup_date')
    search_fields = (
        'customer__email',
        'customer__first_name',
        'customer__last_name',
        'contact_phone',
    )
    date_hierarchy = 'pickup_date'
    actions = [advance_status, complete_pickup, mark_balance_paid, cancel_orders]
    inlines = [OrderItemInline, PaymentInline]

    readonly_fields = (
        'customer',
        'order_total',
        'tax_amount',
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
            'fields': ('order_total', 'tax_amount', 'advance_amount', 'balance_amount'),
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

    @admin.display(description='Pickup window')
    def pickup_window(self, obj):
        if obj.pickup_window_start and obj.pickup_window_end:
            def _fmt(t):
                h = t.hour % 12 or 12
                return f'{h}:{t.minute:02d} {"AM" if t.hour < 12 else "PM"}'
            return f'{_fmt(obj.pickup_window_start)} – {_fmt(obj.pickup_window_end)}'
        return '—'

    @admin.display(description='Balance paid', boolean=True)
    def balance_is_paid(self, obj):
        return bool(obj.balance_paid_at)

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related('customer', 'balance_paid_by')
            .order_by('pickup_date', 'pickup_window_start', '-created_at')
        )

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            try:
                obj = self.get_object(request, object_id)
                if obj and obj.status in COMPLETABLE_STATUSES:
                    extra_context['show_complete_pickup_button'] = True
            except Exception:
                pass
        return super().changeform_view(request, object_id, form_url, extra_context)

    def response_change(self, request, obj):
        if '_complete_pickup' in request.POST:
            if obj.status not in COMPLETABLE_STATUSES:
                self.message_user(
                    request,
                    f'Order #{obj.pk} cannot be completed from status "{obj.get_status_display()}".',
                    level=messages.ERROR,
                )
                return HttpResponseRedirect(request.path)
            with transaction.atomic():
                update_fields = ['status', 'updated_at']
                if not obj.balance_paid_at:
                    obj.balance_paid_at = timezone.now()
                    obj.balance_paid_by = request.user
                    update_fields += ['balance_paid_at', 'balance_paid_by']
                obj.status = OrderStatus.COMPLETED
                obj.save(update_fields=update_fields)
            self.message_user(
                request,
                f'Order #{obj.pk} marked as completed. Balance recorded as paid by {request.user}.',
            )
            return HttpResponseRedirect(request.path)
        return super().response_change(request, obj)

    def delete_queryset(self, request, queryset):
        for order in queryset.filter(status=OrderStatus.AWAITING_PAYMENT):
            order.payments.filter(status=PaymentStatus.PENDING).delete()
        super().delete_queryset(request, queryset)

    def delete_model(self, request, obj):
        if obj.status == OrderStatus.AWAITING_PAYMENT:
            obj.payments.filter(status=PaymentStatus.PENDING).delete()
        super().delete_model(request, obj)
