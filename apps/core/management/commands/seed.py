"""
python manage.py seed

Idempotent: safe to run multiple times. Only creates rows that don't exist yet.
Seeds:
  - CakeFlavor defaults (4 flavors)
  - One starter Category per CategoryKind
  - StoreHours for all 7 weekdays
  - SiteConfiguration singleton
  - CateringSection (10 sections)
  - CateringProduct / CateringOption / CateringVariant (full menu)
  - Custom Cake product (with default size prices)
  - CakeOptionGroup / CakeOptionChoice (Fruit Topping, Outer Layer)

After seeding, any items requiring owner confirmation are printed as warnings.
"""
import datetime
from decimal import Decimal

from django.core.management.base import BaseCommand

# ── Catering seed data ────────────────────────────────────────────────────────

_SECTIONS = [
    ('Appetizers',    10),
    ('Closed Pies',   20),
    ('Open Pies',     30),
    ('Salads',        40),
    ('Finger Foods',  50),
    ('Platters',      60),
    ('Dips',          70),
    ('Grilled Kabobs', 80),
    ('Main Course',   90),
    ('Desserts',      100),
]

T = 'by_tray'
W = 'by_weight'

# Each product entry:
# (section_name, product_name, inquiry_only, [variants], [options], flag_or_None)
# options: (label, serves_note, price_str, mode, sort_order)
_PRODUCTS = [

    # ── Appetizers (all per dozen) ────────────────────────────────────────────
    ('Appetizers', 'Kibbeh', False,
     ['Meat', 'Veggie'],
     [
         ('Regular', 'Per Dozen', '52.00', T, 0),
         ('Party',   'Per Dozen', '100.00', T, 1),
     ], None),

    ('Appetizers', 'Falafel with Tahini Sauce', False,
     [],
     [
         ('Regular', 'Per Dozen', '17.00', T, 0),
         ('Party',   'Per Dozen', '27.00', T, 1),
     ], None),

    # ── Closed Pies ───────────────────────────────────────────────────────────
    # FLAG: For Appetizers, Party > Regular (larger qty). For Closed Pies the
    # photo shows Regular $48 / Party $18 — Party is cheaper, opposite pattern.
    # Seeded as-is from the menu; confirm whether columns are correct or swapped.
    ('Closed Pies', 'Spinach Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], 'CLOSED PIES PRICING: Party ($18) < Regular ($48) is opposite of the Appetizers pattern. Confirm the Regular/Party values for all Closed Pies are correct, or advise if the columns are swapped.'),

    ('Closed Pies', 'Spinach with Cheese Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], 'CLOSED PIES PRICING: same concern as Spinach Pie above.'),

    ('Closed Pies', 'Meat Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], 'CLOSED PIES PRICING: same concern as Spinach Pie above.'),

    ('Closed Pies', 'Chicken Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], 'CLOSED PIES PRICING: same concern as Spinach Pie above.'),

    ('Closed Pies', 'Sambouski', False,
     [],
     [
         ('Regular', '', '28.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], 'CLOSED PIES PRICING: same concern as Spinach Pie above (Sambouski Regular=$28, Party=$18).'),

    # ── Open Pies ─────────────────────────────────────────────────────────────
    ('Open Pies', 'Zaatar', False,
     [],
     [
         ('Regular', '', '28.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    ('Open Pies', 'Cheese Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    ('Open Pies', 'Spinach with Cheese Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    ('Open Pies', 'Cheese & Tomato Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    ('Open Pies', 'Cheese & Veggie Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    ('Open Pies', 'Muhammara Pie', False,
     [],
     [
         ('Regular', '', '48.00', T, 0),
         ('Party',   '', '18.00', T, 1),
     ], None),

    # ── Salads ────────────────────────────────────────────────────────────────
    # Fattoush/Cabbage/House/Spinach & Onions/Spinach & Cheese share the same
    # tiers; the salad type is a variant choice.
    ('Salads', 'Salad Tray', False,
     ['Fattoush', 'Cabbage', 'House', 'Spinach & Onions', 'Spinach & Cheese'],
     [
         ('Deep Tray', 'Serves 18 to 20', '55.00', T, 0),
         ('Half Tray', 'Serves 10 to 12', '30.00', T, 1),
     ], None),

    ('Salads', 'Greek Salad Tray', False,
     [],
     [
         ('Tray',     '', '60.00', T, 0),
         ('Half Tray', '', '35.00', T, 1),
     ], None),

    ('Salads', 'Tabouleh', False,
     [],
     [
         ('Tray',     'Serves 25 to 30', '100.00', T, 0),
         ('Half Tray', 'Serves 15 to 20', '55.00', T, 1),
     ], None),

    # ── Finger Foods ──────────────────────────────────────────────────────────
    ('Finger Foods', 'Spanakopita / Tiropita / Leekopita', False,
     ['Spanakopita', 'Tiropita', 'Leekopita'],
     [
         ('Tray',     '24 to 48 pcs',  '56.00', T, 0),
         ('Half Tray', '12 to 24 pcs', '30.00', T, 1),
     ], None),

    ('Finger Foods', 'Grape Leaves', False,
     ['Veggie', 'Meat'],
     [
         ('Tray', 'Approx 30 to 36 pcs', '36.00', T, 0),
     ], None),

    # FLAG: the menu shows Small Pies at $55 with one tier only. Label seeded
    # as "Tray" — confirm if a different label is preferred.
    ('Finger Foods', 'Small Pies (Spanakopita / Tiropita / Leekopita)', False,
     ['Spanakopita', 'Tiropita', 'Leekopita'],
     [
         ('Tray', 'Serves 25 to 30', '55.00', T, 0),
     ], 'SMALL PIES TIER LABEL: seeded as "Tray (Serves 25 to 30) $55". Confirm this label is correct, or provide a preferred label.'),

    # ── Platters ──────────────────────────────────────────────────────────────
    # Customer's 5 choices + dip go in catering_special_requests for now.
    ('Platters', 'Make Your Own Platter', False,
     [],
     [
         ('Small 12"',  'Serves 10 to 12', '55.00',  T, 0),
         ('Med 16"',    'Serves 15 to 18', '85.00',  T, 1),
         ('Large 18"',  'Serves 22 to 25', '110.00', T, 2),
     ], None),

    # ── Dips ──────────────────────────────────────────────────────────────────
    # Sold strictly by weight. The "~5 lb serves 20 to 25" note is a purchase
    # estimate shown to the customer, not a fixed package.
    ('Dips', 'Dips', False,
     ['Hummus', 'Baba Ghanoush', 'Tzatziki', 'Muhammara'],
     [
         ('Per Pound', '~5 lb serves 20 to 25', '6.99', W, 0),
     ], None),

    # ── Grilled Kabobs (per skewer) ───────────────────────────────────────────
    ('Grilled Kabobs', 'Marinated Chicken Kabob', False,
     [],
     [
         ('Per Skewer', '', '5.99', T, 0),
     ], None),

    ('Grilled Kabobs', 'Marinated Lamb or Beef Kabob', False,
     ['Lamb', 'Beef'],
     [
         ('Per Skewer', '', '7.99', T, 0),
     ], None),

    ('Grilled Kabobs', 'Kefta Beef Kabob', False,
     [],
     [
         ('Per Skewer', '', '5.99', T, 0),
     ], None),

    # ── Main Course ───────────────────────────────────────────────────────────
    ('Main Course', 'Kefta with Veggies & Potatoes in Tomato Sauce', False,
     [],
     [
         ('Tray', '', '100.00', T, 0),
     ], None),

    # Two size tiers on one product
    ('Main Course', 'Baked Kibbeh', False,
     [],
     [
         ('Tray',  '12 pcs',                '48.00', T, 0),
         ('Large', 'Cut to specification',  '95.00', T, 1),
     ], None),

    ('Main Course', 'Eggplant Tray', False,
     [],
     [
         ('Tray', 'Serves 15 to 18', '75.00', T, 0),
     ], None),

    ('Main Course', 'Chicken Alfredo', False,
     [],
     [
         ('Tray', 'Serves 18 to 20', '100.00', T, 0),
     ], None),

    ('Main Course', 'Chicken & Piccata in White Sauce', False,
     [],
     [
         ('Tray', 'Serves 18 to 20', '100.00', T, 0),
     ], None),

    ('Main Course', 'Shawarma', False,
     ['Chicken', 'Beef/Lamb'],
     [
         ('Per Pound', '', '17.00', W, 0),
     ], None),

    # Two tiers on one product
    ('Main Course', 'Rice Pilaf', False,
     [],
     [
         ('Tray',     'Serves 20 to 30', '60.00', T, 0),
         ('Half Tray', 'Serves 15',      '35.00', T, 1),
     ], None),

    ('Main Course', 'Chicken & Rice Garnished with Nuts', False,
     [],
     [
         ('Tray', 'Serves 25 to 30', '120.00', T, 0),
     ], None),

    # FLAG: "Rice Garnished with Nuts" and "Kibbeh Neye" appear together on the
    # menu photo. Seeded as two separate products. Confirm this is correct, or
    # advise if they should be combined (e.g. as options on one product).
    ('Main Course', 'Rice Garnished with Nuts', False,
     [],
     [
         ('Large Tray', 'Serves 25 to 30', '75.00', T, 0),
     ], 'RICE / KIBBEH NEYE GROUPING: "Rice Garnished with Nuts" and "Kibbeh Neye" appear grouped on the menu photo. Seeded as two separate products. Confirm split, or advise if they should be combined.'),

    ('Main Course', 'Kibbeh Neye', False,
     [],
     [
         ('Per Pound', '', '17.00', W, 0),
     ], 'RICE / KIBBEH NEYE GROUPING: see note above.'),

    # ── Desserts ──────────────────────────────────────────────────────────────
    ('Desserts', 'Baklava', False,
     ['Classic', 'Mix (Cashew, Walnut, Pistachio)'],
     [
         ('Large Tray', '24 to 48 pieces', '46.00', T, 0),
         ('Small Tray', '12 to 24 pieces', '26.00', T, 1),
     ], None),

    # inquiry_only — no price shown, not directly orderable.
    ('Desserts', 'Assorted Cookies, Kataifi or Milfei', True,
     [],
     [], None),
]


class Command(BaseCommand):
    help = 'Seed default flavors, categories, store hours, site configuration, and catering menu.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data...')
        self._seed_flavors()
        self._seed_categories()
        self._seed_store_hours()
        self._seed_site_config()
        self._seed_catering_sections()
        flagged = self._seed_catering_products()
        self._seed_custom_cake()
        self._seed_cake_option_groups()
        self.stdout.write(self.style.SUCCESS('Done.'))

        if flagged:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING('*** ITEMS NEEDING OWNER CONFIRMATION:'))
            seen = set()
            for msg in flagged:
                if msg not in seen:
                    self.stdout.write(self.style.WARNING(f'  * {msg}'))
                    seen.add(msg)

    # ── Flavors ───────────────────────────────────────────────────────────────

    def _seed_flavors(self):
        from apps.catalog.models import CakeFlavor

        defaults = [
            ('Chocolate Mixed Fruit', 0),
            ('Vanilla Strawberry',    1),
            ('Vanilla Mixed Fruit',   2),
            ('Chocolate Mousse',      3),
        ]
        for name, sort_order in defaults:
            _, created = CakeFlavor.objects.get_or_create(
                name=name,
                defaults={'sort_order': sort_order, 'is_active': True},
            )
            if created:
                self.stdout.write(f'  [flavor] Created: {name}')

    # ── Categories ────────────────────────────────────────────────────────────

    def _seed_categories(self):
        from apps.catalog.models import Category, CategoryKind

        starters = [
            (CategoryKind.CAKE,      'Cakes'),
            (CategoryKind.MEAT,      'Meats'),
            (CategoryKind.GROCERY,   'Groceries'),
            (CategoryKind.CATERING,  'Catering'),
        ]
        for kind, name in starters:
            if not Category.objects.filter(kind=kind).exists():
                Category.objects.create(name=name, kind=kind, is_active=True)
                self.stdout.write(f'  [category] Created: {name}')

    # ── Store hours ───────────────────────────────────────────────────────────

    def _seed_store_hours(self):
        from apps.core.models import StoreHours

        # weekday: 0=Mon … 4=Fri, 5=Sat, 6=Sun
        schedule = {
            0: (datetime.time(8, 30), datetime.time(19, 0), False),
            1: (datetime.time(8, 30), datetime.time(19, 0), False),
            2: (datetime.time(8, 30), datetime.time(19, 0), False),
            3: (datetime.time(8, 30), datetime.time(19, 0), False),
            4: (datetime.time(8, 30), datetime.time(19, 0), False),
            5: (datetime.time(8, 30), datetime.time(18, 0), False),
            6: (datetime.time(10, 0), datetime.time(15, 0), False),
        }
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        for weekday, (open_t, close_t, is_closed) in schedule.items():
            _, created = StoreHours.objects.get_or_create(
                weekday=weekday,
                defaults={'open_time': open_t, 'close_time': close_t, 'is_closed': is_closed},
            )
            if created:
                self.stdout.write(f'  [hours] Created: {day_names[weekday]}')

    # ── Site configuration ────────────────────────────────────────────────────

    def _seed_site_config(self):
        from apps.core.models import SiteConfiguration

        config = SiteConfiguration.get()
        self.stdout.write(
            f'  [config] SiteConfiguration ready (advance: {config.advance_percentage}%)'
        )

    # ── Catering sections ─────────────────────────────────────────────────────

    def _seed_catering_sections(self):
        from apps.catalog.models import CateringSection

        for name, sort_order in _SECTIONS:
            _, created = CateringSection.objects.get_or_create(
                name=name,
                defaults={'sort_order': sort_order},
            )
            if created:
                self.stdout.write(f'  [section] Created: {name}')

    # ── Catering products ─────────────────────────────────────────────────────

    def _seed_catering_products(self) -> list[str]:
        from apps.catalog.models import (
            Category, CategoryKind,
            CateringSection, CateringProduct, CateringOption, CateringVariant,
        )

        catering_category = Category.objects.filter(kind=CategoryKind.CATERING).first()
        if not catering_category:
            self.stdout.write(self.style.ERROR(
                '  [catering] No CATERING category found — run seed again after _seed_categories.'
            ))
            return []

        flagged_messages = []

        for (section_name, product_name, inquiry_only,
             variants, options, flag) in _PRODUCTS:

            section = CateringSection.objects.get(name=section_name)

            # Lookup by (name, section) to allow same name in different sections.
            product = CateringProduct.objects.filter(
                name=product_name, section=section
            ).first()

            if product is None:
                product = CateringProduct.objects.create(
                    name=product_name,
                    section=section,
                    category=catering_category,
                    inquiry_only=inquiry_only,
                    is_available=True,
                )
                self.stdout.write(f'  [catering] Created: {section_name} -> {product_name}')

            # Options
            for (label, serves_note, price_str, mode, sort_order) in options:
                _, created = CateringOption.objects.get_or_create(
                    catering_product=product,
                    label=label,
                    defaults={
                        'serves_note': serves_note,
                        'price': Decimal(price_str),
                        'pricing_mode': mode,
                        'sort_order': sort_order,
                    },
                )
                if created:
                    self.stdout.write(f'    [option] {label}: ${price_str} ({mode})')

            # Variants
            for i, variant_label in enumerate(variants):
                _, created = CateringVariant.objects.get_or_create(
                    catering_product=product,
                    label=variant_label,
                    defaults={'sort_order': i},
                )
                if created:
                    self.stdout.write(f'    [variant] {variant_label}')

            if flag:
                flagged_messages.append(flag)

        return flagged_messages

    # ── Custom Cake product ───────────────────────────────────────────────────

    def _seed_custom_cake(self):
        from apps.catalog.models import Category, CategoryKind, CakeProduct, CakeSizePrice, CakeSize

        cake_category = Category.objects.filter(kind=CategoryKind.CAKE).first()
        if not cake_category:
            self.stdout.write(self.style.ERROR(
                '  [custom_cake] No CAKE category found — run seed after _seed_categories.'
            ))
            return

        product, created = CakeProduct.objects.get_or_create(
            is_custom=True,
            defaults={
                'name': 'Custom Cake',
                'category': cake_category,
                'description': (
                    'Design your own cake. Choose your size, flavor, and optional toppings — '
                    'add an inscription or any special requests.'
                ),
                'is_available': True,
            },
        )
        if created:
            self.stdout.write('  [custom_cake] Created: Custom Cake')

        # Default size prices — admin can adjust these freely in the dashboard.
        default_prices = [
            (CakeSize.SIX_INCH,   Decimal('30.00')),
            (CakeSize.EIGHT_INCH,  Decimal('45.00')),
            (CakeSize.NINE_INCH,   Decimal('55.00')),
            (CakeSize.TEN_INCH,    Decimal('65.00')),
        ]
        for size, price in default_prices:
            _, sp_created = CakeSizePrice.objects.get_or_create(
                cake_product=product,
                size=size,
                defaults={'price': price},
            )
            if sp_created:
                self.stdout.write(f'    [size_price] {size}: ${price}')

    # ── Cake option groups ────────────────────────────────────────────────────

    def _seed_cake_option_groups(self):
        from apps.catalog.models import CakeOptionGroup, CakeOptionChoice

        groups_data = [
            ('Fruit Topping', 10, False, [
                ('Strawberry',   0),
                ('Blueberry',    1),
                ('Raspberry',    2),
                ('Mixed Fruit',  3),
                ('No Fruit',     4),
            ]),
            ('Outer Layer', 20, False, [
                ('Whipped Cream',  0),
                ('Fondant',        1),
                ('Buttercream',    2),
                ('No Preference',  3),
            ]),
        ]

        for group_name, display_order, required, choices in groups_data:
            group, created = CakeOptionGroup.objects.get_or_create(
                name=group_name,
                defaults={'display_order': display_order, 'required': required},
            )
            if created:
                self.stdout.write(f'  [option_group] Created: {group_name}')

            for label, choice_order in choices:
                _, c_created = CakeOptionChoice.objects.get_or_create(
                    group=group,
                    label=label,
                    defaults={'display_order': choice_order, 'is_available': True},
                )
                if c_created:
                    self.stdout.write(f'    [choice] {label}')
