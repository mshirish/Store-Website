import json
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST

from apps.catalog.models import (
    CakeFlavor,
    CakeSizePrice,
    CateringProduct,
    CategoryKind,
    PricingMode,
)
from .models import Cart, CartItem
from .utils import compute_line_total


def _get_or_create_cart(user):
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _htmx_row_and_totals(request, item, cart):
    """Return HTMX response: updated row (main swap) + totals (OOB swap)."""
    row_html = render_to_string('cart/_item_row.html', {'item': item}, request=request)
    totals_html = render_to_string('cart/_totals.html', {'cart': cart}, request=request)
    # _totals.html already wraps content in <div id="cart-totals" hx-swap-oob="true">
    return HttpResponse(row_html + totals_html)


# ── Cart page ─────────────────────────────────────────────────────────────────

@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product')
    return render(request, 'cart/cart.html', {'cart': cart, 'items': items})


# ── Add to cart ───────────────────────────────────────────────────────────────

def _toast_response(toast_type, message, extra_html=''):
    """Return a minimal HTMX response that fires a showToast event (+ optional OOB HTML)."""
    r = HttpResponse(extra_html)
    r['HX-Trigger'] = json.dumps({'showToast': {'type': toast_type, 'message': message}})
    return r


@login_required
@require_POST
def add_to_cart(request, product_pk):
    from apps.catalog.models import Product
    product = get_object_or_404(Product.objects.select_related('category'), pk=product_pk)
    kind = product.category.kind
    is_htmx = bool(request.headers.get('HX-Request'))

    try:
        if kind == CategoryKind.CAKE:
            item_data = _build_cake_item(request, product)
        elif kind == CategoryKind.MEAT:
            item_data = _build_meat_item(request, product)
        elif kind == CategoryKind.GROCERY:
            item_data = _build_grocery_item(request, product)
        elif kind == CategoryKind.CATERING:
            item_data = _build_catering_item(request, product)
        else:
            if is_htmx:
                return _toast_response('error', 'Unknown product type.')
            messages.error(request, 'Unknown product type.')
            return redirect(request.META.get('HTTP_REFERER', '/'))
    except ValidationError as exc:
        if is_htmx:
            return _toast_response('error', exc.message)
        messages.error(request, exc.message)
        return redirect(request.META.get('HTTP_REFERER', '/'))

    cart = _get_or_create_cart(request.user)
    CartItem.objects.create(cart=cart, product=product, kind=kind, **item_data)

    if is_htmx:
        badge_html = render_to_string(
            'cart/_cart_badge.html',
            {'cart_count': cart.get_item_count()},
        )
        return _toast_response('success', f'"{product.name}" added to your cart.', badge_html)

    messages.success(request, f'"{product.name}" added to your cart.')
    return redirect('cart:cart')


# ── Update / remove ───────────────────────────────────────────────────────────

@login_required
@require_POST
def update_cart_item(request, item_pk):
    item = get_object_or_404(CartItem, pk=item_pk, cart__user=request.user)

    if item.kind == CategoryKind.MEAT:
        try:
            w = Decimal(request.POST.get('weight', ''))
            if w > 0:
                item.quantity = w.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                item.save(update_fields=['quantity', 'updated_at'])
        except (InvalidOperation, ValueError):
            pass

    elif item.kind == CategoryKind.GROCERY:
        try:
            q = int(request.POST.get('quantity', ''))
            if q > 0:
                item.quantity = Decimal(q)
                item.save(update_fields=['quantity', 'updated_at'])
        except (ValueError, TypeError):
            pass

    elif item.kind == CategoryKind.CATERING:
        if item.catering_pricing_mode == PricingMode.BY_WEIGHT:
            try:
                w = Decimal(request.POST.get('weight', ''))
                if w > 0:
                    item.quantity = w.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
                    item.save(update_fields=['quantity', 'updated_at'])
            except (InvalidOperation, ValueError):
                pass
        else:
            try:
                q = int(request.POST.get('quantity', ''))
                if q > 0:
                    item.quantity = Decimal(q)
                    item.save(update_fields=['quantity', 'updated_at'])
            except (ValueError, TypeError):
                pass
    # cake: quantity is fixed at 1, no update path

    if request.headers.get('HX-Request'):
        return _htmx_row_and_totals(request, item, item.cart)
    return redirect('cart:cart')


