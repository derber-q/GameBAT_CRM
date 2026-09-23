from django.db.utils import OperationalError, ProgrammingError

from warehouse.models import Warehouse
from partners.models import SalesPlatform


def crm_header(request):
    """Единый контекст шапки без каких-либо внешних сетевых запросов."""
    warehouses = []
    sales_platforms = []
    try:
        warehouses = list(Warehouse.objects.values("id", "name"))
        sales_platforms = list(SalesPlatform.objects.values("id", "name"))
    except (OperationalError, ProgrammingError):
        # До применения первой миграции таблицы ещё может не быть.
        pass
    user = request.user
    authenticated = user.is_authenticated
    warehouse_global_access = authenticated and (
        user.is_superuser
        or user.has_perm("warehouse.view_global_stock")
        or user.has_perm("catalog.view_cd")
        or user.has_perm("catalog.view_tech")
    )
    warehouse_details_access = authenticated and (
        user.is_superuser
        or user.has_perm("warehouse.view_warehouse_stock")
        or user.has_perm("catalog.view_cd")
        or user.has_perm("catalog.view_tech")
    )
    transfers_access = authenticated and (
        user.is_superuser or user.has_perm("warehouse.view_transfers")
    )
    cash_access = authenticated and (
        user.is_superuser
        or user.has_perm("cash.view_cash_register")
        or user.has_perm("cash.view_cash_history")
        or user.has_perm("cash.view_safe")
    )
    return {
        "nav_warehouses": warehouses,
        "nav_sales_platforms": sales_platforms,
        "nav": {
            "warehouse": warehouse_global_access or warehouse_details_access,
            "warehouse_global": warehouse_global_access,
            "warehouse_details": warehouse_details_access,
            "transfers": transfers_access,
            "cash": cash_access,
            "creditors": authenticated and (
                user.is_superuser or user.has_perm("creditors.view_creditors")
            ),
            "nomenclature": authenticated and (
                user.is_superuser or user.has_perm("catalog.view_nomenclature")
            ),
            "supplies": authenticated and (user.is_superuser or user.has_perm("supplies.view_supply")),
            "consignment": authenticated and (user.is_superuser or user.has_perm("consignment.view_cdconsignmentstock") or user.has_perm("consignment.view_techconsignmentstock")),
            "suppliers": authenticated and (user.is_superuser or user.has_perm("partners.view_supplier")),
            "pricing": authenticated and (user.is_superuser or user.has_perm("pricing.view_pricing")),
            "price": authenticated and (user.is_superuser or user.has_perm("price.view_price_page")),
            "sales": authenticated and (
                user.is_superuser
                or user.has_perm("sales.view_sales")
                or user.has_perm("sales.create_sale")
                or cash_access
            ),
            "statistics": authenticated and (user.is_superuser or user.has_perm("sales.view_sales_statistics")),
            "orders": authenticated and (user.is_superuser or user.has_perm("orders.view_orders")),
            "integrations": authenticated and (
                user.is_superuser
                or user.has_perm("integrations.view_integrations")
                or user.has_perm("integrations.view_avito_integration")
            ),
            "integration_keys": authenticated and (
                user.is_superuser or user.has_perm("integrations.view_integrations")
            ),
            "integration_avito": authenticated and (
                user.is_superuser or user.has_perm("integrations.view_avito_integration")
            ),
            "users": authenticated and user.is_superuser,
            "stuf": authenticated and user.is_superuser,
            "admin": authenticated and (user.is_superuser or user.has_perm("core.access_admin_panel")),
        },
    }
