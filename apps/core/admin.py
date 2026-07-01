from django.contrib import admin

from .models import SiteConfiguration, StoreHours, StoreClosure


@admin.register(SiteConfiguration)
class SiteConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Store', {'fields': ('site_name',)}),
        ('Payment', {
            'fields': ('advance_percentage',),
            'description': 'Percentage of the order total collected as an advance payment (e.g. 50 = 50%).',
        }),
    )

    def has_add_permission(self, request):
        return not SiteConfiguration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        # Redirect directly to the singleton instance for a cleaner UX.
        obj = SiteConfiguration.get()
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        return HttpResponseRedirect(
            reverse('admin:core_siteconfiguration_change', args=[obj.pk])
        )


@admin.register(StoreHours)
class StoreHoursAdmin(admin.ModelAdmin):
    list_display = ('weekday', 'open_time', 'close_time', 'is_closed')
    list_editable = ('open_time', 'close_time', 'is_closed')
    ordering = ('weekday',)

    def has_add_permission(self, request):
        # All 7 weekday rows are seeded; block adding duplicates via admin.
        from .models import WEEKDAY_CHOICES
        return StoreHours.objects.count() < len(WEEKDAY_CHOICES)


@admin.register(StoreClosure)
class StoreClosureAdmin(admin.ModelAdmin):
    list_display = ('date', 'is_full_closure', 'special_open_time', 'special_close_time', 'note')
    ordering = ('date',)
    search_fields = ('note',)
    date_hierarchy = 'date'
