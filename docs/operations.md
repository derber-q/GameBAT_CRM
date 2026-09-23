# Эксплуатация, проверки и восстановление

Все команды ниже выполняются из корня проекта в PowerShell. В рабочем окружении это `C:\Users\89085\Desktop\GameBAT_CRM`; в другой копии путь нужно заменить. Не копировать персональные абсолютные пути в бизнес-код.

## Окружение

```powershell
$env:PYTHONIOENCODING='utf-8'
.venv\Scripts\python.exe --version
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py showmigrations
```

Первая установка описана в README. На существующей БД сначала проверить снимок и план миграций, затем выполнять `migrate`. Виртуальное окружение не включается в Git. Демонстрационный `seed_demo_data` не предназначен для рабочей базы.

| Параметр | Назначение |
| --- | --- |
| `DJANGO_SECRET_KEY` | Секрет Django; локальная альтернатива — `.django-secret-key` |
| `DJANGO_DEBUG` | По умолчанию `1`; `0` включает HTTPS-перенаправление и защищённые cookie |
| `DJANGO_ALLOWED_HOSTS` | Разрешённые хосты через запятую; для LAN включить текущий IP |
| `INTEGRATION_ENCRYPTION_KEY` | Ключ Fernet; альтернатива — `.integration-encryption-key` |
| `AVITO_API_TIMEOUT_SECONDS` | Таймаут клиента, по умолчанию 10 секунд |
| `AVITO_SYNC_DEBOUNCE_SECONDS` | Задержка объединения изменений товара, по умолчанию 3 секунды |
| `DJANGO_LOG_LEVEL` | Уровень бизнес-журнала, по умолчанию INFO |

Файл `.env` автоматически не загружается текущими settings: переменные нужно передать процессу или настроить внешним запускателем. В settings есть локальный IP по умолчанию; он не универсален и может измениться после подключения к другой сети.

## Сайт и worker

```powershell
$env:DJANGO_ALLOWED_HOSTS='localhost,127.0.0.1,192.168.0.101'
.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000 --noreload
```

Локальный адрес — `http://127.0.0.1:8000/`, с другого устройства — `http://<IP компьютера>:8000/`. Устройства должны иметь сетевой доступ; проверить брандмауэр, привязку `0.0.0.0`, IP и ALLOWED_HOSTS. `DisallowedHost` означает, что сервер достигнут, но Host не разрешён. Не исправлять это бессрочным разрешением всех хостов.

Отдельный рабочий процесс интеграции:

```powershell
.venv\Scripts\python.exe manage.py run_integration_worker
```

Он выполняет реальные задания Avito. `--once` означает один цикл обработки, а не безопасную имитацию. `--poll` задаёт паузу при пустой очереди. `start_localhost.ps1` проверяет сайт, запускает его и worker скрыто, затем открывает браузер. Если сайт уже отвечает, ярлык не перезапускает его автоматически.

При `--noreload` после правок Python или шаблонов остановить проверенные процессы проекта и запустить заново. На Windows `.venv\Scripts\python.exe` может иметь дочерний процесс Python: два PID сами по себе не доказывают два сервера. Проверять слушателей порта:

```powershell
Get-CimInstance Win32_Process | Where-Object {
    $_.Name -match '^python' -and $_.CommandLine -match 'manage.py (runserver|run_integration_worker)'
} | Select-Object ProcessId,ParentProcessId,CommandLine
Get-NetTCPConnection -LocalPort 8000 -State Listen
```

`runserver` — сервер разработки. Эти инструкции описывают локальную сеть, а не готовое публичное размещение с TLS, резервированием и промышленным WSGI/ASGI-сервером.

## Проверки кода

```powershell
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.venv\Scripts\python.exe manage.py test --noinput
```

Django создаёт отдельную тестовую базу. Не изменять тестовую конфигурацию так, чтобы suite использовал рабочую БД. Ошибки в журналах негативных тестов ожидаемы; результат определяется финальным `OK`/`FAILED` и кодом процесса. Для короткой проверки задавать модуль или конкретный тест после `test`.

