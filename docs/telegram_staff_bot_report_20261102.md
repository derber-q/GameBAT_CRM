# Отчёт: Telegram-бот сотрудников, 02.11.2026

Исходный и текущий Git HEAD: `b22e60a54127f7dd3c2fc0ed3ed31a93c8937a33`, ветка `main`. Коммит и push не выполнялись.

## Исходные локальные изменения

Сохранены незакоммиченные изменения прежних задач Avito/печати. Они не откатывались и не выдаются за новые функции Telegram:

- `browser_extensions/avito_check/README.md`
- `browser_extensions/avito_check/manifest.json`
- `browser_extensions/avito_check/order-presentation.js`
- `browser_extensions/avito_check/orders-background.js`
- `browser_extensions/avito_check/orders-crm.js`
- `browser_extensions/avito_check/orders.js`
- `browser_extensions/avito_check/test_orders_background.cjs`
- `docs/avito_browser_orders.md`
- `docs/technical/reference/python.md`
- `pricing/avito_extension_browser_checks.py`
- `requirements.txt`
- `sales/avito_orders_browser_checks.py`
- `sales/avito_shipping.py`
- `sales/test_avito_orders.py`

## Реализовано

Отдельное приложение с пятью моделями: StaffBot, StaffBotAccess, StaffBotLink, StaffBotUpdate, StaffBotJob. Права и личная одноразовая привязка используют accounts.User и числовой ID Telegram; username не даёт авторизации.

Единственная бизнес-функция — свежий безымянный XLSX через прежний price.excel.generate_wholesale_price_xlsx, без изменения генератора. Сохранена совместимость скрытых подписанных метаданных с импортом.

Polling и один исполнитель документов независимы; квитанции updates/offset сохраняются, активные задания и частота ограничены. Неизвестная отправка не повторяется. Ошибка сохранения подтверждения после передачи документа также остаётся неизвестным результатом.

В прежний supervisor, мониторинг, блокировки и адаптеры Windows/Linux добавлен telegram_staff. Существующие четыре worker не переустраивались. API-ошибка отделена от падения процесса. Сохранены три попытки запуска, ручное восстановление и общий звук.

local_test показывает только заглушку; реальные клиент, polling и чтение секрета заблокированы. Усилены guard файла, список наследуемых секретов и защита Git от принудительно добавленного токена.

## Схема и рабочая установка

После прямого разрешения пользователя 02.11.2026 в рабочей БД успешно применены `integrations.0010_alter_workercommand_service_alter_workerservice_code` и `telegram_bots.0001_initial`. Контейнер `resource-crm-local` штатно остановлен и запущен заново; отдельный Windows Print Agent не останавливался.

Локальный секрет сохранён в игнорируемом файле `.telegram-staff-bot-token`; его значения нет в коде, этом отчёте или Git. Настоящие `getMe` и `getWebhookInfo` подтвердили бот `ReSOURSE_CRM_BOT` и отсутствие webhook. Бот включён, работает один получатель `getUpdates`; на 14:43 МСК все пять сервисов имеют статус `running`, ошибки отсутствуют. Ручные тестовые сообщения/файлы сотрудникам не отправлялись; фактическое получение XLSX сотрудником ещё не проверено.

Непосредственно перед миграциями, после остановки пишущих процессов, создан согласованный снимок `backups/before_telegram_apply_20261102_113446.sqlite3` (14:34:46 МСК), метаданные и SHA-256 — рядом в JSON. Проверены `integrity_check` и `foreign_key_check`. После миграций все прежние строки таблиц сверены по именам столбцов с этим снимком и совпали; исключены только ожидаемые изменения реестров миграций, типов содержимого и разрешений. Защищённая `backups/current_state_20261031.sqlite3` сохранена без изменений. Диагностические результаты находятся локально в `outputs/telegram_staff_20261102/data_preservation.json`.

