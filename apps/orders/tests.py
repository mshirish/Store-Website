import datetime
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.catalog.models import Category, CategoryKind, Product
from .models import Order, OrderStatus, Payment, PaymentStatus
from .services import complete_order_with_balance

SESSION_ID = 'cs_test_paid_123'


def paid_session(session_id=SESSION_ID):
    return {'id': session_id, 'payment_status': 'paid', 'status': 'complete',
            'payment_intent': 'pi_test_1', 'amount_total': 1000}


def unpaid_session(session_id=SESSION_ID):
    return {'id': session_id, 'payment_status': 'unpaid', 'status': 'open',
            'payment_intent': None, 'amount_total': 1000}


class InvalidRequestError(Exception):
    pass


def fake_stripe():
    stripe = mock.MagicMock()
    stripe.error.InvalidRequestError = InvalidRequestError
    return stripe


class OrderFlowTestBase(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buyer@example.com', 'pw')
        self.staff = get_user_model().objects.create_user('staff@example.com', 'pw', is_staff=True)
        self.client.force_login(self.user)
        category = Category.objects.create(name='Grocery', kind=CategoryKind.GROCERY)
        self.product = Product.objects.create(name='Milk', category=category)
        self.cart = Cart.objects.create(user=self.user)
        self.cart_item = self._add_cart_item()
        self.order = Order.objects.create(
            customer=self.user,
            pickup_date=datetime.date.today() + datetime.timedelta(days=2),
            order_total=Decimal('20.00'),
            advance_amount=Decimal('10.00'),
            balance_amount=Decimal('10.00'),
        )
        self.payment = Payment.objects.create(
            order=self.order, amount=Decimal('10.00'), gateway_reference=SESSION_ID,
        )

    def _add_cart_item(self):
        return CartItem.objects.create(
            cart=self.cart, product=self.product, kind=CategoryKind.GROCERY,
            product_name='Milk', unit_price_snapshot=Decimal('20.00'), quantity=1,
        )

    def return_from_stripe(self, session):
        with mock.patch('apps.orders.views.retrieve_checkout_session', return_value=session), \
             self.captureOnCommitCallbacks(execute=True):
            return self.client.get(
                reverse('orders:payment_success', kwargs={'pk': self.order.pk}),
                {'session_id': session['id']},
            )

    def send_webhook(self, session, event_type='checkout.session.completed'):
        event = {'type': event_type, 'data': {'object': session}}
        with mock.patch('stripe.Webhook.construct_event', return_value=event), \
             self.captureOnCommitCallbacks(execute=True):
            return self.client.post(reverse('orders:stripe_webhook'), b'{}', content_type='application/json')


class RedirectConfirmationTests(OrderFlowTestBase):
    def test_redirect_confirms_order_without_webhook(self):
        response = self.return_from_stripe(paid_session())

        self.assertRedirects(
            response, reverse('orders:order_detail', kwargs={'pk': self.order.pk}) + '?just_paid=1',
            fetch_redirect_response=False,
        )
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.assertEqual(self.payment.status, PaymentStatus.CAPTURED)
        self.assertEqual(self.payment.stripe_payment_intent_id, 'pi_test_1')
        self.assertEqual(len(mail.outbox), 1)
        self.assertFalse(CartItem.objects.filter(pk=self.cart_item.pk).exists())

    def test_redirect_then_webhook_confirms_once(self):
        self.return_from_stripe(paid_session())
        self.assertEqual(self.send_webhook(paid_session()).status_code, 200)
        self.return_from_stripe(paid_session())

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(Payment.objects.filter(status=PaymentStatus.CAPTURED).count(), 1)

    def test_webhook_then_redirect_confirms_once(self):
        self.send_webhook(paid_session())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.return_from_stripe(paid_session())

        self.assertEqual(len(mail.outbox), 1)

    def test_unpaid_session_does_not_confirm_and_stays_hidden(self):
        response = self.return_from_stripe(unpaid_session())

        self.assertContains(response, 'Confirming your payment')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.AWAITING_PAYMENT)
        self.assertEqual(len(mail.outbox), 0)

    def test_foreign_session_id_is_ignored(self):
        with mock.patch('apps.orders.views.retrieve_checkout_session') as retrieve:
            self.client.get(
                reverse('orders:payment_success', kwargs={'pk': self.order.pk}),
                {'session_id': 'cs_test_someone_else'},
            )
        retrieve.assert_not_called()
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.AWAITING_PAYMENT)

    def test_cart_items_added_after_checkout_survive_confirmation(self):
        later_item = self._add_cart_item()
        CartItem.objects.filter(pk=later_item.pk).update(
            created_at=timezone.now() + datetime.timedelta(minutes=5)
        )
        self.return_from_stripe(paid_session())
        self.assertTrue(CartItem.objects.filter(pk=later_item.pk).exists())


