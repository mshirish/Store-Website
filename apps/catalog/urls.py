from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.homepage, name='home'),
    path('search/', views.search_results, name='search'),
    path('search/suggestions/', views.search_suggestions, name='search_suggestions'),
    path('menu/cakes/', views.cake_list, name='cake_list'),
    path('menu/cakes/custom/', views.custom_cake_detail, name='custom_cake_detail'),
    path('menu/cakes/<int:pk>/', views.cake_detail, name='cake_detail'),
    path('menu/meat/', views.meat_list, name='meat_list'),
    path('menu/meat/<int:pk>/', views.meat_detail, name='meat_detail'),
    path('menu/grocery/', views.grocery_list, name='grocery_list'),
    path('menu/grocery/<int:pk>/', views.grocery_detail, name='grocery_detail'),
    path('menu/catering/', views.catering_menu, name='catering_menu'),
    path('menu/catering/<int:pk>/', views.catering_detail, name='catering_detail'),
]
