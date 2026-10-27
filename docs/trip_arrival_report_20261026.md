# Отчёт: общие фактические затраты рейса, 26.10.2026

> Обновление 26.10.2026: по следующему поручению пользователя поля продажных цен убраны из финализации рейса. Перед приёмкой возвращена штатная проверка цен по средней себестоимости складского остатка. Нижеследующие пункты о первоначальных отложенных предложениях цен описывают прежнее состояние. Действующие правила — в `trip_arrival_costs.md`.

Основание — задание «Полная переработка логики прибытия рейса» из приложения пользователя. Текущий порядок работы: [trip_arrival_costs.md](trip_arrival_costs.md). Существовавшие до задачи изменения других подсистем сохранены; коммит и push не выполнялись.

## Ответы на 39 пунктов отчёта

1. Полный список файлов этой задачи приведён ниже; он отделён от прежнего большого рабочего diff.
2. Миграции: `orders.0011_trip_arrival_costs`, `sales.0033_trip_cost_sources`, `supplies.0011_trip_cost_sources`.
3. Состояние рейса хранится в `TripArrival`: параметры → прибытие → подготовка отдельных документов → общая финализация → независимое проведение документов. Ревизия защищает открытые формы.
4. Фактическая доставка и оба курса — поля `TripArrival.actual_delivery`, `usdt_aed`, `usdt_rub`; время и сотрудник каждой фиксации сохраняются.
5. Закупка единицы: `AED / USDT_AED × USDT_RUB`, `Decimal`, округление до копеек без округлённого промежуточного курса.
6. Предварительные тарифы берутся из снимков закупки. CD используют фиксированную доставку RUB/шт.; Tech сохраняют различия веса/тарифа. Исторический курс предварительного расчёта не заменяется новым курсом.
7. Вес распределения источника — предварительная доставка единицы × фактическое количество. Фактическая доставка распределяется пропорционально этим весам.
8. Метод наибольших остатков распределяет все копейки; итог равен введённой доставке. Воспроизводимый порядок устраняет случайные различия округления.
9. До прибытия проверяется положительный вес каждого товара. Недостающие веса вводятся общей формой через существующий сервис карточек.
10. Установка флага создаёт снимки. Снять его можно до первой операции нового прибытия; после любой такой операции, включая отменённую, нельзя.
11. Защиты сервисов/моделей блокируют курсы, доставку и первоначальные закупочные источники; после финализации блокируются фактические количества и итоговые затраты.
12. Используются обычные Sale/Supply и `TripOrderOperation`. Каждый заказ получает самостоятельный документ; повтор запроса идемпотентен.
13. Формы документов читают курсы из прибытия, отдельных валютных полей больше нет. Старые сессионные черновики отклоняются.
14. До финализации разрешено уменьшать фактическое количество конкретного источника. Превышение первоначального, устаревшая ревизия и изменение чужого источника отклоняются.
15. `TripCostRow.original_quantity` и исходный заказ сохраняются. Фактическое значение хранится отдельно.
16. Нулевые источники исключаются из затрат. Полностью отсутствующий заказ отмечается проверенным без пустого документа. Существующий обнулённый документ отменяется штатно.
17. После уменьшения заново распределяется вся фактическая доставка; все незавершённые документы получают согласованные затраты одной транзакцией.
18. В смешанной Sale признак источника задан каждой строке. Складские дополнения списывают обычный остаток и имеют независимую себестоимость; прямые строки не двигают склад. Совпадение Product не объединяет источники.
19. Приход создаётся со статусом `trip_finalization` — «Ждёт финализации рейса». Он исключён из складского проведения и исторического пересчёта до реальной приёмки.
20. Готовность требует по каждому заказу действующего незавершённого документа либо подтверждённого полностью нулевого состава. Непроверенные заказы блокируют финализацию.
21. Общая форма показывает все фактически поступившие закупочные доли, тип назначения и цены; разрешает перенос стоимости между любыми источниками без изменения общей суммы.
22. Переиспользованы `FinalizationRow`, парсинг и контроль итогов, штраф/излишек, автораспределение, общая панель инструментов, `supply-finalization.js` и точное распределение обычной приёмки.
23. Сумма строк обязана точно совпасть с `control_total`. Несбалансированная форма не сохраняется; подтверждение включает контроль актуальной ревизии и исходных значений.
24. Общая финализация обновляет снимки SaleItem и ожидающих SupplyItem, затем фиксирует итог рейса. Копеечные группы обеспечивают точные суммы при неделимом количестве.
25. Базовые покупательские цены остаются снимками заказа. Скидки сохраняются отдельно и не исчезают после перераспределения. Складские дополнения используют обычные цены и правила.
26. Предложения опта/Avito сохраняются в прибытии, применяются при приёмке Supply через штатные сервисы цен. Проверяются права, единое значение для товара и отсутствие более нового решения.
27. Поставщик, allocation и ценовая часть идентифицируют отдельный `TripCostRow`. Несколько Supply одного товара независимы; при каждом проведении учитывается текущий физический остаток.
28. Backend не разрешает раннее завершение Sale и проведение Supply; индивидуальная финализация прихода рейса запрещена. Проверки присутствуют не только в шаблонах.
29. Отмена до финализации сохраняет историю, снимает действующую операцию; для готовности снова нужен документ или подтверждённый нулевой состав.
30. Отмена после финализации использует обычные деньги/склад и не меняет контрольный итог рейса. Прямая часть продажи на склад не возвращается.
31. Повторное создание берёт окончательные количества и затраты `TripCostRow`, не вводит курсы и не распределяет доставку заново.
32. Trip-доставка уже включена в итог строк Supply; повторный transport не добавляется. Независимые расходы при приёмке указываются отдельно и не изменяют контрольный итог рейса.
33. Блокировка рейса, проверка ревизии, транзакции и повтор при SQLite lock защищают атомарность. Ошибка сохранения одной строки откатывает остальные документы и состояние финализации.
34. Добавлены расчётные, сервисные, HTTP, конкурентные, миграционно-совместимые и браузерные проверки; карта 38 сценариев ниже.
35. Полный первый прогон: 1313 тестов, OK, 497,645 с. Заключительный полный прогон: 1314 тестов, OK, 511,305 с. После уточнения снятия прибытия при отменённой старой истории отдельно выполнены все 50 новых расчётных/сервисных/HTTP/конкурентных проверок на свежей БД: OK, 10,768 с.
36. Обычная финализация и обычное весовое распределение включены в целевые и полные регрессионные проверки; отдельный браузерный сценарий использует новые общие компоненты.
37. `manage.py check` и проверка отсутствия пропущенных миграций выполнены; финальная проверка рабочей схемы указана ниже.
38. Ограничения архитектуры: себестоимость единицы хранится в копейках, поэтому нужны максимум две группы; глобальная цена одна на Product, поэтому противоречащие предложения запрещены; SQLite требует сериализации/повтора конкурентной записи; активные исторические документы не конвертируются автоматически.
39. Неохваченных обязательных ветвей задания не выявлено. Проверки выполняются с подменёнными внешними API; реальная Avito-синхронизация не запускалась. Старый рейс с уже выполненными заказами не переоформляется новым процессом автоматически. Реальные финансовые документы ради проверки не создавались.

