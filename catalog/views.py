from warehouse.views import global_stock


def warehouse(request):
    """Сохраняет прежний URL склада, показывая новую страницу общих остатков."""
    return global_stock(request)
