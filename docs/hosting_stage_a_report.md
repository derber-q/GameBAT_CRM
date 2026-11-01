# Отчёт: безопасная основа тестового окружения, этап A

Дата: 31.10.2026. Общий контракт A–F принят, этот проход ограничен этапом A.
Режим local_test реализован и испытан рядом с рабочей CRM. **Полная подготовка
хостинга не завершена**: B–F не выполнялись, production намеренно заблокирован.

**Дополнение после запуска Docker Engine в тот же день:** контейнерная сборка,
HTTP/браузер, запрет внешних соединений без Python-guard и сохранность данных при
перезапуске теперь проверены. [Актуальный протокол](local_test_docker_acceptance_20261031.md).
Ниже сохранено состояние первоначального прохода, когда Engine был недоступен.

## Сохранённое исходное состояние

Исходная и итоговая ветка: `main`; HEAD:
`ed6490e49ab107da2598ec27d3772f0f278da880`.
Коммит, push, reset, clean и переписывание истории не выполнялись.

До работы: 344 записи git status --short, включая 306 изменённых, 7 удалённых
и 31 неотслеживаемую запись/каталог. Список сохранён в
`outputs/hosting_stage_a/baseline/git-status.txt`. Исходные версии 22 файлов
сохранены рядом; остальные правки существующих файлов внесены точечно.

Действующий мониторинг найден в локальных worker_*.py, management commands,
шаблонах и статике. Его модели, миграция 0009 и бизнес-алгоритм не переписаны.
Сайт и рабочие Avito/Яндекс/Sheets/печать/supervisor не останавливались.
PID и время создания всех 12 рабочих процессов (launcher + интерпретатор) совпали
с исходным снимком. Тестовый entry point не попадает в рабочий распознаватель.
Ранее сохранённые защищённые резервные копии не удалялись.

## Реализовано и как пользоваться

Подробный контракт: [окружения этапа A](environments_stage_a.md).

- Default без GAMEBAT_ENV остаётся local_live: прежние SQLite, ключи, сессии,
  рабочий ярлык, цвета и внешние интеграции.
- local_test использует собственные SQLite/media/tmp/logs/keys/cookies/cache/locks,
  постоянную серверную метку и оранжевую навигацию. Корень данных ограничен
  отдельным подкаталогом outputs/local_test, ссылки и смешение ключей отклоняются.
- production распознаётся и завершается с понятной ошибкой до проверки этапа B.
  Это **ещё не готовая production-конфигурация** и не поддержка PostgreSQL.
- Центральные проверки стоят перед клиентами/транспортами, ключами и Windows-печатью.
  Запрещены также прямые HTTP/socket/subprocess/SQLite-обходы штатных путей,
  live webhook и сценарий расширения. Шапка получает пустые курсы без обращения к API.
- При попытке внешнего действия нет fallback в настоящий аккаунт: ответ содержит
  сообщение о запрете. Рабочие API-ключи нельзя сохранить тестовой формой.
- Отдельный запускатель не занимает 8000, не останавливает занятый порт, ждёт
  HTTP-готовности и создаёт только синтетические данные по -Initialize.
- Мониторинг в runtime A показывает реальные интеграции намеренно отключёнными.
  Алгоритм восстановления дополнительно испытан FakeProcesses при local_test
  на отдельной тестовой БД. Runtime-симуляторы процессов относятся к этапу D.
- Подготовлен очищенный Docker-контекст и internal-сеть без рабочих bind mounts.
  Их фактический сетевой запуск пока не испытан: Docker Engine недоступен.

Тестовая CRM оставлена на `http://127.0.0.1:8001/`, instance `acceptance`.
Синтетический логин `test-admin`, случайный пароль — только в
`outputs/local_test/acceptance/secrets/test-admin.json`. Рабочие логины не копировались.
Запуск и команды с явными границами окружения приведены в руководстве.

## Проверки

Все указанные тестовые БД отделены от db.sqlite3. API/принтер в проверках подменены
либо заблокированы до вызова. В браузерной приёмке local_test не было ни одного
запроса за пределы собственного origin. Снимки — outputs/hosting_stage_a/browser/.

| Проверка / точная команда через .venv/Scripts/python.exe | Результат |
| --- | --- |
| manage.py test --parallel 4 --noinput | 1427 тестов, OK, 353,028 с; код 0 |
| manage.py test core.test_environments core.test_external_isolation core.tests core.test_local_network integrations.test_worker_monitoring --noinput | 60 тестов, OK, 13,374 с; код 0 |
| manage.py test core.test_environments core.test_external_isolation --noinput после последнего усиления SQLite guard | 13 тестов, OK, 4,887 с; код 0 |
| -m unittest core.local_test_browser_checks -v после последнего guard и перезапуска только тестового сайта | реальный local_test: 1 составной сценарий, OK, 5,800 с; код 0 |
| manage.py test integrations.worker_browser_checks core.navigation_browser_checks sales.notification_browser_checks --settings=sales.system_browser_settings --noinput | 8 Chromium/WebKit-проверок прежней навигации/звука, OK, 35,912 с; код 0 |
| Все test_*.cjs, список из rg --files -g test_*.cjs | 24 файла, каждый код 0 |
| -m GameBAT_CRM.local_test check | ошибок нет, код 0 |
| -m GameBAT_CRM.local_test makemigrations --check --dry-run | изменений схемы нет, код 0 |
| manage.py check; manage.py makemigrations --check --dry-run | ошибок/новых миграций нет, код 0 |
| scripts/prepare_local_test_container.py outputs/hosting_stage_a/container_final | контекст создан, БД/ключи/media не копируются; код 0 |
| docker compose -f deploy/local_test/compose.yaml config --quiet | синтаксис корректен, код 0 |

