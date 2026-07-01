from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_order_confirmed_email(order):
    subject = render_to_string(
        'emails/order_confirmed_subject.txt', {'order': order}
    ).strip()
    body = render_to_string('emails/order_confirmed_body.txt', {'order': order})
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.customer.email])


def send_order_ready_email(order):
    subject = render_to_string(
        'emails/order_ready_subject.txt', {'order': order}
    ).strip()
    body = render_to_string('emails/order_ready_body.txt', {'order': order})
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.customer.email])
