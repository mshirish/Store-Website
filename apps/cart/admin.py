from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    can_delete = True
    readonly_fields = (
        'product', 'kind', 'product_name', 'unit_price_snapshot', 'quantity',
        'cake_size', 'cake_flavor_name', 'catering_option_label',
        'catering_pricing_mode', 'catering_variant_choice', 'created_at',
    )

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_item_count', 'updated_at')
    readonly_fields = ('user', 'created_at', 'updated_at')
    inlines = [CartItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')
