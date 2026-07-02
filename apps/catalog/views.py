import json

from django.db.models import Prefetch, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from .models import (
    Category,
    CategoryKind,
    CakeFlavor,
    CakeOptionGroup,
    CakeProduct,
    CakeSize,
    CateringProduct,
    CateringSection,
    GroceryProduct,
    MeatProduct,
    PricingMode,
    Product,
)


def homepage(request):
    cats = {c.kind: c for c in Category.objects.filter(is_active=True)}
    return render(request, 'home.html', {'categories': cats})


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
    category = Category.objects.filter(kind=CategoryKind.CAKE, is_active=True).first()
    return render(request, 'catalog/cake_list.html', {
        'products': products,
        'custom_cake': custom_cake,
        'category': category,
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
    category = Category.objects.filter(kind=CategoryKind.MEAT, is_active=True).first()
    return render(request, 'catalog/meat_list.html', {'products': products, 'category': category})


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
    category = Category.objects.filter(kind=CategoryKind.GROCERY, is_active=True).first()
    return render(request, 'catalog/grocery_list.html', {'products': products, 'category': category})


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
    category = Category.objects.filter(kind=CategoryKind.CATERING, is_active=True).first()
    return render(request, 'catalog/catering_menu.html', {'sections': sections, 'category': category})


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


# ── Search ────────────────────────────────────────────────────────────────────

def _detail_url(product, custom_cake_pk):
    kind = product.category.kind
    if kind == CategoryKind.CAKE:
        if product.pk == custom_cake_pk:
            return reverse('catalog:custom_cake_detail')
        return reverse('catalog:cake_detail', args=[product.pk])
    if kind == CategoryKind.MEAT:
        return reverse('catalog:meat_detail', args=[product.pk])
    if kind == CategoryKind.GROCERY:
        return reverse('catalog:grocery_detail', args=[product.pk])
    if kind == CategoryKind.CATERING:
        return reverse('catalog:catering_detail', args=[product.pk])
    return '#'


def search_suggestions(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 2:
        return HttpResponse('')

    custom_cake_pk = (
        CakeProduct.objects.filter(is_custom=True)
        .values_list('pk', flat=True)
        .first()
    )
    products = (
        Product.objects
        .filter(is_available=True)
        .filter(Q(name__icontains=q) | Q(category__name__icontains=q))
        .select_related('category')
        .order_by('name')[:8]
    )
    results = [
        {
            'name': p.name,
            'kind_label': p.category.get_kind_display(),
            'url': _detail_url(p, custom_cake_pk),
            'image': p.image,
        }
        for p in products
    ]
    return render(request, 'catalog/search_suggestions.html', {
        'results': results,
        'query': q,
    })


def search_results(request):
    q = request.GET.get('q', '').strip()
    groups = []
    total = 0

    if q:
        name_q = Q(name__icontains=q) | Q(category__name__icontains=q)

        cakes = list(
            CakeProduct.objects
            .filter(is_available=True).filter(name_q)
            .select_related('category')
            .prefetch_related('size_prices')
            .order_by('is_custom', 'name')
        )
        meats = list(
            MeatProduct.objects
            .filter(is_available=True).filter(name_q)
            .select_related('category')
            .order_by('name')
        )
        groceries = list(
            GroceryProduct.objects
            .filter(is_available=True).filter(name_q)
            .select_related('category')
            .order_by('name')
        )
        caterings = list(
            CateringProduct.objects
            .filter(is_available=True)
            .filter(
                Q(name__icontains=q) |
                Q(category__name__icontains=q) |
                Q(section__name__icontains=q)
            )
            .select_related('category', 'section')
            .prefetch_related('options')
            .order_by('name')
        )

        if cakes:
            groups.append({'kind': 'cake', 'label': 'Cakes', 'products': cakes})
        if meats:
            groups.append({'kind': 'meat', 'label': 'Meat', 'products': meats})
        if groceries:
            groups.append({'kind': 'grocery', 'label': 'Grocery', 'products': groceries})
        if caterings:
            groups.append({'kind': 'catering', 'label': 'Catering', 'products': caterings})
        total = sum(len(g['products']) for g in groups)

    return render(request, 'catalog/search_results.html', {
        'query': q,
        'groups': groups,
        'total': total,
    })