## Карта 38 сценариев задания

| № задания | Проверка |
| --- | --- |
| 1 | `test_arrival_math.test_cross_conversion` |
| 2 | `test_category_tariffs_determine_shares` |
| 3 | `test_reduction_keeps_full_actual_delivery`, `test_quantity_reduction_updates_every_pending_document_atomically` |
| 4 | `test_cd_uses_fixed_original_delivery_despite_catalog_mass` |
| 5 | `test_different_tech_tariffs_are_preserved_instead_of_uniform_per_gram` |
| 6 | `test_missing_weight_rejects_arrival_without_partial_data` |
| 7 | `test_arrival_can_be_unset_before_documents`, заморозка источников |
| 8–10 | HTTP полного цикла, `test_separate_pending_documents_do_not_change_stock_or_catalog_cost`, `test_two_stock_orders_stay_separate_and_post_against_current_cost` |
| 11–13 | `test_same_product_trip_and_warehouse_have_independent_stock_and_cost` и отмена смешанной продажи |
| 14–16 | `test_reduction_preserves_original_quantity_and_whole_delivery`, `test_customer_completely_missing_does_not_create_empty_sale_or_block_finalization`, `test_over_order_and_stale_changes_are_rejected` |
| 17 | `test_supplier_parties_are_not_merged_by_product_id` |
| 18–20 | `test_readiness_requires_each_order_document`, `test_only_customer_documents_are_sufficient`, два самостоятельных складских заказа |
| 21 | `test_cost_can_move_between_customer_and_warehouse_without_changing_total` |
| 22 | `test_authoritative_distribution_tools_work_with_procurement_cohort_keys` |
| 23–25 | `test_finalization_preserves_total_and_defers_stock_and_prices`, HTTP цен, `test_conflicting_proposals_for_one_global_product_are_rejected` |
| 26–27 | `test_premature_completion_is_rejected_on_backend`, итоговая финализация без проведения |
| 28 | `test_completed_sale_statistics_use_final_trip_cost` |
| 29–31 | `test_cancel_and_recreate_after_finalization_reuses_fixed_costs`, `test_supply_cancel_and_recreate_after_finalization_keeps_whole_trip_fixed` |
| 32 | два прихода одного товара; `test_older_price_decision_cannot_override_newer_finalized_trip` |
| 33 | `test_exact_cent_delivery_is_split_without_lost_costs`, `test_largest_remainders_are_exact_and_deterministic` |
| 34 | `test_parallel_reductions_cannot_silently_overwrite_global_distribution` |
| 35 | `test_finalization_rolls_back_all_documents_if_one_update_fails` |
| 36 | `test_independent_supply_expenses_do_not_repeat_trip_delivery` и повторное проведение |
| 37 | существующие `supplies.test_finalization`, `test_weight_transport` и полный suite |
| 38 | тест совместимости схемы, старые fulfilment-сценарии, сравнение старых столбцов 130 таблиц на мигрированной копии |

