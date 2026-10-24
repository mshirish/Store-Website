"""
Reconcile hidden AWAITING_PAYMENT orders against Stripe.

  python manage.py reconcile_stripe_orders --dry-run   # report only
  python manage.py reconcile_stripe_orders             # apply
  python manage.py reconcile_stripe_orders --audit     # also list stray charges

For each AWAITING_PAYMENT order, every stored Checkout Session is looked up at
Stripe. A paid session confirms the order through confirm_paid_session() — the
same idempotent path as the success redirect and the webhook. Unpaid checkouts
older than --stale-minutes are discarded. Safe to run repeatedly (e.g. on a
schedule).

Sessions are matched only by the id stored on our Payment rows, never by
metadata.order_pk: several databases share one Stripe test account, so order
numbers collide across environments.
"""
import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.orders.models import Order, OrderStatus, Payment, PaymentStatus
from apps.orders.services import (
    abandon_pending_order,
    confirm_paid_session,
    retrieve_checkout_session,
    session_is_paid,
)


class Command(BaseCommand):
    help = 'Confirm paid / discard abandoned AWAITING_PAYMENT orders by checking Stripe.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report without changing anything.')
        parser.add_argument(
            '--stale-minutes', type=int, default=60,
            help='Unpaid checkouts older than this are discarded (default 60; sessions expire after 30).',
        )
        parser.add_argument(
            '--audit', action='store_true',
            help='Also list Stripe sessions that were paid but never applied to an order (refund candidates).',
        )

    def handle(self, *args, dry_run, stale_minutes, audit, **options):
        prefix = '[dry-run] ' if dry_run else ''
        cutoff = timezone.now() - datetime.timedelta(minutes=stale_minutes)
        confirmed = removed = waiting = errors = 0

        pending_orders = Order.objects.filter(status=OrderStatus.AWAITING_PAYMENT).order_by('pk')
        self.stdout.write(f'{pending_orders.count()} AWAITING_PAYMENT order(s) to check.')

        for order in pending_orders:
            refs = list(
                order.payments.filter(status=PaymentStatus.PENDING)
                .exclude(gateway_reference=None)
                .values_list('gateway_reference', flat=True)
            )
            try:
                paid = [s for s in (retrieve_checkout_session(r) for r in refs) if session_is_paid(s)]
            except Exception as exc:
                errors += 1
                self.stderr.write(f'  #{order.pk}: could not reach Stripe ({exc}); skipped.')
                continue

            if paid:
                if not dry_run:
                    confirm_paid_session(paid[0])
                    order.refresh_from_db(fields=['status'])
                confirmed += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  {prefix}#{order.pk}: PAID at Stripe ({paid[0]["id"][:24]}..., '
                    f'${paid[0]["amount_total"] / 100:.2f}) -> confirmed'
                ))
                if len(paid) > 1:
                    self.stdout.write(self.style.WARNING(
                        f'    #{order.pk}: {len(paid) - 1} additional paid session(s) — duplicate '
                        f'charge(s); refund from the Stripe dashboard (see --audit).'
                    ))
            elif order.created_at > cutoff:
                waiting += 1
                self.stdout.write(f'  #{order.pk}: unpaid, checkout started recently; left alone.')
            else:
                if not dry_run and not abandon_pending_order(order):
                    confirmed += 1
                    self.stdout.write(self.style.SUCCESS(f'  #{order.pk}: became paid during cleanup -> confirmed'))
                    continue
                removed += 1
                note = '' if refs else ' (no Stripe session recorded)'
                self.stdout.write(f'  {prefix}#{order.pk}: never paid{note} -> removed')

        self.stdout.write(
            f'\n{prefix}Confirmed {confirmed}, removed {removed}, left pending {waiting}, errors {errors}.'
        )

        if audit:
            self._audit()

    def _audit(self):
        """Sessions paid at Stripe whose Payment row was never captured."""
        self.stdout.write('\nAudit: paid Stripe sessions not applied to any order')
        stray = (
            Payment.objects.exclude(status=PaymentStatus.CAPTURED)
            .exclude(gateway_reference=None)
            .exclude(order__status=OrderStatus.AWAITING_PAYMENT)
            .select_related('order', 'order__customer')
            .order_by('order_id', 'pk')
        )
        found = 0
        for payment in stray:
            try:
                session = retrieve_checkout_session(payment.gateway_reference)
            except Exception as exc:
                self.stderr.write(f'  Payment {payment.pk}: could not reach Stripe ({exc})')
                continue
            if session_is_paid(session):
                found += 1
                self.stdout.write(self.style.WARNING(
                    f'  Order #{payment.order_id} ({payment.order.get_status_display()}, '
                    f'{payment.order.customer.email}): session {payment.gateway_reference[:24]}... '
                    f'paid ${session["amount_total"] / 100:.2f}, '
                    f'payment_intent {session.get("payment_intent")} -> refund candidate'
                ))
        self.stdout.write(f'{found} stray charge(s) found.' if found else 'None found.')
