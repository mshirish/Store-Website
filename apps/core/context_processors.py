from .models import SiteConfiguration


def site_config(request):
    config = SiteConfiguration.get()
    return {
        'site_config': config,
        'store_name': config.store_name,
    }
