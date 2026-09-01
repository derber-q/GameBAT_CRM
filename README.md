# GameBAT CRM

Автономная внутренняя CRM для учёта видеоигр и техники GameBAT Store. Первая версия построена на Django Templates и Django ORM, не использует внешние API и сторонние интеграции.

## Возможности

- собственная модель пользователя, роли администратора и работника;
- наборы прав на основе Django Group и индивидуальные permissions;
- защищённые подтверждающие документы пользователей;
- склад CD по платформам и техники по типам товара;
- поставщики с серверным сокрытием реквизитов;
- атомарная приёмка поставок, распределение расходов по физическим единицам и средневзвешенная себестоимость;
- неизменяемая история принятых поставок;
- атомарная передача товара на реализацию и возврат;
- ручные курсы USD/RUB, AED/RUB и USD/AED;
- единый интерфейс CRM и стилизованный Django Admin.

## Быстрый запуск

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Откройте `http://127.0.0.1:8000/`. Первый администратор создаётся только штатной командой `createsuperuser`; готовых логинов и паролей в проекте нет.

Для production задайте `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0` и `DJANGO_ALLOWED_HOSTS`. При локальной разработке секрет автоматически создаётся в игнорируемом файле `.django-secret-key`.

## Основные разделы

- `/warehouse/` — склад;
- `/supplies/` — история и приёмка поставок;
- `/consignment/` — товар на реализации, передача и возврат;
- `/suppliers/` — поставщики;
- `/accounts/users/` — пользователи;
- `/accounts/permission-sets/` — наборы прав;
- `/admin/` — справочники, товары, площадки и валютные курсы.

Platform, Brand, ProductType, SalesPlatform и CurrencyRate управляются через Django Admin. Рабочие операции поставки и реализации выполняются только в собственном интерфейсе CRM.

## Проверки

```powershell
python manage.py test
python manage.py check
python manage.py makemigrations --check
python manage.py verify_inventory
```

`verify_inventory` только диагностирует расхождения между агрегированным полем товара и остатками площадок, ничего не исправляя автоматически.