class CustomerVisibilityTests(OrderFlowTestBase):
    def test_unpaid_order_is_invisible(self):
        response = self.client.get(reverse('orders:order_list'))
        self.assertNotContains(response, f'Order #{self.order.pk}')
        detail = self.client.get(reverse('orders:order_detail', kwargs={'pk': self.order.pk}))
        self.assertEqual(detail.status_code, 404)

    def test_confirmed_order_shows_active_with_no_pay_button(self):
        self.return_from_stripe(paid_session())
        listing = self.client.get(reverse('orders:order_list'))
        self.assertContains(listing, 'Active')
        detail = self.client.get(reverse('orders:order_detail', kwargs={'pk': self.order.pk}))
        self.assertContains(detail, 'Balance due at pickup')
        self.assertContains(detail, 'Cancel order')
        self.assertNotContains(detail, 'Awaiting Payment')
        self.assertNotContains(detail, 'Complete payment')

    def test_internal_statuses_show_as_active(self):
        for status in (OrderStatus.PREPARING, OrderStatus.READY):
            Order.objects.filter(pk=self.order.pk).update(status=status)
            detail = self.client.get(reverse('orders:order_detail', kwargs={'pk': self.order.pk}))
            self.assertContains(detail, '>Active<')

    def test_customer_can_cancel_active_order(self):
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.PREPARING)
        self.client.post(reverse('orders:cancel_order', kwargs={'pk': self.order.pk}))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CANCELLED)


class AbandonedCheckoutTests(OrderFlowTestBase):
    def test_cancel_return_discards_order_and_keeps_cart(self):
        stripe = fake_stripe()
        with mock.patch('apps.orders.services._stripe', return_value=stripe), \
             mock.patch('apps.orders.services.retrieve_checkout_session', return_value=unpaid_session()):
            response = self.client.get(reverse('orders:payment_cancel', kwargs={'pk': self.order.pk}))

        self.assertRedirects(response, reverse('orders:checkout'), fetch_redirect_response=False)
        stripe.checkout.Session.expire.assert_called_once_with(SESSION_ID)
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertTrue(CartItem.objects.filter(pk=self.cart_item.pk).exists())

    def test_cancel_return_confirms_if_actually_paid(self):
        with mock.patch('apps.orders.services._stripe', return_value=fake_stripe()), \
             mock.patch('apps.orders.services.retrieve_checkout_session', return_value=paid_session()):
            self.client.get(reverse('orders:payment_cancel', kwargs={'pk': self.order.pk}))
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)


class ReconcileCommandTests(OrderFlowTestBase):
    def run_command(self, session, *args):
        out = StringIO()
        with mock.patch('apps.orders.management.commands.reconcile_stripe_orders.retrieve_checkout_session',
                        return_value=session), \
             mock.patch('apps.orders.services.retrieve_checkout_session', return_value=session), \
             mock.patch('apps.orders.services._stripe', return_value=fake_stripe()), \
             self.captureOnCommitCallbacks(execute=True):
            call_command('reconcile_stripe_orders', *args, stdout=out, stderr=StringIO())
        return out.getvalue()

    def test_paid_order_is_confirmed(self):
        output = self.run_command(paid_session())
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.CONFIRMED)
        self.assertIn('Confirmed 1', output)
        self.assertEqual(len(mail.outbox), 1)
        # Second run is a no-op.
        self.run_command(paid_session())
        self.assertEqual(len(mail.outbox), 1)

    def test_dry_run_changes_nothing(self):
        self.run_command(paid_session(), '--dry-run')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, OrderStatus.AWAITING_PAYMENT)

    def test_stale_unpaid_order_is_removed(self):
        Order.objects.filter(pk=self.order.pk).update(created_at=timezone.now() - datetime.timedelta(hours=3))
        self.run_command(unpaid_session())
        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())

    def test_recent_unpaid_order_is_left_alone(self):
        self.run_command(unpaid_session())
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())


class CompleteWithBalanceTests(OrderFlowTestBase):
    def test_completes_once(self):
        Order.objects.filter(pk=self.order.pk).update(status=OrderStatus.READY)
        order, changed = complete_order_with_balance(self.order.pk, self.staff)
        self.assertTrue(changed)
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertIsNotNone(order.balance_paid_at)
        self.assertIsNotNone(order.picked_up_at)
        self.assertEqual(order.balance_paid_by, self.staff)

        first_paid_at = order.balance_paid_at
        order, changed = complete_order_with_balance(self.order.pk, self.staff)
        self.assertFalse(changed)
        self.assertEqual(order.balance_paid_at, first_paid_at)

    def test_rejects_unpaid_order(self):
        with self.assertRaises(ValueError):
            complete_order_with_balance(self.order.pk, self.staff)
