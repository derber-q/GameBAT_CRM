from django import template
from django.urls import reverse
from resource_storefront.modes import mode_for

register = template.Library()


@register.simple_tag(takes_context=True)
def storefront_url(context, name, *args):
    namespace = "retailer" if mode_for(context["request"]) == "retail" else "resource_storefront"
    return reverse(f"{namespace}:{name}", args=args)
