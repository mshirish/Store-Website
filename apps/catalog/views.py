import json

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, render

from .models import (
    CakeFlavor,
    CakeOptionGroup,
    CakeProduct,
    CakeSize,
    CateringProduct,
    CateringSection,
    GroceryProduct,
    MeatProduct,
    PricingMode,
)


def homepage(request):
    return render(request, 'home.html')


# ── Cakes ─────────────────────────────────────────────────────────────────────

def cake_list(request):
    products = (
        CakeProduct.objects
        .filter(is_available=True, is_custom=False)
        .prefetch_related('size_prices')
        .select_related('category')
        .order_by('name')
    )
    custom_cake = (
        CakeProduct.objects
        .filter(is_custom=True, is_available=True)
        .prefetch_related('size_prices')
        .first()
    )
    return render(request, 'catalog/cake_list.html', {
        'products': products,
        'custom_cake': custom_cake,
    })


def cake_detail(request, pk):
    product = get_object_or_404(CakeProduct, pk=pk, is_available=True, is_custom=False)
    size_prices = list(product.size_prices.order_by('size'))
    flavors = CakeFlavor.objects.filter(is_active=True)
    sizes_json = json.dumps({sp.size: str(sp.price) for sp in size_prices})
    size_labels = {choice.value: choice.label for choice in CakeSize}
    return render(request, 'catalog/cake_detail.html', {
        'product': product,
        'size_prices': size_prices,
        'flavors': flavors,
        'sizes_json': sizes_json,
        'size_labels': size_labels,
    })


def custom_cake_detail(request):
    product = get_object_or_404(CakeProduct, is_custom=True, is_available=True)
    size_prices = list(product.size_prices.order_by('size'))
    flavors = CakeFlavor.objects.filter(is_active=True)
    groups = (
        CakeOptionGroup.objects
        .prefetch_related('choices')
        .order_by('display_order', 'name')
    )
    sizes_json = json.dumps({sp.size: str(sp.price) for sp in size_prices})
    size_labels = {choice.value: choice.label for choice in CakeSize}
    return render(request, 'catalog/custom_cake_detail.html', {
        'product': product,
        'size_prices': size_prices,
        'flavors': flavors,
        'groups': groups,
        'sizes_json': sizes_json,
        'size_labels': size_labels,
    })


# ── Meat ──────────────────────────────────────────────────────────────────────

def meat_list(request):
    products = (
        MeatProduct.objects
        .filter(is_available=True)
        .select_related('category')
        .order_by('name')
    )
    return render(request, 'catalog/meat_list.html', {'products': products})


def meat_detail(request, pk):
    product = get_object_or_404(MeatProduct, pk=pk, is_available=True)
    return render(request, 'catalog/meat_detail.html', {'product': product})


# ── Grocery ───────────────────────────────────────────────────────────────────

def grocery_list(request):
    products = (
        GroceryProduct.objects
        .filter(is_available=True)
        .select_related('category')
        .order_by('name')
    )
    return render(request, 'catalog/grocery_list.html', {'products': products})


def grocery_detail(request, pk):
    product = get_object_or_404(GroceryProduct, pk=pk, is_available=True)
    return render(request, 'catalog/grocery_detail.html', {'product': product})


# ── Catering ──────────────────────────────────────────────────────────────────

def catering_menu(request):
    sections = (
        CateringSection.objects
        .prefetch_related(
            Prefetch(
                'products',
                queryset=(
                    CateringProduct.objects
                    .filter(is_available=True)
                    .prefetch_related('options', 'variants')
                    .order_by('name')
                ),
            )
        )
        .order_by('sort_order', 'name')
    )
    return render(request, 'catalog/catering_menu.html', {'sections': sections})


def catering_detail(request, pk):
    product = get_object_or_404(CateringProduct, pk=pk, is_available=True)
    options = list(product.options.order_by('sort_order', 'label'))
    variants = list(product.variants.order_by('sort_order', 'label'))
    options_json = json.dumps([
        {'label': o.label, 'pricing_mode': o.pricing_mode, 'price': str(o.price)}
        for o in options
    ])
    return render(request, 'catalog/catering_detail.html', {
        'product': product,
        'options': options,
        'variants': variants,
        'options_json': options_json,
        'BY_WEIGHT': PricingMode.BY_WEIGHT,
    })
