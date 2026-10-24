import datetime
import json
import logging
import time
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.timezone import localdate
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.cart.models import Cart, CartItem
from apps.cart.utils import compute_line_total
from apps.catalog.models import CategoryKind
from apps.core.models import SiteConfiguration
from apps.core.utils import get_next_open_day, get_pickup_window, is_open_on_date
from .models import Order, OrderItem, OrderStatus, Payment, PaymentStatus
from .services import abandon_pending_order, confirm_paid_session, retrieve_checkout_session


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_checkout_context(cart):
    items = list(cart.items.select_related('product__category'))
    config = SiteConfiguration.get()

    pre_tax_subtotal = sum(compute_line_total(i.unit_price_snapshot, i.quantity) for i in items)
    tax_amount = sum(
        compute_line_total(
            compute_line_total(i.unit_price_snapshot, i.quantity),
            i.product.category.tax_rate,
        )
        for i in items
    )
    order_total = pre_tax_subtotal + tax_amount
    advance_amount = (order_total * config.advance_percentage / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    balance_amount = order_total - advance_amount

    today = localdate()
    earliest_pickup = get_next_open_day(from_date=today)

    invalid_dates = []
    for i in range(1, 91):
        d = today + datetime.timedelta(days=i)
        if not is_open_on_date(d):
            invalid_dates.append(d.isoformat())

    return {
        'cart': cart,
        'items': items,
        'pre_tax_subtotal': pre_tax_subtotal,
        'tax_amount': tax_amount,
        'order_total': order_total,
        'advance_amount': advance_amount,
        'balance_amount': balance_amount,
        'config': config,
        'earliest_pickup': earliest_pickup.isoformat() if earliest_pickup else '',
        'invalid_dates_json': json.dumps(invalid_dates),
    }


def _get_current_price(item):
    """Live price for a CartItem. Returns None on any error."""
    try:
        if item.kind == CategoryKind.CAKE:
            return item.product.cakeproduct.size_prices.get(size=item.cake_size).price
        if item.kind == CategoryKind.MEAT:
            return item.product.meatproduct.price_per_lb
        if item.kind == CategoryKind.GROCERY:
            return item.product.groceryproduct.unit_price
        if item.kind == CategoryKind.CATERING:
            return item.product.cateringproduct.options.get(
                label=item.catering_option_label
            ).price
    except Exception:
        return None
    return None


# ── Helpers (continued) ───────────────────────────────────────────────────────

def _annotate_items(queryset):
    """Attach ._kind to each OrderItem for template branching."""
    items = list(queryset.select_related('product__category'))
    for item in items:
        if item.cake_size or item.cake_flavor_name:
            item.kind = CategoryKind.CAKE
        elif item.catering_option_label:
            item.kind = CategoryKind.CATERING
        else:
            kind = None
            if item.product_id:
                try:
                    kind = item.product.category.kind
                except Exception:
                    pass
            item.kind = kind or CategoryKind.GROCERY
    return items


# ── Views ─────────────────────────────────────────────────────────────────────

@login_required
def order_list(request):
    orders = Order.objects.visible_to_customer().filter(customer=request.user).order_by('-created_at')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.visible_to_customer(), pk=pk, customer=request.user)
    items = _annotate_items(order.items.all())
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'items': items,
        'just_paid': request.GET.get('just_paid') == '1',
    })


@login_required
def checkout(request):
    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        messages.info(request, 'Your cart is empty.')
        return redirect('cart:cart')

    if not cart.items.exists():
        messages.info(request, 'Your cart is empty.')
        return redirect('cart:cart')

    return render(request, 'checkout/checkout.html', _build_checkout_context(cart))


def pickup_window_fragment(request):
    date_str = request.GET.get('pickup_date', '').strip()
    try:
        pickup_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        return HttpResponse('<p class="text-red-600 text-sm mt-1">Invalid date.</p>')

    window = get_pickup_window(pickup_date)
    if window is None:
        return HttpResponse(
            '<p class="text-red-600 text-sm mt-1">The store is closed on this date. '
            'Please choose another.</p>'
        )
    open_time, close_time = window
    return render(request, 'checkout/_pickup_window.html', {
        'open_time': open_time,
        'close_time': close_time,
    })


