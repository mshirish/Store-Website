from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('checkout/pickup-window/', views.pickup_window_fragment, name='pickup_window'),
    path('checkout/place/', views.place_order, name='place'),
    path('orders/<int:pk>/confirmation/', views.order_confirmation, name='confirmation'),
    path('orders/<int:pk>/pay/', views.initiate_payment, name='initiate_payment'),
    path('orders/<int:pk>/payment-success/', views.payment_success, name='payment_success'),
    path('orders/<int:pk>/payment-cancel/', views.payment_cancel, name='payment_cancel'),
    path('webhook/stripe/', views.stripe_webhook, name='stripe_webhook'),
]