После запуска: HTTP страницы входа — 200; `check`, `migrate --check`, `verify_inventory` и `verify_cash` завершились успешно. Доступ конкретным сотрудникам автоматически не выдавался. [Порядок привязки и работы](telegram_staff_bot.md#инструкция-для-администратора-и-сотрудника).

## Выполненные проверки

Дополнение 02.11.2026: главное меню перенесено в постоянную `ReplyKeyboardMarkup`
у поля ввода (`is_persistent`, `resize_keyboard`, без одноразового скрытия).
Выбор склада остаётся inline; прежние callback-кнопки совместимы. Тест перед
правкой подтвердил отсутствие постоянной панели; после правки весь набор
`manage.py test telegram_bots --noinput`: **30 тестов, OK**, код возврата 0.
Проверены нажатие текстовой кнопки, выдача документа, выбор склада и отзыв доступа.
Обновлён справочник и инструкция, локальные ссылки проверены. Для получения новой
панели в существующем чате сотрудник один раз отправляет `/menu`.

- `manage.py test telegram_bots integrations.test_worker_monitoring integrations.test_linux_processes --noinput`: 63 теста, OK.
- `manage.py test telegram_bots.browser_checks --settings=sales.system_browser_settings --noinput`: 1 сценарий Chromium, OK; административная форма, личная привязка, ширина 390 px и тестовая заглушка. Внешняя сеть заблокирована.
- Все 25 `test_*.cjs`: коды возврата 0.
- `manage.py check`: ошибок нет; `makemigrations --check --dry-run`: новых изменений нет.
- `scripts/check_repository.py`, шесть тестов repository hygiene и проверка изменённого дерева на секреты: нарушений нет.
- `scripts/check_project_links.py`: ошибок нет; технические справочники перегенерированы без рабочих записей.
- Отдельные read-only `verify_inventory` / `verify_cash`: остатки и денежные журналы согласованы.
- `migrate --plan`: только две подготовленные миграции; `sqlmigrate integrations 0010`: просмотрена техническая перестройка SQLite, без исполнения SQL.

Полный Django-набор завершён: **1526 тестов за 1710,054 секунды, OK (skipped=2)**, код возврата 0. После последних уточнений обработки неизвестного результата и диагностического снимка отдельно выполнены 63 целевых теста и изолированный Chromium-сценарий; оба процесса завершились OK. Журналы — локально в `outputs/telegram_staff_20261102/`; ожидаемые негативные ошибки доступа/API в них не являются сбоем suite.

## Созданные и изменённые файлы текущего дерева

Список включает сохранённые прежние изменения; исходная граница указана выше. Рабочие ключи, БД, snapshots и outputs в этот список не входят.

- `.gitignore`
- `GameBAT_CRM/environments.py`
- `GameBAT_CRM/local_test.py`
- `GameBAT_CRM/settings.py`
- `GameBAT_CRM/test_guard.py`
- `GameBAT_CRM/urls.py`
- `README.md`
- `browser_extensions/avito_check/README.md`
- `browser_extensions/avito_check/manifest.json`
- `browser_extensions/avito_check/order-presentation.js`
- `browser_extensions/avito_check/orders-background.js`
- `browser_extensions/avito_check/orders-crm.js`
- `browser_extensions/avito_check/orders.js`
- `browser_extensions/avito_check/test_orders_background.cjs`
- `deploy/local_live/.dockerignore`
- `docs/README.md`
- `docs/architecture.md`
- `docs/avito_browser_orders.md`
- `docs/development.md`
- `docs/operations.md`
- `docs/technical/integrations.md`
- `docs/technical/reference/models.md`
- `docs/technical/reference/python.md`
- `docs/technical/reference/routes.md`
- `docs/technical/reference/ui_and_migrations.md`
- `docs/telegram_staff_bot.md`
- `docs/telegram_staff_bot_installation.md`
- `docs/worker_monitoring.md`
- `integrations/linux_processes.py`
- `integrations/migrations/0010_alter_workercommand_service_alter_workerservice_code.py`
- `integrations/test_linux_processes.py`
- `integrations/worker_models.py`
- `integrations/worker_monitoring.py`
- `integrations/worker_policy.py`
- `integrations/worker_processes.py`
- `integrations/worker_runtime.py`
- `integrations/worker_schedule.py`
- `pricing/avito_extension_browser_checks.py`
- `requirements.txt`
- `sales/avito_orders_browser_checks.py`
- `sales/avito_shipping.py`
- `sales/test_avito_orders.py`
- `scripts/build_technical_reference.py`
- `scripts/check_repository.py`
- `scripts/local_network.ps1`
- `scripts/test_repository_hygiene.py`
- `telegram_bots/__init__.py`
- `telegram_bots/access.py`
- `telegram_bots/apps.py`
- `telegram_bots/browser_checks.py`
- `telegram_bots/client.py`
- `telegram_bots/configuration.py`
- `telegram_bots/documents.py`
- `telegram_bots/forms.py`
- `telegram_bots/handlers.py`
- `telegram_bots/jobs.py`
- `telegram_bots/management/__init__.py`
- `telegram_bots/management/commands/__init__.py`
- `telegram_bots/management/commands/run_telegram_staff_bot.py`
- `telegram_bots/menu.py`
- `telegram_bots/migrations/0001_initial.py`
- `telegram_bots/migrations/__init__.py`
- `telegram_bots/models.py`
- `telegram_bots/monitoring.py`
- `telegram_bots/test_worker.py`
- `telegram_bots/tests.py`
- `telegram_bots/urls.py`
- `telegram_bots/views.py`
- `telegram_bots/worker.py`
- `templates/base.html`
- `templates/telegram_bots/connection.html`
- `templates/telegram_bots/dashboard.html`
- `templates/telegram_bots/stub.html`

- `docs/telegram_staff_bot_report_20261102.md`

## Первоначальное включение и ограничения

[Руководство](telegram_staff_bot.md) и [точный план установки](telegram_staff_bot_installation.md). Нужно согласовать две рабочие миграции и краткую остановку/запуск контейнера, затем явно настроить/включить первый бот, разрешить конкретного сотрудника и пройти одноразовую привязку.

Реальное подключение и выдача файла пока не проверены. Linux-распознавание процессов проверено на фиктивном /proc; настоящий production/PostgreSQL не разворачивался и остаётся заблокированным. Перенос одного бота между независимыми БД требует остановки старого получателя: общей аренды между ними нет.

Тесты подтвердили регрессию существующих сценариев в пределах их покрытия; это не гарантия отсутствия любых ошибок. Проверки рабочей БД были только читающими. Миграции и запуск настоящего бота ожидают отдельного согласования по исходному заданию.
