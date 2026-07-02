from django.contrib import admin

from .models import (
    Category,
    CakeFlavor,
    CakeOptionGroup,
    CakeOptionChoice,
    CakeProduct,
    CakeSizePrice,
    MeatProduct,
    GroceryProduct,
    CateringSection,
    CateringProduct,
    CateringOption,
    CateringVariant,
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'tax_rate', 'is_active')
    list_filter = ('kind', 'is_active')
    list_editable = ('is_active', 'tax_rate')
    search_fields = ('name',)
    fieldsets = (
        (None, {'fields': ('name', 'kind', 'description', 'cover_image', 'is_active', 'tax_rate')}),
    )


@admin.register(CakeFlavor)
class CakeFlavorAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'sort_order')
    list_editable = ('is_active', 'sort_order')
    ordering = ('sort_order', 'name')


# ── Cake ──────────────────────────────────────────────────────────────────────

class CakeSizePriceInline(admin.TabularInline):
    model = CakeSizePrice
    extra = 1
    min_num = 0
    fields = ('size', 'price')


@admin.register(CakeProduct)
class CakeProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_available', 'updated_at')
    list_filter = ('is_available', 'category')
    list_editable = ('is_available',)
    search_fields = ('name', 'description')
    inlines = [CakeSizePriceInline]
    fieldsets = (
        (None, {'fields': ('name', 'category', 'description', 'image', 'is_available')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')


# ── Meat ──────────────────────────────────────────────────────────────────────

@admin.register(MeatProduct)
class MeatProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price_per_lb', 'is_available', 'updated_at')
    list_filter = ('is_available', 'category')
    list_editable = ('is_available', 'price_per_lb')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {'fields': ('name', 'category', 'description', 'image', 'is_available', 'price_per_lb')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')


# ── Grocery ───────────────────────────────────────────────────────────────────

@admin.register(GroceryProduct)
class GroceryProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'unit_price', 'is_available', 'updated_at')
    list_filter = ('is_available', 'category')
    list_editable = ('is_available', 'unit_price')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {'fields': ('name', 'category', 'description', 'image', 'is_available', 'unit_price')}),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category')


# ── Catering ──────────────────────────────────────────────────────────────────

@admin.register(CateringSection)
class CateringSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'sort_order')
    list_editable = ('sort_order',)
    ordering = ('sort_order', 'name')


class CateringOptionInline(admin.TabularInline):
    model = CateringOption
    extra = 1
    fields = ('label', 'serves_note', 'price', 'pricing_mode', 'sort_order')


class CateringVariantInline(admin.TabularInline):
    model = CateringVariant
    extra = 1
    fields = ('label', 'sort_order')


@admin.register(CateringProduct)
class CateringProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'inquiry_only', 'is_available', 'updated_at')
    list_filter = ('section', 'inquiry_only', 'is_available')
    list_editable = ('is_available', 'inquiry_only')
    search_fields = ('name', 'description')
    inlines = [CateringOptionInline, CateringVariantInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'section', 'category', 'description', 'image', 'is_available', 'inquiry_only'),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('category', 'section')


# ── Custom Cake Options ───────────────────────────────────────────────────────

class CakeOptionChoiceInline(admin.TabularInline):
    model = CakeOptionChoice
    extra = 1
    fields = ('label', 'display_order', 'is_available')


@admin.register(CakeOptionGroup)
class CakeOptionGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_order', 'required')
    list_editable = ('display_order', 'required')
    ordering = ('display_order', 'name')
    inlines = [CakeOptionChoiceInline]