@login_required
@require_POST
def place_order(request):
    try:
        cart = request.user.cart
    except Cart.DoesNotExist:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart:cart')

    items = list(cart.items.select_related('product__category'))
    if not items:
        messages.error(request, 'Your cart is empty.')
        return redirect('cart:cart')

    # ── Re-validation pass ────────────────────────────────────────────────────

    availability_errors = []
    price_changed = []

    for item in items:
        product = item.product
        if not product.is_available:
            availability_errors.append(
                f'"{item.product_name}" is no longer available. Please remove it from your cart.'
            )
            continue
        if item.kind == CategoryKind.CATERING:
            try:
                if product.cateringproduct.inquiry_only:
                    availability_errors.append(
                        f'"{item.product_name}" is now inquiry-only and cannot be ordered. '
                        'Please remove it.'
                    )
                    continue
            except Exception:
                pass

        current_price = _get_current_price(item)
        if current_price is not None and current_price != item.unit_price_snapshot:
            price_changed.append({
                'name': item.product_name,
                'old': item.unit_price_snapshot,
                'new': current_price,
                'item_pk': item.pk,
            })

    if availability_errors:
        for err in availability_errors:
            messages.error(request, err)
        return redirect('orders:checkout')

    if price_changed:
        for pc in price_changed:
            CartItem.objects.filter(pk=pc['item_pk']).update(unit_price_snapshot=pc['new'])
        for pc in price_changed:
            messages.warning(
                request,
                f'Price for "{pc["name"]}" changed from ${pc["old"]} to ${pc["new"]}. '
                'Your cart has been updated. Please review and place your order again.',
            )
        return redirect('orders:checkout')

    # ── Pickup date validation ────────────────────────────────────────────────

    date_str = request.POST.get('pickup_date', '').strip()
    try:
        pickup_date = datetime.date.fromisoformat(date_str)
    except ValueError:
        messages.error(request, 'Please select a valid pickup date.')
        return redirect('orders:checkout')

    today = localdate()
    earliest = get_next_open_day(from_date=today)
    if earliest is None or pickup_date < earliest:
        messages.error(request, 'The selected pickup date is not available. Please choose another.')
        return redirect('orders:checkout')

    pickup_window = get_pickup_window(pickup_date)
    if pickup_window is None:
        messages.error(request, 'The store is closed on the selected date. Please choose another.')
        return redirect('orders:checkout')

    pickup_window_start, pickup_window_end = pickup_window

    # ── Collect contact fields ────────────────────────────────────────────────

    contact_phone = request.POST.get('contact_phone', '').strip()
    notes = request.POST.get('notes', '').strip()

    # ── Compute financials ────────────────────────────────────────────────────

    config = SiteConfiguration.get()
    # Re-fetch after any price-change snapshots
    items = list(cart.items.select_related('product__category'))

    pre_tax_subtotal = sum(compute_line_total(i.unit_price_snapshot, i.quantity) for i in items)
    tax_amount = sum(
        compute_line_total(
            compute_line_total(i.unit_price_snapshot, i.quantity),
            i.product.category.tax_rate,
        )
        for i in items
    )
    order_total = pre_tax_subtotal + tax_amount
    advance_amount = (order_total * config.advance_percentage / Decimal('100')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )
    balance_amount = order_total - advance_amount

    # ── Discard any earlier unfinished checkout ───────────────────────────────
    # Only one pending checkout per customer. If Stripe says an earlier one was
    # actually paid, it gets confirmed here instead and we stop.

    for pending in Order.objects.filter(customer=request.user, status=OrderStatus.AWAITING_PAYMENT):
        try:
            if not abandon_pending_order(pending):
                messages.success(request, f'Your payment for order #{pending.pk} went through.')
                return redirect(reverse('orders:order_detail', kwargs={'pk': pending.pk}) + '?just_paid=1')
        except Exception:
            logger.warning('Could not verify earlier pending order #%d', pending.pk, exc_info=True)

    # ── Create order (hidden until the advance is confirmed) ──────────────────

    with transaction.atomic():
        order = Order.objects.create(
            customer=request.user,
            pickup_date=pickup_date,
            pickup_window_start=pickup_window_start,
            pickup_window_end=pickup_window_end,
            order_total=order_total,
            tax_amount=tax_amount,
            advance_amount=advance_amount,
            balance_amount=balance_amount,
            contact_phone=contact_phone,
            notes=notes,
        )
        for item in items:
            OrderItem.objects.create(
                order=order,
                product=item.product,
                product_name=item.product_name,
                unit_price_snapshot=item.unit_price_snapshot,
                quantity=item.quantity,
                line_total=compute_line_total(item.unit_price_snapshot, item.quantity),
                cake_size=item.cake_size or '',
                cake_flavor_name=item.cake_flavor_name or '',
                cake_inscription=item.cake_inscription,
                cake_special_requests=item.cake_special_requests,
                custom_options_snapshot=item.custom_options_snapshot,
                catering_option_label=item.catering_option_label or '',
                catering_serves_note=item.catering_serves_note or '',
                catering_variant_choice=item.catering_variant_choice or '',
                catering_special_requests=item.catering_special_requests,
            )
        # The cart is NOT cleared here: confirm_paid_session() empties it once
        # the advance is paid, so abandoning Stripe leaves the cart intact.

    # Redirect to Stripe Checkout. The order stays invisible to the customer
    # until the advance is confirmed (success redirect or webhook).
    import stripe as stripe_lib
    stripe_lib.api_key = settings.STRIPE_SECRET_KEY

    success_url = (
        request.build_absolute_uri(
            reverse('orders:payment_success', kwargs={'pk': order.pk})
        )
        + '?session_id={CHECKOUT_SESSION_ID}'
    )
    cancel_url = request.build_absolute_uri(
        reverse('orders:payment_cancel', kwargs={'pk': order.pk})
    )

    payment_error = (
        'We could not connect to our payment provider, so your order was not placed. '
        'Your cart is unchanged. Please try again.'
    )

    try:
        session = stripe_lib.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'unit_amount': int(order.advance_amount * 100),
                    'product_data': {
                        'name': f'Order #{order.pk} — Advance Payment',
                        'description': (
                            f'Advance for pickup on {order.pickup_date.strftime("%B %d, %Y")}. '
                            f'Balance of ${order.balance_amount} due at pickup.'
                        ),
                    },
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=success_url,
            cancel_url=cancel_url,
            customer_email=request.user.email,
            metadata={'order_pk': str(order.pk)},
            # Stripe's minimum; lets abandoned checkouts be cleaned up quickly.
            expires_at=int(time.time()) + 30 * 60,
        )
    except Exception:
        logger.error('Stripe session creation failed for order %d', order.pk, exc_info=True)
        order.delete()
        messages.error(request, payment_error)
        return redirect('orders:checkout')

    try:
        Payment.objects.create(
            order=order,
            amount=order.advance_amount,
            gateway='stripe',
            gateway_reference=session.id,
            status=PaymentStatus.PENDING,
        )
    except Exception:
        logger.error(
            'Stripe session %s was created for order %d but the local Payment row failed '
            'to save. Expiring the session and discarding the order.',
            session.id, order.pk, exc_info=True,
        )
        try:
            stripe_lib.checkout.Session.expire(session.id)
            order.delete()
        except Exception:
            logger.error('Could not expire Stripe session %s', session.id, exc_info=True)
        messages.error(request, payment_error)
        return redirect('orders:checkout')

    return redirect(session.url)


