from django.urls import path

from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='cart'),
    path('add/<int:product_pk>/', views.add_to_cart, name='add'),
    path('update/<int:item_pk>/', views.update_cart_item, name='update'),
    path('remove/<int:item_pk>/', views.remove_cart_item, name='remove'),
]
