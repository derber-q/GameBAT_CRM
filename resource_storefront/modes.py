"""Режим выбирает серверный URL namespace; параметры браузера его не меняют."""
def mode_for(request):
    return "retail" if getattr(request.resolver_match, "namespace", "") == "retailer" else "wholesale"


def session_key(request, key):
    return key.replace("resource_", "retailer_", 1) if mode_for(request) == "retail" else key


def storefront_url(request, name, **kwargs):
    from django.urls import reverse
    namespace = "retailer" if mode_for(request) == "retail" else "resource_storefront"
    return reverse(f"{namespace}:{name}", **kwargs)


def config_for(request):
    from .models import RetailSettings, StorefrontSettings
    model = RetailSettings if mode_for(request) == "retail" else StorefrontSettings
    return model.objects.filter(pk=1).first()
