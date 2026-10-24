"""
Order lifecycle operations shared by views, the Stripe webhook, the admin and
management commands. Every function here is idempotent.
"""
import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import ACTIVE_STATUSES, Order, OrderStatus, Payment, PaymentStatus

logger = logging.getLogger(__name__)


def _stripe():
    import stripe as stripe_lib
    stripe_lib.api_key = settings.STRIPE_SECRET_KEY
    return stripe_lib


def retrieve_checkout_session(session_id):
    return _stripe().checkout.Session.retrieve(session_id)


def session_is_paid(session):
    return session.get('payment_status') == 'paid'


# ── Advance payment confirmation ──────────────────────────────────────────────

def confirm_paid_session(session):
    """
    Confirm the order behind a Stripe Checkout Session if the session is paid.

    The single confirmation path for the success redirect, the webhook and the
    reconcile command. Keyed on the session id (Payment.gateway_reference):
    the Payment and Order rows are locked, so whichever caller arrives first
    confirms the order and queues the email; later callers are no-ops.

    Returns True only for the call that actually confirmed the order.
    """
    from apps.cart.models import CartItem
    from apps.orders.emails import send_order_confirmed_email

    session_id = session['id']
    if not session_is_paid(session):
        return False

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(gateway_reference=session_id)
        except Payment.DoesNotExist:
            logger.error(
                'Stripe session %s is paid but has no matching Payment row — a charge may '
                'have been captured with no local record. Check the Stripe dashboard and '
                'reconcile manually.',
                session_id,
            )
            return False

        if payment.status == PaymentStatus.CAPTURED:
            return False  # idempotency guard

        # Lock the order too, so two different paid sessions for the same order
        # cannot both confirm it.
        order = Order.objects.select_for_update().get(pk=payment.order_id)
        if order.status != OrderStatus.AWAITING_PAYMENT:
            logger.warning(
                'Stripe session %s is paid but order #%d is already %s — this charge was '
                'not applied. Refund it from the Stripe dashboard.',
                session_id, order.pk, order.status,
            )
            return False

        now = timezone.now()
        payment.status = PaymentStatus.CAPTURED
        payment.captured_at = now
        payment.stripe_payment_intent_id = session.get('payment_intent')
        payment.save(update_fields=['status', 'captured_at', 'stripe_payment_intent_id'])

        order.status = OrderStatus.CONFIRMED
        order.save(update_fields=['status', 'updated_at'])

        # The cart is kept through checkout so an abandoned payment loses nothing;
        # it is emptied only once the order is real. Items added after the order
        # was placed belong to a future order and are left alone.
        CartItem.objects.filter(
            cart__user_id=order.customer_id, created_at__lte=order.created_at
        ).delete()

        def _send_email():
            try:
                send_order_confirmed_email(order)
            except Exception:
                logger.exception('Failed to send confirmation email for order #%d', order.pk)

        transaction.on_commit(_send_email)

    return True


def verify_and_confirm_order(order):
    """
    Ask Stripe about each of the order's pending sessions and confirm the order
    if one of them is paid. Returns True if the order is confirmed (now or before).
    """
    if order.status != OrderStatus.AWAITING_PAYMENT:
        return order.status in ACTIVE_STATUSES or order.status == OrderStatus.COMPLETED
    for payment in order.payments.filter(status=PaymentStatus.PENDING).exclude(gateway_reference=None):
        session = retrieve_checkout_session(payment.gateway_reference)
        if session_is_paid(session):
            confirm_paid_session(session)
            break
    order.refresh_from_db(fields=['status'])
    return order.status != OrderStatus.AWAITING_PAYMENT


# ── Abandoned checkouts ───────────────────────────────────────────────────────

def abandon_pending_order(order):
    """
    Discard a checkout that never got paid: expire its open Stripe sessions and
    delete the hidden AWAITING_PAYMENT order. If Stripe reports that one of its
    sessions was in fact paid, the order is confirmed instead.

    Returns True if the order was deleted, False if it turned out to be paid
    (or is no longer pending).
    """
    stripe_lib = _stripe()
    if verify_and_confirm_order(order):
        return False

    for payment in order.payments.filter(status=PaymentStatus.PENDING).exclude(gateway_reference=None):
        try:
            stripe_lib.checkout.Session.expire(payment.gateway_reference)
        except stripe_lib.error.InvalidRequestError:
            # Already expired or complete. If it completed between our check and
            # now, confirm rather than delete.
            if verify_and_confirm_order(order):
                return False

    with transaction.atomic():
        locked = Order.objects.select_for_update().filter(
            pk=order.pk, status=OrderStatus.AWAITING_PAYMENT
        ).first()
        if locked is None:
            return False
        if locked.payments.filter(status=PaymentStatus.CAPTURED).exists():
            return False
        # Payment is PROTECT; drop the never-captured rows first.
        locked.payments.all().delete()
        locked.delete()
    return True


# ── Pickup ────────────────────────────────────────────────────────────────────

def complete_order_with_balance(order_pk, staff_user):
    """
    Staff action at the counter: balance received in person, order picked up,
    order completed — all in one transaction. Re-running it on a completed
    order changes nothing.

    Returns (order, changed). Raises ValueError if the order is not in a state
    that can be completed (unpaid, cancelled).
    """
    with transaction.atomic():
        order = Order.objects.select_for_update().get(pk=order_pk)
        if order.status == OrderStatus.COMPLETED:
            return order, False
        if order.status not in ACTIVE_STATUSES:
            raise ValueError(
                f'Order #{order.pk} cannot be completed from status '
                f'"{order.get_status_display()}".'
            )
        now = timezone.now()
        update_fields = ['status', 'picked_up_at', 'updated_at']
        if not order.balance_paid_at:
            order.balance_paid_at = now
            order.balance_paid_by = staff_user
            update_fields += ['balance_paid_at', 'balance_paid_by']
        order.picked_up_at = order.picked_up_at or now
        order.status = OrderStatus.COMPLETED
        order.save(update_fields=update_fields)
    return order, True
