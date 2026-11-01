"""HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry."""
from warehouse.views import global_stock


def warehouse(request):
    """Сохраняет прежний URL склада, показывая новую страницу общих остатков."""
    return global_stock(request)
