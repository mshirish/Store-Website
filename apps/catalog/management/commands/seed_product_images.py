"""
python manage.py seed_product_images [--dry-run] [--catering-limit N]

Fills missing product images from the Pixabay API. Additive: only products
with no image are touched, so it is safe to re-run. Images are saved through
the ImageField, so they go to whichever storage is configured (R2 or the
local filesystem).

Scope:
  - Every cake (except the custom cake), meat and grocery product
  - Up to --catering-limit catering products per run (default 15), picked
    round-robin across menu sections; inquiry-only items are skipped

Requires PIXABAY_API_KEY in the environment / .env.
"""
import time
from itertools import zip_longest

import environ
import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from django.utils.text import slugify

PIXABAY_URL = 'https://pixabay.com/api/'
REQUEST_DELAY = 0.5   # seconds between Pixabay requests
TIMEOUT = 20          # seconds per HTTP request

# Product name -> Pixabay search query, for names that search poorly as-is.
_QUERY_OVERRIDES = {
    # Cakes
    'Pistachio Cake':           'pistachio cake',
    'Baklava Cake':             'honey walnut cake',
    'Chocolate Ganache Cake':   'chocolate cake',
    'Vanilla Rosewater Cake':   'vanilla cake',
    'Date & Walnut Cake':       'walnut cake',
    # Meat
    'Chicken Breast':           'raw chicken breast',
    'Ground Beef':              'minced meat',
    'Lamb Chops':               'lamb chops',
    'Beef Shawarma Strips':     'sliced beef',
    'Chicken Thighs':           'raw chicken',
    # Grocery
    'Extra Virgin Olive Oil':   'olive oil',
    'Pomegranate Molasses':     'pomegranate',
    'Orange Blossom Water':     'orange blossom',
    'Sumac':                    'sumac spice',
    'Zaatar Spice Blend':       'zaatar',
    'Seven Spice (Baharat)':    'spices',
    'Bulgur Wheat':             'bulgur',
    'Chickpeas (canned)':       'chickpeas',
    'Fava Beans (canned)':      'fava beans',
    'Markook Bread':            'flatbread',
    'Sesame Bread Rings (Kaak)': 'simit',
    'Labneh':                   'labneh',
    'Halloumi Cheese':          'halloumi',
    'Stuffed Grape Leaves (jar)': 'stuffed grape leaves',
    'Date Syrup':               'dates',
    'Mixed Nuts (roasted)':     'mixed nuts',
    # Catering
    'Kibbeh':                   'kibbeh',
    'Baked Kibbeh':             'kibbeh',
    'Kibbeh Neye':              'raw kibbeh',
    'Sambouski':                'meat pastry',
    'Zaatar':                   'manakish',
    'Muhammara':                'red pepper dip',
    'Muhammara Pie':            'red pepper flatbread',
    'Cheese & Tomato Pie':      'cheese tomato flatbread',
    'Cheese & Veggie Pie':      'vegetable flatbread',
    'Spinach with Cheese Pie':  'spinach pie',
    'Salad Tray':               'fattoush salad',
    'Fattoush':                 'fattoush salad',
    'Greek Salad Tray':         'greek salad',
    'Tabouleh':                 'tabbouleh',
    'Spanakopita / Tiropita / Leekopita': 'spanakopita',
    'Small Pies (Spanakopita / Tiropita / Leekopita)': 'spanakopita',
    'Grape Leaves':             'stuffed grape leaves',
    'Make Your Own Platter':    'mezze platter',
    'Dips':                     'hummus',
    'Marinated Chicken Kabob':  'chicken kebab',
    'Marinated Lamb or Beef Kabob': 'lamb kebab',
    'Kefta Beef Kabob':         'kofta kebab',
    'Kefta with Veggies & Potatoes in Tomato Sauce': 'kofta tomato sauce',
    'Eggplant Tray':            'baked eggplant',
    'Chicken & Piccata in White Sauce': 'chicken piccata',
    'Chicken & Rice Garnished with Nuts': 'chicken rice',
    'Rice Garnished with Nuts': 'rice with nuts',
    'Baklava':                  'baklava',
}


def _no_image():
    return Q(image='') | Q(image__isnull=True)