Дополнительно проверены права изменения цен, неизменность источника через `save()`, rollback при нехватке складского дополнения, сохранение скидки при перерасчёте и отменённая история прежних операций.

## Браузер и данные

Браузерный сценарий `orders.arrival_browser_checks` прошёл: предпросмотр, создание документов, общая финализация, отдельная приёмка с независимыми расходами, настольная и мобильная формы. Снимки находятся локально в `outputs/trip_arrival_20261026/browser/`. Они не включаются в Git.

Миграции проверены на двух последовательных согласованных копиях рабочей SQLite. На первоначальной копии сохранились старые значения 130 таблиц / 140858 строк. Непосредственно перед обновлением остановлен только точный процесс сайта и создана новая резервная копия `backups/before_trip_arrival_20261026_182213.sqlite3`: 130 таблиц / 140844 старых строк. На ней снова проверены миграции, затем те же три миграции успешно применены к рабочей БД. Сравнение всех прежних столбцов рабочей БД подтвердило отсутствие изменений старых данных. `integrity_check=ok`, нарушений внешних ключей нет. Отменённые три старые операции сохранены. Проверки `verify_inventory` и `verify_cash` на копии и рабочей БД подтвердили согласованность; `check`, `migrate --check`, `makemigrations --check --dry-run` успешны.

Сайт перезапущен через `start_localhost.ps1 -SiteOnly -NoBrowser`, отвечает HTTP 200 на `127.0.0.1:8000`; локальная сетевая ссылка — `http://192.168.0.131:8000/`. Рабочая страница существующего рейса отрендерена с новым блоком прибытия и общими курсами без создания документов. Существующие интеграционные процессы не запускались и не останавливались.

Все 24 файла `test_*.cjs` завершились успешно. Детальные журналы текущего запуска находятся в `outputs/trip_arrival_20261026/`, резервные копии — в `backups/`; эти каталоги не входят в коммит.

## Файлы задачи

Список формируется сравнением с сохранённым состоянием перед задачей, плюс новые служебные модули и документация. Изменения других задач не перечисляются.

- `README.md`
- `core/allocation.py`
- `docs/architecture.md`
- `docs/development.md`
- `docs/operations.md`
- `docs/trip_arrival_costs.md`
- `docs/trip_arrival_report_20261026.md`
- `docs/trip_order_operations.md`
- `orders/arrival.py`
- `orders/arrival_browser_checks.py`
- `orders/arrival_documents.py`
- `orders/arrival_finalization.py`
- `orders/arrival_math.py`
- `orders/arrival_models.py`
- `orders/arrival_views.py`
- `orders/fulfillment.py`
- `orders/fulfillment_browser_checks.py`
- `orders/fulfillment_test_helpers.py`
- `orders/fulfillment_views.py`
- `orders/migrations/0011_trip_arrival_costs.py`
- `orders/models.py`
- `orders/order_editing.py`
- `orders/services.py`
- `orders/test_arrival.py`
- `orders/test_arrival_concurrency.py`
- `orders/test_arrival_documents.py`
- `orders/test_arrival_edge_cases.py`
- `orders/test_arrival_finalization.py`
- `orders/test_arrival_http.py`
- `orders/test_arrival_math.py`
- `orders/test_arrival_schema_compatibility.py`
- `orders/test_arrival_tariffs.py`
- `orders/test_fulfillment.py`
- `orders/test_operation_changes.py`
- `orders/trip_additions.py`
- `orders/trip_prices.py`
- `orders/trip_views.py`
- `orders/trips.py`
- `orders/urls.py`
- `sales/migrations/0033_trip_cost_sources.py`
- `sales/models.py`
- `sales/services.py`
- `sales/views.py`
- `static/js/stock-lines.js`
- `static/js/supply-finalization.js`
- `static/js/supply.js`
- `static/js/trip-finalization-prices.js`
- `static/js/trip-supply-expenses.js`
- `supplies/finalization.py`
- `supplies/migrations/0011_trip_cost_sources.py`
- `supplies/models.py`
- `supplies/services.py`
- `supplies/views.py`
- `tasks/plan.md`
- `tasks/todo.md`
- `templates/orders/_independent_supply_expenses.html`
- `templates/orders/_operation_actions.html`
- `templates/orders/_operation_source.html`
- `templates/orders/_trip_arrival.html`
- `templates/orders/arrival_finalization.html`
- `templates/orders/arrival_prepare.html`
- `templates/orders/arrival_receipt.html`
- `templates/orders/trip_detail.html`
- `templates/sales/create.html`
- `templates/sales/detail.html`
- `templates/sales/edit.html`
- `templates/supplies/_finalization_toolbar.html`
- `templates/supplies/create.html`
- `templates/supplies/detail.html`
- `templates/supplies/finalization.html`
