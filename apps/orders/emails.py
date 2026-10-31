from email.utils import formataddr, parseaddr

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from apps.core.models import SiteConfiguration

from .models import PaymentStatus


def _from_email(store_name):
    # Sender name follows the store name; the address comes from DEFAULT_FROM_EMAIL.
    address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
    return formataddr((store_name, address)) if address else settings.DEFAULT_FROM_EMAIL


def _send(order, template_prefix, extra_context=None):
    store_name = SiteConfiguration.get().store_name
    context = {'order': order, 'store_name': store_name, **(extra_context or {})}
    subject = render_to_string(f'emails/{template_prefix}_subject.txt', context).strip()
    body = render_to_string(f'emails/{template_prefix}_body.txt', context)
    send_mail(subject, body, _from_email(store_name), [order.customer.email])


def send_order_confirmed_email(order):
    _send(order, 'order_confirmed')


def send_order_ready_email(order):
    _send(order, 'order_ready')


def send_order_cancelled_email(order):
    advance_captured = order.payments.filter(status=PaymentStatus.CAPTURED).exists()
    _send(order, 'order_cancelled', {'advance_captured': advance_captured})
