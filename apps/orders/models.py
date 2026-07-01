from django.conf import settings
from django.db import models


class OrderStatus(models.TextChoices):
    AWAITING_PAYMENT = 'awaiting_payment', 'Awaiting Payment'
    CONFIRMED = 'confirmed', 'Confirmed'
    PREPARING = 'preparing', 'Preparing'
    READY = 'ready', 'Ready for Pickup'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


# Forward path through the lifecycle (used by the admin advance-status action).
STATUS_TRANSITIONS = {
    OrderStatus.AWAITING_PAYMENT: OrderStatus.CONFIRMED,
    OrderStatus.CONFIRMED: OrderStatus.PREPARING,
    OrderStatus.PREPARING: OrderStatus.READY,
    OrderStatus.READY: OrderStatus.COMPLETED,
}


class FulfillmentType(models.TextChoices):
    PICKUP = 'pickup', 'Pickup'
    # DELIVERY = 'delivery', 'Delivery'  # Phase 4+


class Order(models.Model):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.AWAITING_PAYMENT,
    )
    fulfillment_type = models.CharField(
        max_length=20,
        choices=FulfillmentType.choices,
        default=FulfillmentType.PICKUP,
    )

    # Pickup
    pickup_date = models.DateField()
    # Snapshotted at order placement from get_pickup_window(); frozen thereafter
    # because StoreHours is mutable admin data.
    pickup_window_start = models.TimeField(null=True, blank=True)
    pickup_window_end = models.TimeField(null=True, blank=True)

    # Financials (all snapshotted at placement)
    order_total = models.DecimalField(max_digits=10, decimal_places=2)
    tax_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default='0.00',
        help_text='Total tax snapshotted at order placement (sum of per-line tax).',
    )
    advance_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Advance due in-app = order_total × (advance_percentage / 100).',
    )
    balance_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Remaining balance collected offline = order_total − advance_amount.',
    )

    # Offline balance payment (marked by staff in admin)
    balance_paid_at = models.DateTimeField(null=True, blank=True)
    balance_paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='balance_payments_marked',
    )

    # Captured at checkout; not required at account registration.
    # Shown prominently in admin so staff can call about timing.
    contact_phone = models.CharField(max_length=20, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def pre_tax_subtotal(self):
        return self.order_total - self.tax_amount

    def __str__(self):
        return f'Order #{self.pk} — {self.customer} ({self.get_status_display()})'


class PaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    CAPTURED = 'captured', 'Captured'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class Payment(models.Model):
    """
    Records the in-app advance payment transaction.
    Designed for Stripe (gateway_reference = PaymentIntent ID); not wired in Phase 1.
    """
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway = models.CharField(max_length=50, default='stripe')
    gateway_reference = models.CharField(max_length=200, null=True, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=200, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    captured_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Payment #{self.pk} — Order #{self.order_id} ({self.get_status_display()})'


class OrderItem(models.Model):
    """
    Line item with price and product-name snapshotted at order placement.
    Historical orders are unaffected by later product edits.
    Cake-specific fields (size, flavor, inscription, special requests) are
    nullable for meat and grocery items.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_items',
    )

    # Snapshots (immutable after creation)
    product_name = models.CharField(max_length=200)
    unit_price_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text='Price per unit/lb/size at time of order.',
    )
    # For grocery: integer quantity; for meat: weight in lbs (3 decimal places); for cake: 1.
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    line_total = models.DecimalField(max_digits=10, decimal_places=2)

    # Cake-specific extras (null/blank for non-cake items)
    cake_size = models.CharField(max_length=20, null=True, blank=True)
    cake_flavor_name = models.CharField(max_length=100, null=True, blank=True)  # snapshot
    cake_inscription = models.TextField(blank=True)
    cake_special_requests = models.TextField(blank=True)

    # Catering-specific extras (null/blank for non-catering items)
    catering_option_label = models.CharField(max_length=100, null=True, blank=True)   # snapshot
    catering_serves_note = models.CharField(max_length=200, null=True, blank=True)    # snapshot
    catering_variant_choice = models.CharField(max_length=100, null=True, blank=True) # snapshot
    catering_special_requests = models.TextField(blank=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.product_name} × {self.quantity} = ${self.line_total}'
