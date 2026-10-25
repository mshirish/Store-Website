from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.catalog.models import Category, CategoryKind, Product
from .models import Cart, CartItem
from .utils import compute_line_total


class UpdateCartItemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('buyer@example.com', 'pw')
        self.client.force_login(self.user)
        self.cart = Cart.objects.create(user=self.user)
        self.grocery = self._item(CategoryKind.GROCERY, '48.00', '4')
        self.meat = self._item(CategoryKind.MEAT, '6.99', '2.000')

    def _item(self, kind, price, qty):
        category, _ = Category.objects.get_or_create(name=kind, kind=kind)
        product = Product.objects.create(name=f'{kind} product', category=category)
        return CartItem.objects.create(
            cart=self.cart, product=product, kind=kind, product_name=product.name,
            unit_price_snapshot=Decimal(price), quantity=Decimal(qty),
        )

    def post(self, item, **data):
        return self.client.post(reverse('cart:update', args=[item.pk]), data, HTTP_HX_REQUEST='true')

    def assert_saved(self, item, expected):
        item.refresh_from_db()
        self.assertEqual(item.quantity, Decimal(expected))

    def test_quantity_change_returns_server_computed_line_total_and_totals(self):
        response = self.post(self.grocery, quantity='1')
        html = response.content.decode()

        self.assert_saved(self.grocery, '1')
        line_total = compute_line_total(Decimal('48.00'), Decimal(1))
        self.assertIn(f'<span id="line-total-{self.grocery.pk}" hx-swap-oob="true">${line_total}</span>', html)
        self.assertIn(f'${self.cart.get_subtotal()}', html)
        self.assertIn('Subtotal (2 items)', html)
        self.assertIn('id="cart-totals" hx-swap-oob="true"', html)
        # No table-row markup (breaks htmx parsing) and no input swap for a valid value.
        self.assertNotIn('<tr', html)
        self.assertNotIn('qty-field-', html)

    def test_weight_change_is_rounded_by_server(self):
        html = self.post(self.meat, weight='1.2345').content.decode()
        self.assert_saved(self.meat, '1.235')
        self.assertIn(f'${compute_line_total(Decimal("6.99"), Decimal("1.235"))}', html)
        self.assertIn(f'id="qty-field-{self.meat.pk}" hx-swap-oob="true"', html)  # shows 1.235

    def test_zero_and_negative_clamp_to_minimum(self):
        self.post(self.grocery, quantity='0')
        self.assert_saved(self.grocery, '1')
        html = self.post(self.meat, weight='-3').content.decode()
        self.assert_saved(self.meat, '0.001')
        self.assertIn('value="0.001"', html)

    def test_invalid_input_keeps_saved_value_and_resets_field(self):
        for bad in ('', 'abc', '2.5', 'NaN', 'Infinity', '99999999999'):
            with self.subTest(bad=bad):
                response = self.post(self.grocery, quantity=bad)
                self.assertEqual(response.status_code, 200)
                self.assert_saved(self.grocery, '4')
                self.assertIn('value="4"', response.content.decode())

    def test_cannot_update_someone_elses_item(self):
        other = get_user_model().objects.create_user('other@example.com', 'pw')
        self.client.force_login(other)
        self.assertEqual(self.post(self.grocery, quantity='2').status_code, 404)
        self.assert_saved(self.grocery, '4')

    def test_cart_page_renders_live_inputs(self):
        html = self.client.get(reverse('cart:cart')).content.decode()
        self.assertIn(f'id="line-total-{self.grocery.pk}"', html)
        self.assertIn('hx-swap="none"', html)
        self.assertIn('input[this.checkValidity()] changed delay:500ms, change changed', html)