Полный suite выполнен до добавления двух дополнительных адресных сценариев/усиления
guard; эти изменения проверены последующим адресным прогоном. Новый guard действует
только в отдельном local_test-процессе и не меняет режим обычного suite/live.
Дальнейшие финальные проверки запуска и справочника приведены в конце отчёта.

CJS запускались установленным Node runtime приложения (node отсутствует в PATH).
Результаты по каждому файлу: outputs/hosting_stage_a/cjs-results.json.
Итоги процессов не подменяются ожидаемыми PermissionDenied/ValidationError
негативных сценариев. Журналы лежат в outputs/hosting_stage_a/ и не добавляются в Git.

## Найденные и исправленные проблемы

Первый тест настроек ожидаемо падал до реализации режима. Затем проверка показала
оборачивание PermissionError сетевыми библиотеками: тест проверяет признак запрета
в цепочке ошибки, а не разрешает запрос. В CPython 3.14 audit connect/handle
происходит до завершения SQLite Connection.__init__: authorizer перенесён в
ограниченный подкласс после super().__init__, сырой native connect запрещён.
Добавлены проверки ATTACH, URI и поддельного memorydb.

PowerShell 5.1 потребовал UTF-8 BOM для нового русскоязычного запускателя.
Добавлено ожидание HTTP-готовности. Браузерный тест уточнён под реальные маршруты
Admin и формы: неподключённая интеграция не имеет кнопки проверки подключения.
Эти промежуточные неудачи не скрыты; итоговые проверки повторены.

## Файлы

Новые:
- GameBAT_CRM/environments.py, local_test.py, test_guard.py;
- core/external_policy.py, environment_context.py, test_environments.py,
  test_external_isolation.py, local_test_browser_checks.py;
- core/management/commands/initialize_local_test.py;
- start_local_test.ps1;
- templates/core/_test_environment_banner.html, static/css/test-environment.css;
- scripts/prepare_local_test_container.py, deploy/local_test/Dockerfile, compose.yaml;
- docs/hosting_plan.md, environments_stage_a.md, hosting_stage_a_report.md.

Изменены:
- GameBAT_CRM/settings.py;
- клиенты integrations/client.py, reef_api.py, google_sheets.py, services.py,
  reef_settings.py, avito_check.py;
- yandex_market/client.py, documents.py, services.py, webhooks.py;
- core/services/coinbase.py и rapira.py, sales/label_printing.py;
- integrations/worker_policy.py и worker_processes.py — только отказ в local_test;
- pricing/avito_check_views.py;
- templates/base.html, templates/admin/base_site.html, шаблоны витрины и Avito Check;
- README, architecture/development/operations и четыре технических справочника.

Новых миграций нет. Только новая тестовая БД прошла существующие миграции.
Рабочую SQLite не мигрировали, рабочие заказы/остатки/деньги/ключи не исправляли,
очереди не синхронизировали и ярлыки ради проверки не печатали.

## Невыполненные этапы и ограничения

| Этап/компонент | Точное состояние |
| --- | --- |
| A, Windows local_test | Программная изоляция и браузерная приёмка реализованы |
| A, инфраструктурная изоляция | Compose/контекст подготовлены; Engine недоступен, runtime/egress не испытаны |
| B, PostgreSQL и Linux/production | Не реализовано и не испытано; production блокируется |
| C, GitHub/установки/откаты | Не реализовано; кандидаты нельзя исполнять в нативном тестовом процессе |
| D, серверные worker | Прежний мониторинг сохранён; Linux/runtime-симуляторы не реализованы |
| E, Print Agent | Не реализован; прежняя физическая печать local_live сохранена |
| E, Opera GX | Только отключён live-сценарий в local_test; HTTPS-origin/версии не менялись |
| F, готовность VPS | Не подтверждена; VPS не выбран |

Python-guard не является защитой от произвольного недоверенного C/Python-кода.
До инфраструктурной проверки контейнера нельзя запускать непроверенные кандидаты
обновлений. Реальные data migration, backup/restore PostgreSQL, check --deploy,
TLS/reverse proxy, Print Agent и испытания выбранного VPS остаются обязательными
следующими этапами. Их нельзя отмечать выполненными по этому отчёту.

Рабочая CRM остаётся запущенной. Для применения A к рабочим процессам их
перезапуск сейчас не выполнялся и не требуется для проверки тестового режима.

## Финальная проверка сохранности

После всех правок повторно сверены PID/время создания 12 рабочих процессов:
они неизменны. Читающий запрос страницы входа на 8000 вернул 200 без тестового
заголовка и метки; на 8001 — 200 с заголовком local_test и меткой. Рабочая сессия
при этом не создавалась. Контрольные данные: outputs/hosting_stage_a/final-health.json.

Технический справочник перегенерирован и проверен; проверка ссылок и Git-индекса
прошла без ошибок. Контекст контейнера подготовлен без рабочего каталога данных,
но сам контейнер не запускался. Никакие ограничения Docker/Windows Firewall
рабочей CRM не изменялись, Docker Desktop не запускался автоматически.