Node.js нужен для проверок JS, но не для запуска сайта. При наличии Node в PATH:

```powershell
node core/test_collapse_js.cjs
node pricing/test_pricing_js.cjs
node pricing/test_pricing_scroll.cjs
node sales/test_sales_status_js.cjs
node consignment/test_actions_js.cjs
```

Это проверки логики скриптов с моделируемым DOM, не полноценные проверки браузера. После UI-изменений вручную проверить нужную страницу, сохранение, клавиатуру, сканер и выпадающее меню. При отсутствии браузера явно отметить границу проверки.

## Диагностика данных

```powershell
.venv\Scripts\python.exe manage.py verify_inventory
.venv\Scripts\python.exe manage.py verify_cash
```

Первая команда проверяет сумму реализации и отсутствие отрицательного склада. Она не сверяет фактический пересчёт товара с Excel. Вторая сверяет кассы и сейфы с журналом. Обе ничего не исправляют. Расхождение требует исследования первичных записей; нельзя просто обнулить журнал или переписать баланс.

`verify_avito_sync` обращается к реальному API и обновляет локальные снимки/создаёт CSV. Без `--fix` не предназначен для исправления внешних данных; с `--fix` может отправлять изменения. Для обычного тестирования кода использовать подменённый API в тестах.

Если ручная синхронизация ожидает: проверить worker и `AvitoSyncJob`, `run_after`, `last_error`, фазу, время обновления. Успешный HTTP проверки подключения не равен завершённой сверке. Для SQLite учитывать короткие блокировки записывающих процессов; не оставлять сетевой HTTP внутри долгой транзакции. Не запускать несколько worker без проверки конкурентного захвата заданий.

## Резервная копия

Рабочий файл — `db.sqlite3`. Копия активного файла обычным копированием может не включить состояние журнала. Использовать SQLite Backup API либо остановить все пишущие процессы и убедиться в согласованности БД. Пример согласованного снимка с новым именем:

```powershell
.venv\Scripts\python.exe -c "import sqlite3; from pathlib import Path; from datetime import datetime; folder=Path('backups'); folder.mkdir(exist_ok=True); target=folder/('crm_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.sqlite3'); source=sqlite3.connect('file:db.sqlite3?mode=ro',uri=True); snapshot=sqlite3.connect(target); source.backup(snapshot); assert snapshot.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert not snapshot.execute('PRAGMA foreign_key_check').fetchall(); snapshot.close(); source.close(); print(target)"
```

Сохранить отдельно `.integration-encryption-key`, `.django-secret-key`, используемые переменные окружения и `protected_media/`. Не выводить значения ключей в журнал. Снимок SQLite не содержит файлов фотографий/документов. Папки резервирования и секреты исключены из Git.

`db.sqlite3` исторически отслеживается Git. Для контрольного коммита код и согласованный снимок должны соответствовать друг другу; простое наличие `.gitignore` не прекращает отслеживание. Не публиковать репозиторий с рабочей БД как публичный шаблон.

## Восстановление

1. Выбрать проверенный коммит и сохранить текущее состояние отдельно.
2. Остановить сайт, worker и другие процессы записи. Проверить точные PID и пути.
3. В отдельной папке восстановить код и базу из одной контрольной точки. Не смешивать старую БД с несовместимым набором миграций.
4. Вернуть секреты и медиа из защищённой копии; при другом ключе Avito потребуется заново ввести реквизиты. Связи товара и объявления остаются в БД.
5. Выполнить integrity/foreign-key проверки, `check`, просмотр миграций, `verify_inventory`, `verify_cash`. Миграции вперёд применять только после понимания версии восстановления.
6. Запустить сайт, проверить карточки и операции. Worker включать после проверки целевых цен и остатков.

Откат CRM не откатывает Avito: восстановленные цены и остатки могут быть устаревшими относительно внешнего аккаунта. Прерванные задания имеют механизм повторного запуска; это также нужно учитывать перед включением worker.
