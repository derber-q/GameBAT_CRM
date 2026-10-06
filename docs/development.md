# Карта кода для сопровождения

## Где менять поведение

| Задача | Файлы для первичного изучения |
| --- | --- |
| Поля карточки, изображения и права редактирования | `catalog/models.py`, `product_fields.py`, `nomenclature_forms.py`, `nomenclature_services.py`, `product_media.py`, `nomenclature_views.py`, `admin.py` |
| Аудит товара | `catalog/audit.py`, модели `ProductChangeEvent`/`ProductFieldChange` |
| Поиск, штрихкоды, фильтры | `catalog/product_search.py`, `product_identifiers.py`, `product_filters.py`, `static/js/app.js` |
| Места хранения | `warehouse/storage_locations.py`, `storage_services.py`, локальные модели назначений |
| Остатки и перемещения | `warehouse/services.py`, `models.py` |
| Ревизия локального склада | `warehouse/revision_services.py`, `revision_views.py`, `templates/warehouse/revision.html`; отметки не меняют остатки |
| Приход и себестоимость | `supplies/services.py`, `finalization.py`, ревизии в `models.py` |
| Реализация по строкам | `consignment/services.py`, `row_actions.py`, `opening_balances.py`, `static/js/consignment-actions.js` |
| Цены и предупреждения | `pricing/services.py`, `warnings.py`, `views.py`, `static/js/pricing.js`, `pricing-scroll.js` |
| Продажи и списки | `sales/services.py`, `listing.py`, `views.py`, `_list_group.html`, `_list_row.html`, `sales-status.js` |
| Статистика | `sales/statistics_service.py`, `statistics_forms.py`, `statistics_excel.py` |
| Деньги | `cash/services.py`, `models.py`, `creditors/services.py`, `orders/services.py` |
| Прайсы | `price/services.py`, `excel.py`, `views.py`; импорт в продажу — `sales/views.py` |
| Avito | `integrations/client.py`, `services.py`, `queue.py`, `tasks.py`, `manual_sync.py`, `verification.py`, `required_actions.py` |
| Avito Check | `integrations/avito_check.py`, `reef_api.py`, `reef_settings.py`, `pricing/avito_check_views.py`; результат и ключ — `integrations/models.py` |
| Google Sheets | `integrations/google_sheets.py`, `google_tasks.py`, блок в `api_keys.html`, общий integration worker |
| Оптовая витрина ReSOURCE | `resource_storefront/` — доступ, выборка товаров, редактор и checkout; продажа создаётся через `sales.services.create_sale` |
| Шапка и сотрудники | `templates/base.html`, `core/context_processors.py`, `accounts/views.py`, `accounts/urls.py`, `staff_by_group.html` |

## Яндекс Маркет

`yandex_market/models.py` — состояния и ограничения; `client.py/contracts.json` — официальный API; `services.py/content.py/forms.py` — товары; `orders.py/packing.py/documents.py` — заказы и документы; `queue.py/tasks.py/signals.py` — обмен; `views.py/webhooks.py` — права и HTTP. Общий физический остаток вынесен в `warehouse/inventory.py`, приём физического возврата — в `warehouse/receipts.py`. Подробности и результаты: [отчёт](yandex_market_report.md).

## Как вносить изменения

Сначала проверить текущий diff: в проекте часто есть несколько незакоммиченных задач. Не перезаписывать файлы целиком ради небольшой правки. Для новой бизнес-операции определить источник истины, права, транзакционную границу, аудит и влияние на Avito. Изменения данных модели требуют миграции; правки только комментариев/шаблонов — нет.

Валидация формы удобна пользователю, но критические проверки нужны и в сервисе. Суммы не передавать через `float`. Отмена/повтор запроса/устаревшая страница — нормальные сценарии, которые нельзя превращать в повторное списание.

