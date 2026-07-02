from django.conf import settings
from django.db import models

from apps.catalog.models import CategoryKind, Product


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Cart({self.user})'

    def get_item_count(self):
        return self.items.count()

    def get_subtotal(self):
        from apps.cart.utils import compute_line_total
        return sum(
            compute_line_total(item.unit_price_snapshot, item.quantity)
            for item in self.items.all()
        )


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')

    # Live reference — used for availability checks and image display only.
    # CASCADE is intentional: dropping a deleted product from live carts is acceptable.
    product = models.ForeignKey(Product, on_delete=models.CASCADE)

    # Denormalised for efficient rendering without a join to category.
    kind = models.CharField(max_length=20, choices=CategoryKind.choices)

    # Snapshots — written once at add time; NEVER updated from live product data.
    product_name = models.CharField(max_length=200)
    unit_price_snapshot = models.DecimalField(max_digits=10, decimal_places=2)
    # grocery: integer qty; meat/by-weight catering: lbs (3 dp); cake: 1
    quantity = models.DecimalField(max_digits=10, decimal_places=3)

    # Cake-specific extras (null/blank for other kinds)
    cake_size = models.CharField(max_length=20, null=True, blank=True)
    cake_flavor_name = models.CharField(max_length=100, null=True, blank=True)  # snapshot
    cake_inscription = models.TextField(blank=True)
    cake_special_requests = models.TextField(blank=True)

    # Catering-specific extras (null/blank for other kinds)
    catering_option_label = models.CharField(max_length=100, null=True, blank=True)    # snapshot
    catering_serves_note = models.CharField(max_length=200, null=True, blank=True)     # snapshot
    catering_pricing_mode = models.CharField(max_length=20, blank=True)                # 'by_tray' or 'by_weight'
    catering_variant_choice = models.CharField(max_length=100, null=True, blank=True)  # snapshot
    catering_special_requests = models.TextField(blank=True)

    # Custom-cake-specific (blank for all other kinds)
    # JSON list of {group, choice} dicts, e.g. [{"group": "Fruit Topping", "choice": "Strawberry"}]
    custom_options_snapshot = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.product_name} x {self.quantity}'

    @property
    def line_total(self):
        from apps.cart.utils import compute_line_total
        return compute_line_total(self.unit_price_snapshot, self.quantity)

    @property
    def is_by_weight(self):
        return self.kind == 'meat' or (
            self.kind == 'catering' and self.catering_pricing_mode == 'by_weight'
        )

    @property
    def custom_options_list(self):
        import json
        if self.custom_options_snapshot:
            try:
                return json.loads(self.custom_options_snapshot)
            except (ValueError, TypeError):
                return []
        return []