@login_required
def order_confirmation(request, pk):
    get_object_or_404(Order.objects.visible_to_customer(), pk=pk, customer=request.user)
    return redirect('orders:order_detail', pk=pk)


@login_required
def payment_success(request, pk):
    """
    Stripe success return. Verifies the payment with Stripe directly, so the
    order is confirmed even if the webhook never arrives.
    """
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    session_id = request.GET.get('session_id', '')

    if order.status == OrderStatus.AWAITING_PAYMENT and session_id:
        # Only trust a session that we created for this order.
        if order.payments.filter(gateway_reference=session_id).exists():
            try:
                confirm_paid_session(retrieve_checkout_session(session_id))
            except Exception:
                logger.warning(
                    'Could not verify Stripe session %s for order %d on return',
                    session_id, order.pk, exc_info=True,
                )
        order.refresh_from_db(fields=['status'])

    if order.status != OrderStatus.AWAITING_PAYMENT:
        return redirect(reverse('orders:order_detail', kwargs={'pk': pk}) + '?just_paid=1')

    # Not confirmed yet (Stripe unreachable or payment still settling). This page
    # refreshes itself, re-running the verification above.
    return render(request, 'orders/payment_success.html', {'order': order})


@login_required
def payment_cancel(request, pk):
    """Stripe cancel return: discard the unpaid checkout and go back to checkout."""
    order = get_object_or_404(Order, pk=pk, customer=request.user)
    if order.status == OrderStatus.AWAITING_PAYMENT:
        try:
            if not abandon_pending_order(order):
                return redirect(reverse('orders:order_detail', kwargs={'pk': pk}) + '?just_paid=1')
        except Exception:
            # Stripe unreachable: the order stays hidden and its session expires
            # on its own; reconcile_stripe_orders removes it later.
            logger.warning('Could not abandon pending order %d', pk, exc_info=True)
        messages.info(request, 'Payment was not completed, so no order was placed. Your cart is unchanged.')
        return redirect('orders:checkout')
    return redirect('orders:order_detail', pk=pk)