`select_for_update()` на SQLite не даёт такой же построчной блокировки, как на PostgreSQL. Сохранять атомарность, уникальные ключи операций и существующие конкурентные тесты; не считать добавление этого вызова достаточной защитой от гонок. У реализации одноразовая квитанция является первым SQL-запросом записи.

Сетевые операции не держать внутри долгих транзакций. Новый сигнал должен учитывать откат и `on_commit`. Массовые `update`/`bulk` не воспроизводят автоматически поведение `save()` и все сигналы — это особенно важно для Avito и аудита.

## Шаблоны и JavaScript

Основной стиль — `static/css/gamebat.css`. Dropdown использует `nav-dropdown`, `nav-dropdown-trigger`, `nav-dropdown-menu` и CSS `:hover`/`:focus-within`, без отдельной реализации для `stuf`. Ссылки формируются через `{% url %}`.

Сворачивание привязывает кнопку к элементу по `aria-controls`, меняет `aria-expanded` и `hidden`. Ошибка в ранней инициализации общего `app.js` может отключить все последующие обработчики. Регрессия отсутствующего фильтра серии покрыта `core/test_collapse_js.cjs`.

AJAX-сохранение цен находится в исторически названном `pricing-scroll.js`; имя не означает, что он только восстанавливает прокрутку. Он отправляет FormData, показывает состояние и учитывает новые правки во время запроса. В модальных формах CSS `display:grid` может переопределять HTML `hidden`, поэтому проверять существующие специальные правила.

Сканер использует скорость набора и Enter; не превращать любую клавишу страницы в ввод штрихкода. Клавиатурные обработчики должны уважать обычные поля редактирования.

## Покрытие проверками

`accounts/tests.py`, `core/tests.py` — доступ и базовые страницы; `catalog/test_*.py` — карточки, штрихкоды, миграции и поиск; `warehouse/test_storage_locations.py` — хранение. `supplies/test_revision.py`, `test_cancellation.py`, `test_finalization.py` — пересчёт оценки; `sales/test_listing.py`, `test_cancellation.py`, `test_statistics.py` — списки, деньги, историческая прибыль. `consignment/test_row_actions.py` проверяет повторные и конкурентные запросы, `test_opening_balances.py` — ввод партий без складского списания. `integrations/tests.py`, `test_required_actions.py` подменяют внешний API.

CJS-проверки выполняют реальные скрипты в моделируемом окружении. Они не удостоверяют визуальную раскладку в браузере. Полный список команд — в `operations.md`, результаты текущей проверки — в `verification.md`.

## Известные ограничения текущего состояния

- `nav.stuf` пока доступен только суперпользователю. Сотрудник с правом статистики или поставщиков может открыть разрешённый прямой URL, но не увидеть эти ссылки в шапке. Это расхождение последней реализации с исходным заданием, а не предполагаемая бизнес-политика. Исправление должно сохранить backend-защиту страницы сотрудников.
- «Касса» в меню продаж ведёт к первому складу из `nav_warehouses`. Старый выпадающий выбор касс нескольких складов не перенесён. Остальные кассы доступны по штатным URL и со страниц складов; перед развитием мультисклада нужно восстановить удобный выбор, не создавая второй кассовый сервис.
- Права на создание продажи могут отсутствовать у сотрудника с доступом только к кассе; основной клик «Продажа» всё равно ведёт на форму создания и может дать 403. Сама касса в меню защищена прежним правилом.
- Восстановление из Git не возвращает секреты и медиа. Защищённые документы и фото существуют вне БД.
- Локальные рабочие скрипты из `backups/` и старые импортеры не являются идемпотентным способом разворачивания проекта. Проверять каждый отдельно и не запускать для восстановления по привычке.
- Параметры 289/489 для геймпадов Sony были разовой правкой данных; новых автоматических правил в модели нет.

Эта документационная задача фиксирует наблюдаемое состояние и не меняет перечисленные бизнес-сценарии.
