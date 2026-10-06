from decimal import Decimal, InvalidOperation
from django import template
from django.utils.html import format_html

register = template.Library()


@register.filter
def hero_heading(value):
    title = value or "Игровая индустрия. Ваш следующий уровень."
    phrase = "Ваш следующий уровень."
    if title.endswith(phrase):
        return format_html("{}<span>{}</span>", title[:-len(phrase)].strip(), phrase)
    return title


@register.filter
def rubles(value):
    """Разряды разделены неразрывным пробелом; значимые копейки сохраняются."""
    try:
        amount = Decimal(str(value))
        if not amount.is_finite():
            return "—"
        places = 0 if amount == amount.to_integral_value() else 2
        return format(amount, f",.{places}f").replace(",", "\u00a0").replace(".", ",")
    except (InvalidOperation, TypeError, ValueError):
        return "—"