@login_required
@require_POST
def cancel_order(request, pk):
    from apps.orders.emails import send_order_cancelled_email

    get_object_or_404(Order.objects.visible_to_customer(), pk=pk, customer=request.user)

    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=pk)
        if not order.is_active:
            messages.error(request, 'Only active orders can be cancelled.')
            return redirect('orders:order_detail', pk=pk)
        order.status = OrderStatus.CANCELLED
        order.save(update_fields=['status', 'updated_at'])

    try:
        send_order_cancelled_email(order)
    except Exception:
        pass

    messages.success(request, f'Order #{order.pk} has been cancelled.')
    return redirect('orders:order_list')


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """
    Backup confirmation path. The success redirect normally confirms the order
    first; both go through confirm_paid_session(), so the second one is a no-op.
    """
    import stripe as stripe_lib

    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        event = stripe_lib.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except stripe_lib.error.SignatureVerificationError as exc:
        logger.warning('Stripe webhook signature verification failed: %s', exc)
        return HttpResponse(status=400)
    except Exception as exc:
        logger.error('Stripe webhook: unexpected error parsing event: %s', exc, exc_info=True)
        return HttpResponse(status=400)

    if event['type'] in ('checkout.session.completed', 'checkout.session.async_payment_succeeded'):
        _handle_checkout_completed(event['data']['object'])
    elif event['type'] == 'checkout.session.expired':
        _handle_checkout_expired(event['data']['object'])

    return HttpResponse(status=200)


def _handle_checkout_completed(session):
    confirm_paid_session(session)


def _handle_checkout_expired(session):
    payment = (
        Payment.objects.select_related('order')
        .filter(gateway_reference=session['id'], order__status=OrderStatus.AWAITING_PAYMENT)
        .first()
    )
    if payment:
        try:
            abandon_pending_order(payment.order)
        except Exception:
            logger.warning('Could not clean up expired checkout %s', session['id'], exc_info=True)
