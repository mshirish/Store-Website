from decimal import Decimal

from django.db import models


class CategoryKind(models.TextChoices):
    CAKE = 'cake', 'Cake'
    MEAT = 'meat', 'Meat'
    GROCERY = 'grocery', 'Grocery'
    CATERING = 'catering', 'Catering'
    # Add new kinds here; each requires a matching Product subclass and pricing logic.


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    kind = models.CharField(max_length=20, choices=CategoryKind.choices)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal('0.0000'),
        help_text='Tax rate as a decimal (e.g. 0.0625 for 6.25%). Applied per line at checkout.',
    )

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.get_kind_display()})'


class CakeFlavor(models.Model):
    """
    Admin-managed list of available cake flavors.
    All active flavors are available for every cake — no per-product restriction.
    A price_modifier field can be added here later (Phase N) without a schema rewrite.
    """
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']

    def __str__(self):
        return self.name


# ── Product base (MTI) ────────────────────────────────────────────────────────

class Product(models.Model):
    name = models.CharField(max_length=200)
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name='products',
    )
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    is_available = models.BooleanField(
        default=True,
        help_text='Uncheck to hide this product on the storefront without deleting it.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ── Cake ──────────────────────────────────────────────────────────────────────

class CakeSize(models.TextChoices):
    SIX_INCH = '6_inch', '6 Inch'
    EIGHT_INCH = '8_inch', '8 Inch'
    NINE_INCH = '9_inch', '9 Inch'
    TEN_INCH = '10_inch', '10 Inch'
    SLICE = 'slice', 'Individual Slice'


class CakeProduct(Product):
    """
    Cake pricing is by size only. Flavors are drawn from the global CakeFlavor table.
    is_custom=True marks the single "Custom Cake" configurator entry (seeded, not
    admin-created); it is filtered out of the regular cake grid and shown separately.
    """
    is_custom = models.BooleanField(
        default=False,
        help_text='Marks the single custom cake configurator product. Do not create more than one.',
    )

    class Meta:
        verbose_name = 'Cake Product'
        verbose_name_plural = 'Cake Products'


class CakeSizePrice(models.Model):
    cake_product = models.ForeignKey(
        CakeProduct,
        on_delete=models.CASCADE,
        related_name='size_prices',
    )
    size = models.CharField(max_length=20, choices=CakeSize.choices)
    price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        unique_together = ('cake_product', 'size')
        ordering = ['size']

    def __str__(self):
        return f'{self.cake_product.name} — {self.get_size_display()}: ${self.price}'


# ── Meat ──────────────────────────────────────────────────────────────────────

class MeatProduct(Product):
    price_per_lb = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        help_text='Price in USD per pound.',
    )

    class Meta:
        verbose_name = 'Meat Product'
        verbose_name_plural = 'Meat Products'


# ── Grocery ───────────────────────────────────────────────────────────────────

class GroceryProduct(Product):
    """
    Standard unit-priced item. No stock tracking in Phase 1; add a
    stock_quantity field here when inventory is needed.
    """
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        verbose_name = 'Grocery Product'
        verbose_name_plural = 'Grocery Products'


# ── Catering ──────────────────────────────────────────────────────────────────

class CateringSection(models.Model):
    """Menu section heading for catering items (e.g. Appetizers, Main Course)."""
    name = models.CharField(max_length=100, unique=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Catering Section'
        verbose_name_plural = 'Catering Sections'

    def __str__(self):
        return self.name


class CateringProduct(Product):
    """
    A catering menu item. Pricing tiers are defined via CateringOption children
    (BY_TRAY or BY_WEIGHT). inquiry_only items display without a price and
    cannot be added to cart directly (e.g. custom desserts, ask-about items).
    """
    section = models.ForeignKey(
        CateringSection,
        on_delete=models.PROTECT,
        related_name='products',
    )
    inquiry_only = models.BooleanField(
        default=False,
        help_text='Show without a price; not directly orderable.',
    )

    class Meta:
        verbose_name = 'Catering Product'
        verbose_name_plural = 'Catering Products'


class PricingMode(models.TextChoices):
    BY_TRAY = 'by_tray', 'By Tray / Unit (fixed price × integer quantity)'
    BY_WEIGHT = 'by_weight', 'By Weight per lb (price × customer-entered weight)'


class CateringOption(models.Model):
    """
    A size / tier for a CateringProduct (e.g. "Regular", "Half Tray", 'Small 12"').
    One product may have options in different modes — e.g. Dips: per-lb + 5 lb tray.
    """
    catering_product = models.ForeignKey(
        CateringProduct,
        on_delete=models.CASCADE,
        related_name='options',
    )
    label = models.CharField(max_length=100, help_text='e.g. "Regular", "Half Tray", "Per Pound"')
    serves_note = models.CharField(
        max_length=200,
        blank=True,
        help_text='e.g. "Serves 18 to 20", "24 to 48 pcs"',
    )
    price = models.DecimalField(max_digits=8, decimal_places=2)
    pricing_mode = models.CharField(
        max_length=20,
        choices=PricingMode.choices,
        default=PricingMode.BY_TRAY,
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'label']
        unique_together = ('catering_product', 'label')

    def __str__(self):
        suffix = '/lb' if self.pricing_mode == PricingMode.BY_WEIGHT else ''
        note = f' ({self.serves_note})' if self.serves_note else ''
        return f'{self.catering_product.name} — {self.label}{note}: ${self.price}{suffix}'


class CateringVariant(models.Model):
    """
    An optional choice for a CateringProduct that does NOT affect price
    (e.g. "Meat" or "Veggie", "Chicken" or "Beef/Lamb", "Classic" or "Mix").
    Empty list = no variant selection required.
    """
    catering_product = models.ForeignKey(
        CateringProduct,
        on_delete=models.CASCADE,
        related_name='variants',
    )
    label = models.CharField(max_length=100, help_text='e.g. "Meat", "Veggie", "Chicken"')
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'label']
        unique_together = ('catering_product', 'label')

    def __str__(self):
        return f'{self.catering_product.name} — {self.label}'


# ── Custom Cake Options ───────────────────────────────────────────────────────

class CakeOptionGroup(models.Model):
    """
    Admin-editable category of customisation for the custom cake configurator
    (e.g. "Fruit Topping", "Outer Layer"). required=True forces the customer to
    pick a choice before adding to cart.
    """
    name = models.CharField(max_length=100, unique=True)
    display_order = models.PositiveIntegerField(default=0)
    required = models.BooleanField(
        default=False,
        help_text='If True, customer must select a choice for this group.',
    )

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Cake Option Group'
        verbose_name_plural = 'Cake Option Groups'

    def __str__(self):
        return self.name


class CakeOptionChoice(models.Model):
    """A single selectable choice within a CakeOptionGroup."""
    group = models.ForeignKey(
        CakeOptionGroup,
        on_delete=models.CASCADE,
        related_name='choices',
    )
    label = models.CharField(max_length=100)
    display_order = models.PositiveIntegerField(default=0)
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ['display_order', 'label']
        unique_together = ('group', 'label')

    def __str__(self):
        return f'{self.group.name} — {self.label}'