@login_required
@require_POST
def remove_cart_item(request, item_pk):
    item = get_object_or_404(CartItem, pk=item_pk, cart__user=request.user)
    cart = item.cart
    item.delete()

    if request.headers.get('HX-Request'):
        if cart.get_item_count() == 0:
            # Full redirect so the empty-cart page renders properly
            from django.urls import reverse
            response = HttpResponse()
            response['HX-Redirect'] = reverse('cart:cart')
            return response
        totals_html = render_to_string('cart/_totals.html', {'cart': cart}, request=request)
        return HttpResponse(totals_html)
    return redirect('cart:cart')


# ── Kind-specific item builders ───────────────────────────────────────────────

def _build_cake_item(request, product):
    if not product.is_available:
        raise ValidationError('This product is not available.')
    try:
        cake = product.cakeproduct
    except Exception:
        raise ValidationError('Invalid product type.')

    size = request.POST.get('size', '').strip()
    flavor_name = request.POST.get('flavor_name', '').strip()

    try:
        size_price = cake.size_prices.get(size=size)
    except CakeSizePrice.DoesNotExist:
        raise ValidationError('Please select a valid size.')

    if not flavor_name or not CakeFlavor.objects.filter(name=flavor_name, is_active=True).exists():
        raise ValidationError('Please select a valid flavor.')

    return {
        'product_name': product.name,
        'unit_price_snapshot': size_price.price,
        'quantity': Decimal('1'),
        'cake_size': size,
        'cake_flavor_name': flavor_name,
        'cake_inscription': request.POST.get('cake_inscription', '').strip(),
        'cake_special_requests': request.POST.get('cake_special_requests', '').strip(),
    }


def _build_meat_item(request, product):
    if not product.is_available:
        raise ValidationError('This product is not available.')
    try:
        meat = product.meatproduct
    except Exception:
        raise ValidationError('Invalid product type.')

    try:
        weight = Decimal(request.POST.get('weight', '').strip())
        if weight <= 0:
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValidationError('Please enter a valid weight greater than 0 lbs.')

    return {
        'product_name': product.name,
        'unit_price_snapshot': meat.price_per_lb,
        'quantity': weight.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
    }


def _build_grocery_item(request, product):
    if not product.is_available:
        raise ValidationError('This product is not available.')
    try:
        grocery = product.groceryproduct
    except Exception:
        raise ValidationError('Invalid product type.')

    try:
        qty = int(request.POST.get('quantity', '').strip())
        if qty <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValidationError('Please enter a valid whole-number quantity.')

    return {
        'product_name': product.name,
        'unit_price_snapshot': grocery.unit_price,
        'quantity': Decimal(qty),
    }


def _build_catering_item(request, product):
    if not product.is_available:
        raise ValidationError('This product is not available.')
    try:
        catering = product.cateringproduct
    except Exception:
        raise ValidationError('Invalid product type.')

    if catering.inquiry_only:
        raise ValidationError('This item is not directly orderable. Please contact us.')

    option_label = request.POST.get('option_label', '').strip()
    try:
        option = catering.options.get(label=option_label)
    except Exception:
        raise ValidationError('Please select a valid option/tier.')

    variants = catering.variants.all()
    variant_choice = None
    if variants.exists():
        variant_label = request.POST.get('variant', '').strip()
        if not variants.filter(label=variant_label).exists():
            raise ValidationError('Please select a valid variant.')
        variant_choice = variant_label

    if option.pricing_mode == PricingMode.BY_WEIGHT:
        try:
            weight = Decimal(request.POST.get('weight', '').strip())
            if weight <= 0:
                raise ValueError()
        except (InvalidOperation, ValueError):
            raise ValidationError('Please enter a valid weight greater than 0 lbs.')
        quantity = weight.quantize(Decimal('0.001'), rounding=ROUND_HALF_UP)
    else:
        try:
            qty = int(request.POST.get('quantity', '1').strip())
            if qty <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValidationError('Please enter a valid quantity.')
        quantity = Decimal(qty)

    return {
        'product_name': product.name,
        'unit_price_snapshot': option.price,
        'quantity': quantity,
        'catering_option_label': option.label,
        'catering_serves_note': option.serves_note,
        'catering_pricing_mode': option.pricing_mode,
        'catering_variant_choice': variant_choice,
        'catering_special_requests': request.POST.get('catering_special_requests', '').strip(),
    }
