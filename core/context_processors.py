from .models import CurrencyRate
from django.db.utils import OperationalError, ProgrammingError


def crm_header(request):
    """Единый контекст шапки без каких-либо внешних сетевых запросов."""
    rates = {choice.value: None for choice in CurrencyRate.Pair}
    try:
        rates.update(dict(CurrencyRate.objects.values_list("pair", "rate")))
    except (OperationalError, ProgrammingError):
        # До применения первой миграции таблицы ещё может не быть.
        pass
    user = request.user
    authenticated = user.is_authenticated
    return {
        "currency_rates": rates,
        "nav": {
            "warehouse": authenticated and (user.is_superuser or user.has_perm("catalog.view_cd") or user.has_perm("catalog.view_tech")),
            "supplies": authenticated and (user.is_superuser or user.has_perm("supplies.view_supply")),
            "consignment": authenticated and (user.is_superuser or user.has_perm("consignment.view_cdconsignmentstock") or user.has_perm("consignment.view_techconsignmentstock")),
            "suppliers": authenticated and (user.is_superuser or user.has_perm("partners.view_supplier")),
            "users": authenticated and user.is_superuser,
            "admin": authenticated and (user.is_superuser or user.has_perm("core.access_admin_panel")),
        },
    }
