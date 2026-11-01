# Документация ReSOURCE

## Актуальная техническая база

- [Полный технический навигатор](technical/README.md).
- [Архитектура и правила учёта](architecture.md).
- [Эксплуатация и восстановление](operations.md).
- [Карта сопровождения](development.md).
- [Пользовательские сценарии](user_guide.md).
- [Подготовка и глобальная проверка 31.10.2026](maintenance_20261031.md).

## Основные тематические контракты

- Заказы Avito в расширении: [создание продажи, связь и отправительные стикеры](avito_browser_orders.md).

- Рейсы: [пустой рейс](empty_trips.md), [изменения количества](trip_quantity_reductions.md), [AED-цена](trip_supplier_prices.md), [дополнительные партии](crm_complex_20261025.md), [действующее прибытие/финализация](trip_arrival_costs.md).
- Закупки: [выбор поставщика](procurement_supplier_selection.md), [группировка Excel](procurement_excel_grouping.md), [постоплата](procurement_postpayment.md), [закупка на склад](stock_procurement_orders.md).
- Приход/продажа: [ожидающий приход](pending_supply_edit.md), [оплата](sale_payments.md), [системные позиции](system_operations.md), [накладная](sale_invoice_excel.md), [партнёры/долги](partners.md).
- Реализация: [партийные действия](consignment_row_actions.md), [Excel-отчёт](consignment_excel.md).
- Интеграции: [Avito Check](avito_check.md), [необходимые действия](avito_required_actions.md), [Яндекс FBS](yandex_market.md), [FBS-формула](fbs_pricing.md), [сборка/печать](market_scan_fulfillment.md), [внимание сотрудника](market_staff_alerts.md).
- Каталог/склад: [новинки/поставщики](catalog_procurement_controls.md), [порядок товаров](product_display_order.md), [ревизия](warehouse_revision.md).
- Витрины: [оптовая](resource_wholesale.md), [розничная](resource_retail.md), [каталог](resource_catalog.md), [мобильная оболочка](resource_mobile.md).

## Исторические материалы

`verification.md`, `trip_arrival_report_20261026.md`, `yandex_market_report.md`, датированные итоги внутри остальных документов фиксируют результат своей проверки. Это не утверждение об актуальном полном suite.

`trip_order_operations.md` описывает ранний сценарий отдельных операций; при конфликте с ним действует `trip_arrival_costs.md` и текущий код. Старые `CHECKPOINT_*.md` и завершённый `tasks/plan.md` удалены как устаревшие инструкции отката; миграции и полезные описания правил сохранены.