class Command(BaseCommand):
    help = 'Fill missing product images (cake, meat, grocery, some catering) from Pixabay.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Search Pixabay and report what would be set, without downloading or saving.',
        )
        parser.add_argument(
            '--catering-limit', type=int, default=15,
            help='Maximum catering images to set in this run (default 15).',
        )

    def handle(self, *args, dry_run, catering_limit, **options):
        env = environ.Env()
        self.api_key = env('PIXABAY_API_KEY', default='').strip()
        if not self.api_key:
            raise CommandError(
                'PIXABAY_API_KEY is not set. Add it to .env or the environment '
                '(get a key at https://pixabay.com/api/docs/).'
            )
        self.session = requests.Session()
        self.used_hit_ids = set()   # avoid giving two products the same photo
        self.dry_run = dry_run

        set_count = 0
        no_result = []
        skipped_existing = self._count_skipped_existing()

        self.stdout.write(f'{"[dry-run] " if dry_run else ""}Filling missing product images from Pixabay...')

        for product in self._storefront_products():
            if self._fill(product):
                set_count += 1
            else:
                no_result.append(product)

        catering_set = 0
        for product in self._catering_products():
            if catering_set >= catering_limit:
                break
            if self._fill(product):
                set_count += 1
                catering_set += 1
            else:
                no_result.append(product)

        verb = 'would be set' if dry_run else 'set'
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Images {verb}: {set_count} (catering: {catering_set}/{catering_limit})'
        ))
        self.stdout.write(f'Skipped (already had an image): {skipped_existing}')
        self.stdout.write(f'No result / failed: {len(no_result)}')
        for product in no_result:
            self.stdout.write(self.style.WARNING(
                f'  * {product.name} ({product.category.get_kind_display()}, pk={product.pk}) '
                '— needs a manual image'
            ))

    # ── Product selection ─────────────────────────────────────────────────────

    def _storefront_products(self):
        from apps.catalog.models import CakeProduct, GroceryProduct, MeatProduct

        yield from CakeProduct.objects.filter(_no_image(), is_custom=False).select_related('category').order_by('pk')
        yield from MeatProduct.objects.filter(_no_image()).select_related('category').order_by('pk')
        yield from GroceryProduct.objects.filter(_no_image()).select_related('category').order_by('pk')

    def _catering_products(self):
        """Round-robin across sections so the cap covers the whole menu."""
        from apps.catalog.models import CateringProduct

        qs = (
            CateringProduct.objects.filter(_no_image(), inquiry_only=False)
            .select_related('category', 'section')
            .order_by('section__sort_order', 'pk')
        )
        by_section = {}
        for product in qs:
            by_section.setdefault(product.section_id, []).append(product)
        for row in zip_longest(*by_section.values()):
            yield from (p for p in row if p is not None)

    def _count_skipped_existing(self):
        from apps.catalog.models import CakeProduct, CateringProduct, GroceryProduct, MeatProduct

        return (
            CakeProduct.objects.filter(is_custom=False).exclude(_no_image()).count()
            + MeatProduct.objects.exclude(_no_image()).count()
            + GroceryProduct.objects.exclude(_no_image()).count()
            + CateringProduct.objects.filter(inquiry_only=False).exclude(_no_image()).count()
        )

    # ── Pixabay ───────────────────────────────────────────────────────────────

    def _fill(self, product):
        """Find, download and save one image. Returns True if set (or would be)."""
        query = _QUERY_OVERRIDES.get(product.name, product.name)
        hit = self._search(query)
        if hit is None and 'food' not in query.split():
            hit = self._search(f'{query} food')
        if hit is None:
            self.stdout.write(self.style.WARNING(f'  [no result] {product.name} (q="{query}")'))
            return False

        image_url = hit.get('largeImageURL') or hit.get('webformatURL')
        if self.dry_run:
            self.stdout.write(f'  [dry-run] {product.name} <- {image_url}')
            self.used_hit_ids.add(hit.get('id'))
            return True

        try:
            response = self.session.get(image_url, timeout=TIMEOUT)
            response.raise_for_status()
            if not response.headers.get('Content-Type', '').startswith('image/'):
                raise ValueError(f'unexpected content type {response.headers.get("Content-Type")!r}')
        except (requests.RequestException, ValueError) as exc:
            self.stdout.write(self.style.WARNING(f'  [download failed] {product.name}: {exc}'))
            return False

        product.image.save(f'{slugify(product.name) or "product"}.jpg', ContentFile(response.content), save=True)
        self.used_hit_ids.add(hit.get('id'))
        self.stdout.write(f'  [set] {product.name} <- "{query}" ({product.image.name})')
        return True

    def _search(self, query):
        """First unused Pixabay hit for query, or None on no hits / any error."""
        params = {
            'key': self.api_key,
            'q': query[:100],
            'image_type': 'photo',
            'orientation': 'horizontal',
            'per_page': 3,
            'safesearch': 'true',
        }
        for attempt in range(2):
            time.sleep(REQUEST_DELAY)
            try:
                response = self.session.get(PIXABAY_URL, params=params, timeout=TIMEOUT)
                if response.status_code == 429 and attempt == 0:
                    # Pixabay allows 100 requests/minute; wait for the window to reset.
                    wait = int(response.headers.get('X-RateLimit-Reset', 60)) + 1
                    self.stdout.write(self.style.WARNING(f'  [rate limited] waiting {wait}s...'))
                    time.sleep(wait)
                    continue
                response.raise_for_status()
                hits = response.json().get('hits', [])
            except (requests.RequestException, ValueError) as exc:
                # Never echo the URL: it contains the API key.
                status = getattr(getattr(exc, 'response', None), 'status_code', '')
                self.stdout.write(self.style.WARNING(
                    f'  [request error] q="{query}": {type(exc).__name__} {status}'.rstrip()
                ))
                return None
            unused = [h for h in hits if h.get('id') not in self.used_hit_ids]
            return (unused or hits or [None])[0]
        return None
