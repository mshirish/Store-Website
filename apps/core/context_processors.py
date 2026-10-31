from .models import SiteConfiguration

DEFAULT_STORE_NAME = 'Our Store'


def site_config(request):
    config = SiteConfiguration.get()
    return {
        'site_config': config,
        # Falls back to the default so templates never render an empty name.
        'store_name': config.site_name.strip() or DEFAULT_STORE_NAME,
    }
