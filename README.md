# ReSOURCE / GameBAT CRM

Внутренняя CRM GameBAT Store: номенклатура видеоигр/техники, несколько складов, закупочные заказы и рейсы, приходы, продажи, реализация, кассы/сейфы, долги партнёров, прайсы и витрины. Внешние интеграции: Avito, ReefAPI, Google Sheets и Яндекс Маркет FBS.

Актуализация структуры и технической документации: **31.10.2026**.

## Документация

- [Полный технический навигатор](docs/technical/README.md): страницы, функции, приложения, формулы, транзакции, правила изменения и программные справочники.
- [Индекс тематических документов](docs/README.md).
- [Архитектура и правила учёта](docs/architecture.md).
- [Эксплуатация и восстановление](docs/operations.md).
- [Карта сопровождения кода](docs/development.md).
- [Telegram-бот сотрудников: актуальный оптовый Excel](docs/telegram_staff_bot.md).
- [Печать из Docker и удалённого сервера через Windows-агент](docs/print_agent.md).
- [Ручные обновления GitHub: страница и отдельный серверный менеджер](docs/updates.md).
- [Пользовательские сценарии](docs/user_guide.md).
- [Результаты подготовки и проверки](docs/maintenance_20261031.md).
- [Правила работы агента](AGENTS.md).

Документы со старой датой проверки описывают состояние на ту дату. Действующее прибытие и совместная финализация рейса описаны в [trip_arrival_costs.md](docs/trip_arrival_costs.md); ранний сценарий отдельных курсов не является текущим правилом новых операций.

## Структура

Сервер — Django 5.2.17, Templates, ORM и SQLite. JavaScript дополняет серверные формы и таблицы; отдельного SPA нет. Зафиксированные зависимости — `requirements.txt`. Для браузерных проверок дополнительно `requirements-browser.txt`.

| Приложение | Ответственность |
| --- | --- |
| `core`, `accounts` | Общая оболочка, курсы, пользователи, permissions |
| `catalog`, `partners` | Товарные карточки, штрихкоды, серии, контрагенты |
| `warehouse`, `supplies`, `consignment` | Физические склады, приход/оценка, партии реализации |
| `sales`, `cash`, `creditors` | Продажи/статистика, наличные, задолженность |
| `pricing`, `price` | Текущие цены/FBS/Avito Check и проверяемые Excel-прайсы |
| `orders` | Закупочные заказы, поставщики, рейсы, прибытие/финализация |
| `integrations`, `yandex_market` | Очереди и внешние сервисы |
| `telegram_bots` | Личный бот сотрудников, безопасная привязка и свежий оптовый Excel |
| `resource_storefront` | Оптовая/розничная витрины и оформление |

`templates/` и `static/` содержат общую оболочку. `browser_extensions/avito_check/` — исходники расширения Opera/Chromium. Миграции и тесты являются частью CRM, а не временными файлами.

## Первый запуск отдельной новой копии

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py createsuperuser
.venv\Scripts\python.exe manage.py runserver
```

Это установка новой пустой базы, а не инструкция восстановления/обнуления существующей. Готового логина/пароля нет. На рабочей установке сначала проверить текущую БД, резервную копию и план миграций. Вход: `http://127.0.0.1:8000/` → `/crm/accounts/login/`.

## Сайт и фоновые процессы

Отдельная безопасная тестовая CRM: [режимы и запуск local_test](docs/environments_stage_a.md).
Рабочая локальная CRM с основной SQLite в Docker: [запуск и данные](docs/local_live_container.md).
По умолчанию сохраняется `local_live`; `start_local_test.ps1` использует другой порт,
отдельные данные и оранжевую шапку. Подготовка хостинга выполняется по
[плану A–F](docs/hosting_plan.md); production пока заблокирован до этапа B.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\start_localhost.ps1 -SiteOnly
```

`-SiteOnly` не запускает и не останавливает интеграции/принтер. Без этого флага запускатель отдельно проверяет сайт, сервисные worker Avito/Яндекс/Google и worker печати. Обычный запуск может выполнять реальные внешние изменения.

Сайт с `--noreload` и каждый worker требуют загрузки нового кода после Python-изменений. Проверять путь/команду конкретного процесса; не завершать все `python.exe`. Для LAN использовать текущий адрес компьютера и `DJANGO_ALLOWED_HOSTS`, а не бессрочное разрешение всех хостов. Подробности — [эксплуатация](docs/operations.md).

## Критические правила

- Физический остаток — `CDWarehouseStock`/`TechWarehouseStock`; карточка не хранит независимое общее количество.
- Реализация учитывается партиями `stock_id`; `quantity_on_consignment` — производная сумма.
- Средняя cost прихода рассчитывается по физическому остатку всех складов. Исторические продажи используют собственные снимки.
- Деньги — `Decimal`, клиентские проверки — копейки/`BigInt`. Наличные, банк и долг раздельны.
- Частичный расчёт требует настоящего `Partner`, разрешённого оптового сценария и серверной проверки. Отмена сторнирует вклад своей операции.
- Прибытие рейса фиксирует общие USDT/AED, USDT/RUB и доставку. После общей финализации складской приход проходит обычную проверку продажных цен по будущей средней cost.
- Яндекс готов к отгрузке после подтверждённой печати ярлыка; scan/picking, print job и внимание сотрудника — разные состояния.
- Скрытая кнопка не заменяет backend-права. Пользователи и `stuf` защищены `superuser_required`.

## Проверки

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py test --noinput
.venv\Scripts\python.exe manage.py verify_inventory
.venv\Scripts\python.exe manage.py verify_cash
.venv\Scripts\python.exe -m unittest scripts.test_repository_hygiene -v
.venv\Scripts\python.exe scripts/check_repository.py
.venv\Scripts\python.exe scripts/check_project_links.py
.venv\Scripts\python.exe scripts/build_technical_reference.py --check
```

Suite создаёт отдельную тестовую БД. Все `test_*.cjs` запускаются Node.js. Браузерные проверки используют специальные settings и отдельную SQLite; их карта находится в [справочнике проверок](docs/technical/reference/ui_and_migrations.md). API/принтер подменяются. `run_integration_worker`, настоящая синхронизация и `verify_avito_sync --fix` не являются безопасным способом проверить UI.

## Рабочие данные и Git

Текущая `db.sqlite3`, её активные WAL/SHM, секреты и `protected_media/` остаются локально. Согласованная резервная копия текущего состояния — `backups/current_state_20261031.sqlite3`; контрольная информация рядом в JSON. Она исключена из очистки и Git. Старые копии удаляются только после успешной проверки новой.

База уже не входит в текущий Git-индекс, но её прежние снимки существуют в старых коммитах. `.gitignore` не удаляет опубликованную историю. Переписывание истории и force push этой подготовкой не выполняются.

Защита от будущего случайного коммита данных:

```powershell
git config --local core.hooksPath .githooks
```

Hook проверяет именно индекс и обнаруживает в том числе `git add -f` и SQLite под другим расширением. При клонировании включается отдельно. Он не заменяет review секретов в исходниках. Не коммитить `backups`, `outputs`, медиа, виртуальное окружение, `node_modules`, ключи и `.env`. Подробнее — [хранение и Git](docs/technical/repository_and_data.md).

Коммит и push выполняются только по прямому поручению владельца.
