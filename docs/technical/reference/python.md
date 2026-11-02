# Python-модули, функции и методы

<!-- Сгенерировано scripts/build_technical_reference.py; не редактировать вручную. -->

Справочник исходников и метаданных схемы, без рабочих записей/ключей. Перегенерация: `.venv/Scripts/python.exe scripts/build_technical_reference.py`.

Функций/методов: **1693**.

Вложенные функции, миграции и тесты не включены в этот индекс; их отдельная карта находится ниже в справочнике UI/проверок. Декораторы, docstring и вызываемые символы описывают контракт/зависимости, но не заменяют чтение тела перед изменением.

## `accounts/admin.py`

Регистрация моделей и разрешённых действий в Django Admin пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django.contrib`, `django.contrib.auth.admin`, `django.contrib.auth.models`, `models`.

### `SuperuserOnlyAdminMixin.has_module_permission(self, request)`

Исходник: `accounts/admin.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SuperuserOnlyAdminMixin.has_view_permission(self, request, obj=None)`

Исходник: `accounts/admin.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SuperuserOnlyAdminMixin.has_add_permission(self, request)`

Исходник: `accounts/admin.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SuperuserOnlyAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `accounts/admin.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SuperuserOnlyAdminMixin.has_delete_permission(self, request, obj=None)`

Исходник: `accounts/admin.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `accounts/apps.py`

Конфигурация приложения и его регистрация в Django пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django.apps`.

## `accounts/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django`, `django.contrib.auth.forms`, `django.contrib.auth.models`, `django.db`, `models`.

### `CRMUserCreationForm.save(self, commit=True)`

Исходник: `accounts/forms.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.save_m2m`, `super`, `super().save`, `user.save`.

### `CRMUserUpdateForm.__init__(self, *args, **kwargs)`

Исходник: `accounts/forms.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `CRMUserUpdateForm.save(self, commit=True)`

Исходник: `accounts/forms.py:63`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.save_m2m`, `super`, `super().save`, `user.save`.

### `PermissionSetForm.__init__(self, *args, **kwargs)`

Исходник: `accounts/forms.py:88`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `super`, `super().__init__`.

### `PermissionSetForm.save(self, commit=True)`

Исходник: `accounts/forms.py:95`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionSetMetadata.objects.update_or_create`, `self.cleaned_data.get`, `super`, `super().save`.

## `accounts/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django.contrib.auth.models`, `django.db`.

### `verification_document_path(instance, filename)`

Исходник: `accounts/models.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `User.role_label(self)`

Исходник: `accounts/models.py:33`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `User.__str__(self)`

Исходник: `accounts/models.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `PermissionSetMetadata.__str__(self)`

Исходник: `accounts/models.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `accounts/urls.py`

Именованные HTTP-маршруты приложения пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django.contrib.auth`, `django.urls`.

## `accounts/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю пользователей и прав.

Управление сотрудниками и stuf требует superuser; документы выдаются защищённо.

Импорты: `django.contrib`, `django.contrib.auth`, `django.contrib.auth.decorators`, `django.contrib.auth.forms`, `django.contrib.auth.models`, `django.core.exceptions`, `django.db.models`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `forms`, `functools`, `models`.

### `superuser_required(view_func)`

Исходник: `accounts/views.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `view_func`, `wraps`.

### `user_list(request)`

Исходник: `accounts/views.py:36`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `User.objects.prefetch_related`, `render`.

### `staff_by_group(request)`

Исходник: `accounts/views.py:41`.

Декораторы: `superuser_required`.

Обзор сотрудников по реальным группам прав с доступом как у списка пользователей.

Статические вызовы: `Group.objects.order_by`, `Group.objects.order_by('name', 'pk').prefetch_related`, `Prefetch`, `User.objects.order_by`, `render`, `users.filter`.

### `user_detail(request, pk)`

Исходник: `accounts/views.py:57`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `User.objects.prefetch_related`, `get_object_or_404`, `render`.

### `user_create(request)`

Исходник: `accounts/views.py:63`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CRMUserCreationForm`, `form.is_valid`, `form.save`, `logger.info`, `messages.success`, `redirect`, `render`.

### `user_update(request, pk)`

Исходник: `accounts/views.py:74`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CRMUserUpdateForm`, `form.is_valid`, `form.save`, `get_object_or_404`, `logger.info`, `messages.success`, `redirect`, `render`.

### `admin_password_reset(request, pk)`

Исходник: `accounts/views.py:86`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AdminPasswordResetForm`, `form.is_valid`, `form.save`, `get_object_or_404`, `logger.info`, `messages.success`, `redirect`, `render`.

### `password_change(request)`

Исходник: `accounts/views.py:98`.

Декораторы: `login_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PasswordChangeForm`, `form.is_valid`, `form.save`, `messages.success`, `redirect`, `render`, `update_session_auth_hash`.

### `verification_document(request, pk)`

Исходник: `accounts/views.py:109`.

Декораторы: `login_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FileResponse`, `Http404`, `PermissionDenied`, `get_object_or_404`, `mimetypes.guess_type`, `request.user.has_perm`, `target.verification_document.name.rsplit`, `target.verification_document.storage.open`.

### `permission_set_list(request)`

Исходник: `accounts/views.py:125`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Group.objects.prefetch_related`, `render`.

### `permission_set_edit(request, pk=None)`

Исходник: `accounts/views.py:130`.

Декораторы: `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Group`, `PermissionSetForm`, `form.is_valid`, `form.save`, `get_object_or_404`, `logger.info`, `messages.success`, `redirect`, `render`.

### `permission_set_delete(request, pk)`

Исходник: `accounts/views.py:143`.

Декораторы: `require_POST`; `superuser_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `group.delete`, `logger.info`, `messages.success`, `redirect`.

## `cash/admin.py`

Регистрация моделей и разрешённых действий в Django Admin кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django.contrib`, `models`.

### `CashRegisterAdmin.has_add_permission(self, request)`

Исходник: `cash/admin.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashRegisterAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `cash/admin.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SafeAdmin.has_add_permission(self, request)`

Исходник: `cash/admin.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SafeAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `cash/admin.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransactionAdmin.has_add_permission(self, request)`

Исходник: `cash/admin.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransactionAdmin.has_change_permission(self, request, obj=None)`

Исходник: `cash/admin.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransactionAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `cash/admin.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `cash/apps.py`

Конфигурация приложения и его регистрация в Django кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django.apps`.

### `CashConfig.ready(self)`

Исходник: `cash/apps.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `cash/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django`.

## `cash/management/commands/verify_cash.py`

Диагностика балансов кассы/сейфа по журналу; команда ничего не исправляет.

Импорты: `cash.models`, `decimal`, `django.core.management.base`, `django.db.models`.

### `Command.handle(self, *args, **options)`

Исходник: `cash/management/commands/verify_cash.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.all`, `CommandError`, `Decimal`, `Q`, `Safe.objects.all`, `Sum`, `errors.append`, `len`, `register.transactions.filter`, `register.transactions.filter(Q(operation_type__in=(CashTransaction.OperationType.COLLECTION, CashTransaction.OperationType.SALE_REFUND, CashTransaction.OperationType.CASH_TO_SAFE, CashTransaction.OperationType.CUSTOMER_ORDER_REFUND)) | Q(operation_type=CashTransaction.OperationType.CREDITOR_ADVANCE, safe__isnull=True)).aggregate`, `register.transactions.filter(Q(operation_type__in=(CashTransaction.OperationType.DEPOSIT, CashTransaction.OperationType.SALE_PAYMENT, CashTransaction.OperationType.SAFE_TO_CASH, CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT, CashTransaction.OperationType.CUSTOMER_ORDER_POSTPAYMENT)) | Q(operation_type=CashTransaction.OperationType.CREDITOR_REPAYMENT, safe__isnull=True)).aggregate`, `safe.transactions.filter`, `safe.transactions.filter(operation_type__in=(CashTransaction.OperationType.SAFE_COLLECTION, CashTransaction.OperationType.SAFE_TO_CASH, CashTransaction.OperationType.CREDITOR_ADVANCE)).aggregate`, `safe.transactions.filter(operation_type__in=(CashTransaction.OperationType.SAFE_DEPOSIT, CashTransaction.OperationType.CASH_TO_SAFE, CashTransaction.OperationType.CREDITOR_REPAYMENT)).aggregate`, `self.stderr.write`, `self.stdout.write`, `self.style.SUCCESS`.

## `cash/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django.conf`, `django.core.validators`, `django.db`, `warehouse.models`.

### `CashRegister.__str__(self)`

Исходник: `cash/models.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Safe.__str__(self)`

Исходник: `cash/models.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.signed_amount(self)`

Исходник: `cash/models.py:185`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.is_internal_transfer(self)`

Исходник: `cash/models.py:195`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.is_outflow(self)`

Исходник: `cash/models.py:202`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.source_label(self)`

Исходник: `cash/models.py:211`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.destination_label(self)`

Исходник: `cash/models.py:231`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CashTransaction.__str__(self)`

Исходник: `cash/models.py:250`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_operation_type_display`.

## `cash/services.py`

Безопасные операции с физическими наличными касс складов.

Импорты: `decimal`, `django.core.exceptions`, `django.db`, `models`.

### `_positive_amount(value)`

Исходник: `cash/services.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `str`.

### `_comment(value)`

Исходник: `cash/services.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `str`, `str(value or '').strip`.

### `_operation_key(value)`

Исходник: `cash/services.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `str`, `uuid.UUID`, `uuid.uuid4`.

### `_existing_operation(operation_key, operation_type)`

Исходник: `cash/services.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashTransaction.objects.select_for_update`, `CashTransaction.objects.select_for_update().filter`, `CashTransaction.objects.select_for_update().filter(operation_key=operation_key).first`, `ValidationError`.

### `_locked_register(warehouse_id)`

Исходник: `cash/services.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.select_for_update`, `CashRegister.objects.select_for_update().select_related`, `CashRegister.objects.select_for_update().select_related('warehouse').get`, `ValidationError`.

### `_locked_safe(warehouse_id)`

Исходник: `cash/services.py:57`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Safe.objects.select_for_update`, `Safe.objects.select_for_update().select_related`, `Safe.objects.select_for_update().select_related('warehouse').get`, `ValidationError`.

### `deposit_cash(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:65`.

Декораторы: `transaction.atomic`.

Вносит реальные наличные на выбранный склад атомарно с журналом. Ключ операции позволяет безопасный повтор; права проверяет вызывающий сценарий.

Статические вызовы: `CashTransaction.objects.create`, `_comment`, `_existing_operation`, `_locked_register`, `_operation_key`, `_positive_amount`, `logger.info`, `register.full_clean`, `register.save`.

### `collect_cash(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:89`.

Декораторы: `transaction.atomic`.

Уменьшает кассу вместе с журналом; недостаток наличных откатывает всё. Это инкассация, не отмена продажи.

Статические вызовы: `CashTransaction.objects.create`, `ValidationError`, `_comment`, `_existing_operation`, `_locked_register`, `_operation_key`, `_positive_amount`, `logger.info`, `register.full_clean`, `register.save`.

### `credit_sale_payment(*, sale, actor)`

Исходник: `cash/services.py:115`.

Декораторы: `transaction.atomic`.

Проводит одну наличную оплату продажи. Предоплата заказа не дублируется, банк исключён, нулевой долг не создаёт фиктивную кассовую запись.

Статические вызовы: `CashTransaction.objects.create`, `CashTransaction.objects.select_for_update`, `CashTransaction.objects.select_for_update().filter`, `CashTransaction.objects.select_for_update().filter(sale=sale, operation_type=CashTransaction.OperationType.SALE_PAYMENT).exists`, `ValidationError`, `_locked_register`, `getattr`, `logger.info`, `register.full_clean`, `register.save`, `sale.creditor_movements.filter`, `sale.creditor_movements.filter(kind='sale_debt' if sale.debt_charge_amount else 'offset', amount=shortfall, delta=shortfall, reversal_of__isnull=True, creditor_id=sale.partner.creditor_id).exists`.

### `refund_sale_payment(*, sale, actor, comment)`

Исходник: `cash/services.py:162`.

Декораторы: `transaction.atomic`.

Возвращает сумму исходной кассовой оплаты один раз. Недостаток наличных блокирует полную отмену; отдельный произвольный deposit не входит в этот возврат.

Статические вызовы: `CashTransaction.objects.create`, `CashTransaction.objects.select_for_update`, `CashTransaction.objects.select_for_update().filter`, `CashTransaction.objects.select_for_update().filter(sale=sale, operation_type=CashTransaction.OperationType.SALE_PAYMENT).first`, `CashTransaction.objects.select_for_update().filter(sale=sale, operation_type=CashTransaction.OperationType.SALE_REFUND).first`, `ValidationError`, `_comment`, `_locked_register`, `getattr`, `logger.info`, `logger.warning`, `register.full_clean`, `register.save`.

### `deposit_safe(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:207`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.get`, `CashTransaction.objects.create`, `_comment`, `_existing_operation`, `_locked_safe`, `_operation_key`, `_positive_amount`, `logger.info`, `safe.full_clean`, `safe.save`.

### `collect_safe(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:232`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.get`, `CashTransaction.objects.create`, `ValidationError`, `_comment`, `_existing_operation`, `_locked_safe`, `_operation_key`, `_positive_amount`, `logger.info`, `safe.full_clean`, `safe.save`.

### `transfer_cash_to_safe(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:259`.

Декораторы: `transaction.atomic`.

Переносит наличные между двумя балансами и единым журналом в одной транзакции; выручку не создаёт.

Статические вызовы: `CashTransaction.objects.create`, `ValidationError`, `_comment`, `_existing_operation`, `_locked_register`, `_locked_safe`, `_operation_key`, `_positive_amount`, `logger.info`, `register.full_clean`, `register.save`, `safe.full_clean`, `safe.save`.

### `transfer_safe_to_cash(*, actor, warehouse_id, amount, comment, operation_key=None)`

Исходник: `cash/services.py:290`.

Декораторы: `transaction.atomic`.

Обратный перевод сейф -> касса, атомарный и идемпотентный по ключу запроса.

Статические вызовы: `CashTransaction.objects.create`, `ValidationError`, `_comment`, `_existing_operation`, `_locked_register`, `_locked_safe`, `_operation_key`, `_positive_amount`, `logger.info`, `register.full_clean`, `register.save`, `safe.full_clean`, `safe.save`.

## `cash/signals.py`

Реакции на сохранение моделей и запуск связанных действий кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django.db.models.signals`, `django.dispatch`, `models`, `warehouse.models`.

### `ensure_cash_register(sender, instance, raw=False, **kwargs)`

Исходник: `cash/signals.py:13`.

Декораторы: `receiver(post_save, sender=Warehouse, dispatch_uid='cash.ensure_register_for_warehouse')`.

Создаёт нулевые хранилища наличных вместе со складом.

Статические вызовы: `CashRegister.objects.get_or_create`, `Safe.objects.get_or_create`, `receiver`.

## `cash/urls.py`

Именованные HTTP-маршруты приложения кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `django.urls`.

## `cash/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю кассы и сейфа.

Наличные отделены от банка/долга; баланс согласуется с журналом в одной транзакции.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.shortcuts`, `forms`, `models`, `services`, `warehouse.models`.

### `_cash_destination(request, warehouse)`

Исходник: `cash/views.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `redirect`, `request.user.has_perm`.

### `register_detail(request, warehouse_pk)`

Исходник: `cash/views.py:43`.

Декораторы: `permission_required_any('cash.view_cash_register', 'cash.view_cash_history', 'cash.view_safe')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `permission_required_any`, `register.transactions.select_related`, `render`, `request.user.has_perm`, `transactions.filter`.

### `_operation(request, warehouse_pk, *, service, title, permission, storage_label='Касса', requires_safe_view=False)`

Исходник: `cash/views.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashOperationForm`, `CashTransaction.objects.filter`, `CashTransaction.objects.filter(operation_key=operation_key).exists`, `PermissionDenied`, `_cash_destination`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `get_object_or_404`, `messages.info`, `messages.success`, `render`, `request.user.has_perm`, `service`, `uuid.uuid4`.

### `deposit(request, warehouse_pk)`

Исходник: `cash/views.py:117`.

Декораторы: `permission_required_any('cash.deposit_cash')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

### `collect(request, warehouse_pk)`

Исходник: `cash/views.py:124`.

Декораторы: `permission_required_any('cash.collect_cash')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

### `safe_deposit(request, warehouse_pk)`

Исходник: `cash/views.py:131`.

Декораторы: `permission_required_any('cash.deposit_safe')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

### `safe_collect(request, warehouse_pk)`

Исходник: `cash/views.py:140`.

Декораторы: `permission_required_any('cash.collect_safe')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

### `cash_to_safe(request, warehouse_pk)`

Исходник: `cash/views.py:149`.

Декораторы: `permission_required_any('cash.transfer_cash_to_safe')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

### `safe_to_cash(request, warehouse_pk)`

Исходник: `cash/views.py:158`.

Декораторы: `permission_required_any('cash.transfer_safe_to_cash')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_operation`, `permission_required_any`.

## `catalog/admin.py`

Регистрация моделей и разрешённых действий в Django Admin номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry.

Импорты: `audit`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.urls`, `django.utils.html`, `models`, `product_fields`, `product_identifiers`.

### `ProductAdminMixin.save_formset(self, request, form, formset, change)`

Исходник: `catalog/admin.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `after.items`, `before.items`, `changes.append`, `field_change`, `form.instance.barcodes.all`, `record_product_changes`, `super`, `super().save_formset`.

### `ProductAdminMixin.has_delete_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:68`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:72`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().has_change_permission`.

### `ProductAdminMixin.get_actions(self, request)`

Исходник: `catalog/admin.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `actions.pop`, `super`, `super().get_actions`.

### `ProductAdminMixin.get_readonly_fields(self, request, obj=None)`

Исходник: `catalog/admin.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `field_permissions_for`, `field_permissions_for(self.model).items`, `readonly.append`, `request.user.has_perm`, `tuple`.

### `ProductAdminMixin.save_model(self, request, obj, form, change)`

Исходник: `catalog/admin.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `card_fields_for`, `changed_snapshots`, `ensure_product_article`, `field_change`, `isinstance`, `logger.exception`, `obj._meta.get_field`, `product_snapshot`, `record_product_changes`, `snapshot.items`, `str`, `super`, `super().save_model`, `transaction.atomic`, `type`, `type(obj).objects.select_for_update`, `type(obj).objects.select_for_update().select_related`, `type(obj).objects.select_for_update().select_related(*related_fields).get`.

### `GameSeriesAdmin.get_queryset(self, request)`

Исходник: `catalog/admin.py:161`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Count`, `super`, `super().get_queryset`, `super().get_queryset(request).annotate`.

### `GameSeriesAdmin.cd_count(self, obj)`

Исходник: `catalog/admin.py:165`.

Декораторы: `admin.display(description='CD')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `admin.display`, `format_html`, `reverse`.

### `BarcodeInlineBase._permission(self, obj)`

Исходник: `catalog/admin.py:175`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `BarcodeInlineBase.has_add_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:179`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `self._permission`.

### `BarcodeInlineBase.has_change_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:184`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.has_add_permission`.

### `BarcodeInlineBase.has_delete_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:187`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.has_add_permission`.

### `ProductRemovalEventAdmin.has_add_permission(self, request)`

Исходник: `catalog/admin.py:231`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductRemovalEventAdmin.has_change_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:234`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductRemovalEventAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:237`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductFieldChangeInline.has_add_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:248`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadonlyAuditAdminMixin.has_add_permission(self, request)`

Исходник: `catalog/admin.py:253`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadonlyAuditAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:256`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadonlyAuditAdminMixin.has_delete_permission(self, request, obj=None)`

Исходник: `catalog/admin.py:259`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductChangeEventAdmin.product_display(self, obj)`

Исходник: `catalog/admin.py:280`.

Декораторы: `admin.display(description='Товар')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `admin.display`.

### `SystemProductAdmin.barcode_value(self, obj)`

Исходник: `catalog/admin.py:309`.

Декораторы: `admin.display(description='Штрихкод')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `admin.display`.

### `SystemProductAdmin.barcode_image(self, obj)`

Исходник: `catalog/admin.py:313`.

Декораторы: `admin.display(description='Code128 для печати')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `admin.display`, `format_html`, `render_barcode_svg_data_url`.

## `catalog/apps.py`

Конфигурация приложения и его регистрация в Django номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry.

Импорты: `django.apps`.

## `catalog/audit.py`

Неизменяемые снимки изменений карточек CD и Tech.

Импорты: `decimal`, `models`.

### `snapshot_value(instance, field_name)`

Исходник: `catalog/audit.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `instance._meta.get_field`, `isinstance`, `str`.

### `product_snapshot(instance, field_names)`

Исходник: `catalog/audit.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `snapshot_value`.

### `changed_snapshots(instance, before, field_names)`

Исходник: `catalog/audit.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `changes.append`, `instance._meta.get_field`, `snapshot_value`, `str`.

### `stock_change(*, warehouse, old_quantity, new_quantity)`

Исходник: `catalog/audit.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`.

### `field_change(*, field_name, field_label, old_value, new_value)`

Исходник: `catalog/audit.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`.

### `record_product_changes(*, actor, instance, changes, source, action_kind='', action_object_id=None, action_label='')`

Исходник: `catalog/audit.py:56`.

Записывает одну пользовательскую операцию и её изменения в текущей транзакции.

Статические вызовы: `ProductChangeEvent.objects.create`, `ProductFieldChange`, `ProductFieldChange.objects.bulk_create`, `TypeError`, `isinstance`.

## `catalog/game_codes.py`

Коды дисков PlayStation: нормализация, обязательность при приёмке и аудит.

Импорты: `audit`, `django.core.exceptions`, `django.db`, `models`.

### `requires_game_codes(product)`

Исходник: `catalog/game_codes.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`, `product.platform.name.casefold`, `re.sub`.

### `normalize_game_codes(value)`

Исходник: `catalog/game_codes.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD._meta.get_field`, `ValidationError`, `codes.append`, `len`, `match[1].upper`, `part.strip`, `re.fullmatch`, `re.split`, `str`.

### `display_game_codes(product)`

Исходник: `catalog/game_codes.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `dict.fromkeys`, `getattr`, `part.strip`, `re.split`.

### `validate_supply_game_codes(products)`

Исходник: `catalog/game_codes.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `ValidationError`, `product.cusa_ppsa_code.strip`, `requires_game_codes`.

### `set_game_codes(*, actor, product_id, value)`

Исходник: `catalog/game_codes.py:48`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().select_for_update`, `CD.objects.active().select_for_update().get`, `PermissionDenied`, `ValidationError`, `actor.has_perm`, `field_change`, `normalize_game_codes`, `product.full_clean`, `product.save`, `record_product_changes`.

## `catalog/game_series_classifier.py`

Детерминированная первичная классификация исторического каталога CD.

Не вызывается при обычном создании/редактировании товара. Не обращается к сети.
Незнакомое название сохраняется как самостоятельная серия, а не угадывается
по первому слову. Известные франшизы перечислены явно и в приоритетном порядке.

Импорты: `models`.

### `clean_game_title(value)`

Исходник: `catalog/game_series_classifier.py:430`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_CODE.sub`, `_EDITION.sub`, `_EDITION.sub('', title).strip`, `_LANGUAGE.sub`, `_PLATFORM.sub`, `normalize_game_series_name`, `normalize_game_series_name(title).strip`, `range`, `re.sub`, `str`, `str.maketrans`, `title.replace`, `title.strip`, `title.translate`, `unicodedata.normalize`.

### `classify_game_title(value)`

Исходник: `catalog/game_series_classifier.py:453`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `alias.rstrip`, `any`, `clean_game_title`, `folded.startswith`, `normalize_game_series_name`, `title.casefold`.

## `catalog/management/commands/backfill_product_newness.py`

План и безопасное однократное присвоение исторического статуса новинки.

Импорты: `catalog.newness_backfill`, `django.conf`, `django.contrib.auth`, `django.core.exceptions`, `django.core.management.base`, `django.utils`, `django.utils.dateparse`, `pathlib`.

### `Command.add_arguments(self, parser)`

Исходник: `catalog/management/commands/backfill_product_newness.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `mode.add_argument`, `parser.add_argument`, `parser.add_mutually_exclusive_group`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/backfill_product_newness.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `CommandError`, `Path`, `apply_newness_backfill`, `backup.execute`, `backup.execute('PRAGMA integrity_check').fetchone`, `backup_dir.mkdir`, `bool`, `build_newness_backfill`, `db_path.as_posix`, `get_user_model`, `get_user_model().objects.filter`, `get_user_model().objects.filter(pk=options['user']).exists`, `json.dumps`, `len`, `parse_datetime`, `plan.update`, `plan['counts'].get`, `self.stdout.write`, `source.backup`, `sqlite3.connect`, `str`, `target.parent.mkdir`, `target.write_text`, `timezone.is_naive`, `timezone.now`, `timezone.now().strftime`, `web_creation_evidence`.

## `catalog/management/commands/classify_game_series.py`

Первичная классификация исторической базы CD без сетевых запросов.

Импорты: `catalog.game_series_classifier`, `catalog.models`, `collections`, `datetime`, `django.conf`, `django.core.management.base`, `django.db`, `pathlib`.

### `Command.add_arguments(self, parser)`

Исходник: `catalog/management/commands/classify_game_series.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/classify_game_series.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().filter`, `CD.objects.active().filter(game_series__isnull=True).count`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform', 'game_series').order_by`, `CD.objects.bulk_update`, `CommandError`, `Counter`, `GameSeries.objects.all`, `GameSeries.objects.create`, `assignments.append`, `bool`, `classify_game_title`, `csv.DictWriter`, `datetime.now`, `datetime.now(utc_timezone.utc).strftime`, `dict`, `json.dumps`, `len`, `list`, `name.casefold`, `normalize_game_series_name`, `options['report_dir'].resolve`, `report_dir.mkdir`, `report_path.open`, `row['classifier_suggestion'].casefold`, `row['game_series'].casefold`, `row['old_game_series'].casefold`, `rows.append`, `rows[0].keys`, `self.stdout.write`, `str`, `sum`, `target.casefold`, `transaction.atomic`, `writer.writeheader`, `writer.writerows`.

## `catalog/management/commands/ensure_system_products.py`

Идемпотентное создание системных цифровых/расходных позиций с сохранением выданных штрихкодов.

Импорты: `catalog.system_products`, `django.core.management.base`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/ensure_system_products.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ensure_system_products`, `self.stdout.write`.

## `catalog/management/commands/import_catalog_names.py`

Ручной импорт номенклатуры из внешнего файла; не запускать повторно как процедуру развёртывания.

Импорты: `catalog.models`, `collections`, `dataclasses`, `decimal`, `difflib`, `django.core.management.base`, `django.db`, `functools`, `openpyxl`, `pathlib`, `warehouse.models`.

### `_base_normalize(value)`

Исходник: `catalog/management/commands/import_catalog_names.py:69`.

Декораторы: `lru_cache(maxsize=None)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `lru_cache`, `re.sub`, `str`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', str(value or '')).strip`, `unicodedata.normalize('NFKC', str(value or '')).strip().casefold`, `unicodedata.normalize('NFKC', str(value or '')).strip().casefold().replace`, `value.replace`, `value.replace('&', ' and ').replace`, `value.split`, `value.translate`.

### `_cd_key(value)`

Исходник: `catalog/management/commands/import_catalog_names.py:82`.

Декораторы: `lru_cache(maxsize=None)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_base_normalize`, `lru_cache`, `re.sub`.

### `_soft_key(value, *, cd=False)`

Исходник: `catalog/management/commands/import_catalog_names.py:89`.

Декораторы: `lru_cache(maxsize=None)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_base_normalize`, `_cd_key`, `lru_cache`, `re.sub`, `value.split`.

### `_numbers(value)`

Исходник: `catalog/management/commands/import_catalog_names.py:98`.

Декораторы: `lru_cache(maxsize=None)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `char.isdigit`, `lru_cache`, `re.sub`, `tuple`, `value.split`.

### `_edition_words(value)`

Исходник: `catalog/management/commands/import_catalog_names.py:117`.

Декораторы: `lru_cache(maxsize=None)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_soft_key`, `_soft_key(value).split`, `lru_cache`.

### `_strict_signature(value, *, cd=False, soft=False)`

Исходник: `catalog/management/commands/import_catalog_names.py:121`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_base_normalize`, `_cd_key`, `_soft_key`, `any`, `char.isdigit`, `frozenset`, `normalized.split`, `signature.add`, `signature.update`, `str`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', str(value)).casefold`, `unicodedata.normalize('NFKC', str(value)).casefold().replace`.

### `_catalog_codes(value)`

Исходник: `catalog/management/commands/import_catalog_names.py:134`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_base_normalize`, `frozenset`, `re.findall`.

### `_similarity(left, right, *, cd=False)`

Исходник: `catalog/management/commands/import_catalog_names.py:139`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SequenceMatcher`, `SequenceMatcher(None, a, b).ratio`, `_soft_key`.

### `_is_same_product(left, right, *, cd=False, existing=False)`

Исходник: `catalog/management/commands/import_catalog_names.py:147`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SequenceMatcher`, `SequenceMatcher(None, ' '.join(sorted(tokens_a)), ' '.join(sorted(tokens_b))).ratio`, `SequenceMatcher(None, soft_a, soft_b).ratio`, `_base_normalize`, `_catalog_codes`, `_cd_key`, `_soft_key`, `_strict_signature`, `len`, `max`, `min`, `set`, `soft_a.split`, `soft_b.split`, `sorted`.

### `_money(value, row)`

Исходник: `catalog/management/commands/import_catalog_names.py:182`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `Decimal(str(value)).quantize`, `str`.

### `_read_cd(path)`

Исходник: `catalog/management/commands/import_catalog_names.py:194`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SourceItem`, `_money`, `enumerate`, `items.append`, `load_workbook`, `missing_cost.append`, `next`, `sheet.iter_rows`, `str`, `str(raw_name).split`, `workbook.close`.

### `_tech_brand(row, name)`

Исходник: `catalog/management/commands/import_catalog_names.py:220`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_base_normalize`, `any`, `low.startswith`.

### `_tech_type(row, name)`

Исходник: `catalog/management/commands/import_catalog_names.py:273`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_base_normalize`, `any`, `low.endswith`, `low.startswith`, `range`, `str`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', str(name)).casefold`, `unicodedata.normalize('NFKC', str(name)).casefold().replace`.

### `_read_tech(path)`

Исходник: `catalog/management/commands/import_catalog_names.py:351`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SourceItem`, `_money`, `_tech_brand`, `_tech_type`, `enumerate`, `items.append`, `load_workbook`, `missing_cost.append`, `sheet.iter_rows`, `str`, `str(raw_name).split`, `workbook.close`.

### `_dedupe_source(items, *, cd)`

Исходник: `catalog/management/commands/import_catalog_names.py:376`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SourceItem`, `_base_normalize`, `_cd_key`, `_is_same_product`, `_soft_key`, `abs`, `candidates.add`, `candidates.update`, `defaultdict`, `duplicate_rows.append`, `enumerate`, `exact_index.get`, `groups.append`, `len`, `set`, `soft.split`, `sorted`, `token_index[class_key, token].add`.

### `_match_existing(items, existing, *, cd)`

Исходник: `catalog/management/commands/import_catalog_names.py:421`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TECH_MATCH_SKU_BY_ROW.get`, `_base_normalize`, `_catalog_codes`, `_cd_key`, `_is_same_product`, `_similarity`, `_soft_key`, `abs`, `ambiguous.append`, `assigned_items.add`, `assigned_objects.add`, `candidate_indices.update`, `defaultdict`, `enumerate`, `exact.append`, `exact.sort`, `exact_index[class_key, base].add`, `exact_index[class_key, soft].add`, `len`, `matches.append`, `pools[class_key].append`, `proposals.append`, `quality`, `set`, `soft.split`, `sorted`, `tech_by_sku.get`, `token_index[class_key, token].add`.

### `_require_references(model, names, label)`

Исходник: `catalog/management/commands/import_catalog_names.py:482`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CommandError`, `model.objects.active`, `model.objects.active().filter`, `set`, `sorted`.

### `Command.add_arguments(self, parser)`

Исходник: `catalog/management/commands/import_catalog_names.py:493`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/import_catalog_names.py:499`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.create`, `CDWarehouseStock`, `CDWarehouseStock.objects.bulk_create`, `CommandError`, `Counter`, `Counter((x.classification for x in new_cd)).items`, `Counter((x.classification for x in new_tech)).items`, `Counter((x.secondary for x in new_tech)).items`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.create`, `TechWarehouseStock`, `TechWarehouseStock.objects.bulk_create`, `Warehouse.objects.all`, `_dedupe_source`, `_match_existing`, `_read_cd`, `_read_tech`, `_require_references`, `len`, `list`, `options['cd_xlsx'].resolve`, `options['tech_xlsx'].resolve`, `path.is_file`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `sorted`, `transaction.atomic`.

## `catalog/management/commands/import_current_inventory.py`

Явный перенос исходного наличия из файла; меняет рабочие данные только по отдельному поручению.

Импорты: `accounts.models`, `catalog.models`, `collections`, `consignment.models`, `consignment.services`, `dataclasses`, `decimal`, `django.core.management.base`, `django.db`, `django.db.models`, `openpyxl`, `partners.models`, `pathlib`, `warehouse.models`.

### `_decimal(value, *, row, label, allow_blank=False)`

Исходник: `catalog/management/commands/import_current_inventory.py:100`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `Decimal(str(value)).quantize`, `str`.

### `_quantity(value, *, row, label='Наличие')`

Исходник: `catalog/management/commands/import_current_inventory.py:114`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `int`, `str`.

### `_tech_reference(row, name)`

Исходник: `catalog/management/commands/import_current_inventory.py:127`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`.

### `_parse_workbook(path)`

Исходник: `catalog/management/commands/import_current_inventory.py:191`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD_PLATFORM_BY_BLOCK.get`, `CommandError`, `ConsignmentRow`, `Counter`, `Decimal`, `MainRow`, `_decimal`, `_quantity`, `_tech_reference`, `consignment_rows.append`, `grouped.values`, `item.name.casefold`, `len`, `list`, `load_workbook`, `main_rows.append`, `match.groups`, `names.items`, `normalized.append`, `presence_pattern.match`, `range`, `re.compile`, `sheet.cell`, `str`, `str(raw_name).strip`, `str(sheet.cell(row, 3).value or '').strip`, `workbook.close`.

### `_require_exact(model, names, label)`

Исходник: `catalog/management/commands/import_current_inventory.py:286`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CommandError`, `model.objects.active`, `model.objects.active().filter`, `set`, `sorted`.

### `_extract_code(name)`

Исходник: `catalog/management/commands/import_current_inventory.py:294`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `match.group`, `re.search`.

### `Command.add_arguments(self, parser)`

Исходник: `catalog/management/commands/import_current_inventory.py:302`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/import_current_inventory.py:307`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD.objects.count`, `CD.objects.create`, `CDConsignmentStock.objects.aggregate`, `CDConsignmentStock.objects.count`, `CDWarehouseStock.objects.aggregate`, `CDWarehouseStock.objects.count`, `CDWarehouseStock.objects.create`, `CommandError`, `ConsignmentMovement.objects.count`, `ProductChangeEvent.objects.count`, `Sum`, `Tech.objects.count`, `Tech.objects.create`, `TechConsignmentStock.objects.aggregate`, `TechConsignmentStock.objects.count`, `TechWarehouseStock.objects.aggregate`, `TechWarehouseStock.objects.count`, `TechWarehouseStock.objects.create`, `User.objects.get`, `Warehouse.objects.count`, `Warehouse.objects.get`, `_extract_code`, `_parse_workbook`, `_require_exact`, `defaultdict`, `isinstance`, `len`, `lines.append`, `nonempty.items`, `options['xlsx'].resolve`, `path.is_file`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `sorted`, `sum`, `transaction.atomic`, `transfer_many_to_consignment`.

## `catalog/management/commands/import_wholesale_prices.py`

Явный импорт оптовых цен; не является миграцией и требует проверки источника/области.

Импорты: `accounts.models`, `catalog.models`, `dataclasses`, `decimal`, `django.core.management.base`, `django.db`, `openpyxl`, `pathlib`, `pricing.services`.

### `_normalize(value)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:48`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `re.findall`, `str`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', str(value)).casefold`, `unicodedata.normalize('NFKC', str(value)).casefold().replace`.

### `_price(value, row)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `Decimal(str(value)).quantize`, `str`.

### `_load_source(path)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `_price`, `load_workbook`, `range`, `rows.append`, `sheet.cell`, `str`, `str(raw_name or '').strip`, `workbook.close`.

### `_resolve_rows(source_rows)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:88`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `MANUAL_SKU_BY_SOURCE_ROW.get`, `PriceRow`, `_normalize`, `by_normalized_name[kind].get`, `by_normalized_name[kind].setdefault`, `by_normalized_name[kind].setdefault(_normalize(product.name), []).append`, `len`, `list`, `model.objects.active`, `models.items`, `models[kind].objects.active`, `models[kind].objects.active().get`, `products.items`, `resolved.append`.

### `Command.add_arguments(self, parser)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:126`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/import_wholesale_prices.py:131`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `CommandError`, `User.objects.get`, `_load_source`, `_resolve_rows`, `errors.append`, `len`, `max`, `min`, `model.objects.values_list`, `model.objects.values_list('wholesale_price', flat=True).get`, `options['xlsx'].resolve`, `path.is_file`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `transaction.atomic`, `update_product_prices`.

## `catalog/management/commands/verify_inventory.py`

Диагностика физического склада и суммы партий реализации; команда ничего не исправляет.

Импорты: `catalog.models`, `django.core.management.base`, `django.db.models`, `warehouse.models`.

### `Command.handle(self, *args, **options)`

Исходник: `catalog/management/commands/verify_inventory.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Sum`, `errors.append`, `len`, `model.objects.annotate`, `model.objects.filter`, `self.stderr.write`, `self.stdout.write`, `self.style.SUCCESS`.

## `catalog/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry.

Импорты: `decimal`, `django.conf`, `django.core.exceptions`, `django.core.validators`, `django.db`, `django.db.models.functions`, `django.urls`, `django.utils`, `newness`, `packaging_defaults`, `pathlib`, `profit_defaults`, `uuid`.

### `NamedReference.__str__(self)`

Исходник: `catalog/models.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `normalize_game_series_name(value)`

Исходник: `catalog/models.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `name.translate`, `re.sub`, `re.sub('\\s+', ' ', name).strip`, `str`, `str.maketrans`, `unicodedata.normalize`.

### `GameSeries.clean(self)`

Исходник: `catalog/models.py:90`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GameSeries.objects.filter`, `GameSeries.objects.filter(normalized_name=self.normalized_name).exclude`, `GameSeries.objects.filter(normalized_name=self.normalized_name).exclude(pk=self.pk).exists`, `ValidationError`, `normalize_game_series_name`, `self.name.casefold`, `super`, `super().clean`.

### `GameSeries.save(self, *args, **kwargs)`

Исходник: `catalog/models.py:99`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `kwargs.get`, `self.clean`, `set`, `super`, `super().save`.

### `GameSeries.__str__(self)`

Исходник: `catalog/models.py:105`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductQuerySet.active(self)`

Исходник: `catalog/models.py:110`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.filter`.

### `_product_image_extension(filename)`

Исходник: `catalog/models.py:114`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `Path(filename or '').suffix.lower`.

### `product_title_image_upload_to(instance, filename)`

Исходник: `catalog/models.py:119`.

Хранит титульные фото отдельно по типу и ID товара.

Статические вызовы: `_product_image_extension`, `uuid4`.

### `product_gallery_image_upload_to(instance, filename)`

Исходник: `catalog/models.py:127`.

Хранит галереи отдельно от титульного изображения.

Статические вызовы: `_product_image_extension`, `uuid4`.

### `ProductBase.__str__(self)`

Исходник: `catalog/models.py:214`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductBase.__init__(self, *args, **kwargs)`

Исходник: `catalog/models.py:217`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `kwargs.pop`, `super`, `super().__init__`.

### `ProductBase.barcode(self)`

Исходник: `catalog/models.py:224`.

Декораторы: `property`.

Первый штрихкод для старых потребителей, ожидающих одно значение.

Статические вызовы: `self.barcodes.order_by`, `self.barcodes.order_by('id').values_list`, `self.barcodes.order_by('id').values_list('value', flat=True).first`, `str`, `str(self._pending_legacy_barcode or '').strip`.

### `ProductBase.barcode(self, value)`

Исходник: `catalog/models.py:233`.

Декораторы: `barcode.setter`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `str(value or '').strip`.

### `ProductBase.save(self, *args, **kwargs)`

Исходник: `catalog/models.py:236`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.create`, `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(**lookup).delete`, `bool`, `fill_new_product_desired_profit`, `fill_new_product_dimensions`, `isinstance`, `kwargs.get`, `newness_expiry`, `set`, `str`, `str(pending or '').strip`, `str(pending).strip`, `super`, `super().save`, `timezone.now`, `transaction.atomic`.

### `ProductBase.clean(self)`

Исходник: `catalog/models.py:268`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `fill_new_product_desired_profit`, `fill_new_product_dimensions`, `getattr`, `newness_expiry`, `size.is_finite`, `str`, `str(self.sku or '').strip`, `super`, `super().clean`.

### `ProductBase.is_new(self)`

Исходник: `catalog/models.py:287`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `timezone.now`.

### `CD.clean(self)`

Исходник: `catalog/models.py:309`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().clean`.

### `ProductImage.product(self)`

Исходник: `catalog/models.py:440`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductImage.clean(self)`

Исходник: `catalog/models.py:443`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `super`, `super().clean`.

### `ProductImage.save(self, *args, **kwargs)`

Исходник: `catalog/models.py:457`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.clean`, `super`, `super().save`.

### `ProductImage.__str__(self)`

Исходник: `catalog/models.py:461`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_image_kind_display`.

### `SystemProduct.name(self)`

Исходник: `catalog/models.py:507`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_kind_display`.

### `SystemProduct.__str__(self)`

Исходник: `catalog/models.py:510`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SystemProduct.delete(self, *args, **kwargs)`

Исходник: `catalog/models.py:513`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `BarcodeRegistry.product(self)`

Исходник: `catalog/models.py:558`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `BarcodeRegistry.clean(self)`

Исходник: `catalog/models.py:563`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `str`, `str(self.value or '').strip`, `super`, `super().clean`.

### `BarcodeRegistry.save(self, *args, **kwargs)`

Исходник: `catalog/models.py:582`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `self.clean`, `super`, `super().save`, `type`, `type(self).objects.filter`, `type(self).objects.filter(pk=self.pk).values`, `type(self).objects.filter(pk=self.pk).values('system_product_id', 'value', 'product_kind').first`.

### `BarcodeRegistry.delete(self, *args, **kwargs)`

Исходник: `catalog/models.py:593`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `super`, `super().delete`.

### `BarcodeRegistry.__str__(self)`

Исходник: `catalog/models.py:598`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductChangeEvent.product(self)`

Исходник: `catalog/models.py:691`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductChangeEvent.__str__(self)`

Исходник: `catalog/models.py:694`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.created_at.strftime`, `self.get_product_kind_display`.

### `ProductChangeEvent.product_id(self)`

Исходник: `catalog/models.py:699`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductChangeEvent.executor_display(self)`

Исходник: `catalog/models.py:703`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_source_display`.

### `ProductChangeEvent.action_url(self)`

Исходник: `catalog/models.py:712`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `reverse`, `{self.ActionKind.SALE: 'sales:detail', self.ActionKind.WAREHOUSE_TRANSFER: 'warehouse:transfer_detail', self.ActionKind.CONSIGNMENT: 'consignment:movement_detail', self.ActionKind.SUPPLY: 'supplies:detail', self.ActionKind.SUPPLY_FINALIZATION: 'supplies:detail'}.get`.

### `ProductFieldChange.__str__(self)`

Исходник: `catalog/models.py:745`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `catalog/newness.py`

Календарный срок новинки от неизменной даты создания карточки.

Импорты: `django.core.exceptions`, `django.utils`.

### `newness_expiry(created_at, months)`

Исходник: `catalog/newness.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `calendar.monthrange`, `divmod`, `isinstance`, `local.replace`, `min`, `timezone.is_naive`, `timezone.localtime`.

### `customer_product_name(name, product, *, at=None)`

Исходник: `catalog/newness.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `timezone.now`.

## `catalog/newness_backfill.py`

Обратное заполнение только при явном подтверждении создания через веб-форму.

Импорты: `audit`, `collections`, `datetime`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `newness`, `pathlib`.

### `previous_calendar_month(value)`

Исходник: `catalog/newness_backfill.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `calendar.monthrange`, `divmod`, `local.replace`, `min`, `timezone.localtime`.

### `web_creation_evidence(directory)`

Исходник: `catalog/newness_backfill.py:25`.

Строгая цепочка одного журнала: создание → POST 302 → GET нужной карточки 200.

Статические вызовы: `'\n'.join`, `'\n'.join((line, request, lines[detail_index])).encode`, `(opened - requested).total_seconds`, `(requested - created).total_seconds`, `Path`, `ValidationError`, `created.isoformat`, `creation.search`, `datetime.strptime`, `defaultdict`, `enumerate`, `found[kind, pk].append`, `hashlib.sha256`, `hashlib.sha256('\n'.join((line, request, lines[detail_index])).encode('utf-8')).hexdigest`, `int`, `len`, `min`, `path.read_bytes`, `range`, `raw.decode`, `raw.decode('cp1251', errors='replace').splitlines`, `raw.decode('utf-8').splitlines`, `re.compile`, `re.search`, `root.glob`, `root.is_dir`, `sorted`, `str`, `timezone.make_aware`.

### `build_newness_backfill(*, user_id, as_of, web_evidence=None)`

Исходник: `catalog/newness_backfill.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(event.created_at - datetime.fromisoformat(proof['logged_at'])).total_seconds`, `Counter`, `ProductChangeEvent.objects.filter`, `ProductChangeEvent.objects.filter(field_changes__field_name='created').distinct`, `ProductChangeEvent.objects.filter(field_changes__field_name='created').distinct().order_by`, `ValidationError`, `abs`, `bool`, `created_at.isoformat`, `datetime.fromisoformat`, `defaultdict`, `dict`, `events[event.product_kind, event.product_id].append`, `len`, `model.objects.order_by`, `previous_calendar_month`, `product.created_at.isoformat`, `product.newness_backfill_checked_at.isoformat`, `product.newness_until.isoformat`, `rows.append`, `since.isoformat`, `timezone.is_naive`, `timezone.localtime`, `timezone.localtime(as_of).isoformat`, `web_evidence.get`.

### `apply_newness_backfill(plan)`

Исходник: `catalog/newness_backfill.py:143`.

Декораторы: `transaction.atomic`.

Неподтверждённые карточки не изменяются, включая служебные отметки.

Статические вызовы: `ValidationError`, `changed.append`, `created_at.isoformat`, `datetime.fromisoformat`, `field_change`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `newness_expiry`, `product.created_at.isoformat`, `product.full_clean`, `product.newness_until.isoformat`, `product.save`, `record_product_changes`, `timezone.now`.

## `catalog/nomenclature_forms.py`

Явные формы карточек с серверной проверкой прав на каждое поле.

Импорты: `decimal`, `django`, `django.core.exceptions`, `django.forms`, `django.urls`, `models`, `partners.models`, `pricing.warnings`, `product_fields`, `removal`, `warehouse.models`, `warehouse.storage_locations`.

### `BulkProductDeleteForm.clean_selection(self)`

Исходник: `catalog/nomenclature_forms.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize_removal_selection`.

### `BulkProductDeleteForm.clean(self)`

Исходник: `catalog/nomenclature_forms.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `data.get`, `self.add_error`, `super`, `super().clean`, `token.startswith`.

### `product_version(instance)`

Исходник: `catalog/nomenclature_forms.py:46`.

Возвращает optimistic-lock token для карточки и её складских остатков.

Статические вызовы: `Decimal`, `format`, `getattr`, `hasattr`, `hashlib.sha256`, `hashlib.sha256(payload.encode('utf-8')).hexdigest`, `instance._meta.get_field`, `instance.barcodes.order_by`, `instance.barcodes.order_by('id').values_list`, `instance.supplier_exclusions.order_by`, `instance.supplier_exclusions.order_by('supplier_id').values_list`, `instance.warehouse_stocks.order_by`, `instance.warehouse_stocks.order_by('warehouse_id').prefetch_related`, `isinstance`, `json.dumps`, `list`, `payload.encode`, `stock.storage_assignments.all`, `str`.

### `SupplierExclusionChoiceField.label_from_instance(self, supplier)`

Исходник: `catalog/nomenclature_forms.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductOptionsForm.__init__(self, *args, user=None, **kwargs)`

Исходник: `catalog/nomenclature_forms.py:104`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Supplier.objects.all`, `len`, `list`, `self.instance.change_events.filter`, `self.instance.change_events.filter(field_changes__field_name='created').distinct`, `self.instance.change_events.filter(field_changes__field_name='created').distinct().order_by`, `self.instance.supplier_exclusions.values_list`, `str`, `super`, `super().__init__`, `user.has_perm`.

### `ProductOptionsForm.clean(self)`

Исходник: `catalog/nomenclature_forms.py:127`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `data.pop`, `int`, `self.add_error`, `super`, `super().clean`.

### `ProductCardFormMixin.__init__(self, *args, user, **kwargs)`

Исходник: `catalog/nomenclature_forms.py:152`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `(attrs.get('class', '') + ' price-warning').strip`, `Decimal`, `MARKUP_FOR_PRICE.items`, `Warehouse.objects.all`, `attrs.get`, `bool`, `compatible.setlist`, `forms.CharField`, `forms.IntegerField`, `forms.NumberInput`, `forms.TextInput`, `getattr`, `hasattr`, `instance.supplier_exclusions.values_list`, `isinstance`, `kwargs.get`, `list`, `money`, `price_warning`, `product_version`, `reverse`, `self.allowed_fields.add`, `self.allowed_fields.clear`, `self.allowed_fields.update`, `self.field_permissions.items`, `self.fields['cost'].widget.attrs.update`, `self.fields[field_name].widget.attrs.setdefault`, `self.stock_fields.append`, `self.storage_location_fields.append`, `self.warehouse_field_pairs.append`, `self.warehouses_by_id.values`, `self[name].value`, `set`, `stock.storage_assignments.all`, `stock_model.objects.filter`, `stock_model.objects.filter(**{self.instance._meta.model_name: self.instance}).prefetch_related`, `stock_values.get`, `storage_location_values.get`, `str`, `str(self[name].value()).replace`, `submitted.copy`, `super`, `super().__init__`, `user.has_perm`, `value.is_finite`.

### `ProductCardFormMixin.clean(self)`

Исходник: `catalog/nomenclature_forms.py:293`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `ValidationError`, `labels.append`, `normalize_storage_location_list`, `self.add_error`, `self.instance._meta.get_field`, `sorted`, `str`, `super`, `super().clean`.

### `ProductCreateFormMixin.__init__(self, *args, **kwargs)`

Исходник: `catalog/nomenclature_forms.py:343`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.fields[field_name].widget.attrs.setdefault`, `super`, `super().__init__`.

### `TechCreateForm.__init__(self, *args, **kwargs)`

Исходник: `catalog/nomenclature_forms.py:362`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `ProductBarcodeForm.clean_value(self)`

Исходник: `catalog/nomenclature_forms.py:383`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `self.cleaned_data.get`, `str`, `str(self.cleaned_data.get('value') or '').strip`.

### `BaseProductBarcodeFormSet.__init__(self, *args, product=None, **kwargs)`

Исходник: `catalog/nomenclature_forms.py:393`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `BaseProductBarcodeFormSet.clean(self)`

Исходник: `catalog/nomenclature_forms.py:397`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(pk=barcode_id, **owner_filter).exists`, `BarcodeRegistry.objects.filter(value=value).first`, `ValidationError`, `any`, `form.cleaned_data.get`, `isinstance`, `seen.add`, `set`, `super`, `super().clean`, `values.append`.

### `barcode_formset(*, data=None, product=None)`

Исходник: `catalog/nomenclature_forms.py:438`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductBarcodeFormSet`, `product.barcodes.order_by`.

## `catalog/nomenclature_grouping.py`

Иерархия страницы номенклатуры для самой страницы и закупочных документов.

Импорты: `collections`, `product_ordering`.

### `get_nomenclature_grouping(tech_items, cd_items, *, product_of=lambda item: item)`

Исходник: `catalog/nomenclature_grouping.py:7`.

Сохраняет исходные строки, включая несколько распределений одного товара.

Статические вызовы: `OrderedDict`, `cd_groups.append`, `cd_order_key`, `len`, `pair[0].name.casefold`, `platforms.values`, `platforms[platform_id]['items'].append`, `product_of`, `series_groups.values`, `series_groups[series_id][1].append`, `sorted`, `tech_brand_groups`.

### `nomenclature_product_groups(tech_items, cd_items, *, product_of=lambda item: item)`

Исходник: `catalog/nomenclature_grouping.py:39`.

Группы закупочных Excel: Tech → бренд → тип; CD → платформа → товар.

Статические вызовы: `get_nomenclature_grouping`, `groups.append`.

## `catalog/nomenclature_services.py`

Атомарное редактирование карточек номенклатуры.

Импорты: `audit`, `dataclasses`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `nomenclature_forms`, `pricing.services`, `product_fields`, `product_identifiers`, `supplier_exclusions`, `warehouse.models`, `warehouse.storage_services`.

### `product_configuration(product_kind)`

Исходник: `catalog/nomenclature_services.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValueError`.

### `create_product(*, actor, product_kind, data, barcode_formset_instance=None, creation_source=CD.CreationSource.AUTOMATIC)`

Исходник: `catalog/nomenclature_services.py:55`.

Декораторы: `transaction.atomic`.

Атомарно создаёт номенклатурную карточку с нулевым системным состоянием и audit.

Статические вызовы: `BarcodeRegistry.objects.create`, `ValidationError`, `ValueError`, `barcode_changes.append`, `changes.extend`, `data.get`, `ensure_product_article`, `field_change`, `logger.info`, `model`, `product._meta.get_field`, `product.full_clean`, `product.save`, `product_snapshot`, `record_product_changes`, `save_barcode_formset`, `set_supplier_exclusions`, `snapshot.items`, `str`, `str(data.get('barcode') or '').strip`, `timezone.now`.

### `update_product_card(*, actor, product_kind, product_id, data, barcode_data=None)`

Исходник: `catalog/nomenclature_services.py:131`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `ProductUpdateResult`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().filter`, `Warehouse.objects.select_for_update().filter(pk__in=location_warehouse_ids).order_by`, `barcode_formset`, `barcode_formset_instance.has_changed`, `barcode_formset_instance.is_valid`, `bool`, `card_fields.append`, `changed_snapshots`, `changed_warehouses.append`, `clear_storage_locations_if_zero`, `data.copy`, `field.startswith`, `field_change`, `field_name.removeprefix`, `field_name.removeprefix('storage_location_').isdigit`, `field_name.startswith`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `form.save`, `form_class`, `form_data.keys`, `int`, `key.startswith`, `list`, `logger.exception`, `logger.info`, `logger.warning`, `model.objects.select_for_update`, `model.objects.select_for_update().select_related`, `model.objects.select_for_update().select_related(*related_fields).get`, `product.created_at.isoformat`, `product.save`, `product_configuration`, `product_snapshot`, `product_version`, `record_product_changes`, `save_barcode_formset`, `set_supplier_exclusions`, `sorted`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_changes.append`, `stock_model.objects.create`, `stock_model.objects.filter`, `stock_model.objects.filter(warehouse_id=warehouse_id, **{f'{stock_product_field}_id': product.pk}).first`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(**{stock_product_field: product}).select_related`, `stocks_by_warehouse.get`, `str`, `timezone.now`, `tuple`, `update_product_prices`, `update_storage_locations`.

## `catalog/nomenclature_urls.py`

Маршруты карточек, галерей, штрихкодов и контролируемого удаления номенклатуры.

Импорты: `django.urls`.

## `catalog/nomenclature_views.py`

Карточки номенклатуры: полевые permissions, оптимистическая версия и аудит значимых изменений.

Импорты: `collections`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.core.paginator`, `django.db.models`, `django.db.models.functions`, `django.http`, `django.shortcuts`, `django.urls`, `django.views.decorators.http`, `integrations.models`, `integrations.views`, `models`, `nomenclature_forms`, `nomenclature_grouping`, `nomenclature_services`, `product_filters`, `product_identifiers`, `product_media`, `removal`, `warehouse.models`, `yandex_market.models`, `yandex_market.product_content`.

### `nomenclature_list(request, product_kind=None)`

Исходник: `catalog/nomenclature_views.py:47`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.filter`, `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform', 'game_series').annotate`, `CD.objects.active().select_related('platform', 'game_series').annotate(global_stock=stock_total).order_by`, `Coalesce`, `Exists`, `Http404`, `IntegerField`, `OuterRef`, `Sum`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.active().select_related('brand', 'product_type').annotate`, `Tech.objects.active().select_related('brand', 'product_type').annotate(global_stock=stock_total).order_by`, `Value`, `cds.annotate`, `cds.none`, `context.update`, `defaultdict`, `filter_product_querysets`, `get_nomenclature_grouping`, `list`, `params.pop`, `permission_required_any`, `product_filter_context`, `render`, `request.GET.copy`, `request.GET.get`, `request.session.pop`, `request.user.has_perm`, `tech_groups.items`, `tech_groups[product.product_type].append`, `tech_items.annotate`, `tech_items.none`.

### `product_bulk_delete(request)`

Исходник: `catalog/nomenclature_views.py:129`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`; `permission_required_any('catalog.delete_cd', 'catalog.delete_tech')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `BulkProductDeleteForm`, `NOMENCLATURE_LIST_ROUTES.get`, `QueryDict`, `QueryDict(form.cleaned_data['query']).urlencode`, `form.cleaned_data.get`, `form.errors.values`, `form.is_valid`, `len`, `messages.error`, `permission_required_any`, `redirect`, `remove_products`, `reverse`, `str`, `sum`.

### `product_create(request)`

Исходник: `catalog/nomenclature_views.py:161`.

Декораторы: `permission_required_any('catalog.add_cd', 'catalog.add_tech')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(request.POST.get('product_kind') or request.GET.get('kind') or '').lower`, `barcode_data.update`, `barcode_formset`, `barcodes.is_valid`, `create_product`, `form.add_error`, `form.is_valid`, `form_class`, `messages.success`, `permission_required_any`, `redirect`, `render`, `request.GET.get`, `request.POST.copy`, `request.POST.get`, `request.user.has_perm`, `str`, `str(request.POST.get('barcode') or '').strip`, `{'cd': CDCreateForm, 'tech': TechCreateForm}.get`.

### `_stock_context(product)`

Исходник: `catalog/nomenclature_views.py:208`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `Warehouse.objects.all`, `list`, `product.warehouse_stocks.select_related`, `product.warehouse_transfer_items.filter`, `product.warehouse_transfer_items.filter(transfer__status__in=active_statuses).aggregate`, `quantities.get`, `sum`.

### `_form_sections(form, product_kind)`

Исходник: `catalog/nomenclature_views.py:234`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_render_detail(request, *, product, product_kind, form, barcodes=None)`

Исходник: `catalog/nomenclature_views.py:262`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Integration.objects.all`, `Paginator`, `Paginator(events, 10).get_page`, `_form_sections`, `_stock_context`, `barcode_formset`, `list`, `product.catalog_images.all`, `product.change_events.select_related`, `product.change_events.select_related('actor').prefetch_related`, `product.yandex_connections.filter`, `product.yandex_connections.filter(active=True).select_related`, `product.yandex_connections.filter(active=True).select_related('remote_offer', 'integration').prefetch_related`, `product_avito_context`, `render`, `request.GET.get`, `request.user.has_perm`, `saved_product_content`.

### `_product_detail(request, *, product_kind, product_id)`

Исходник: `catalog/nomenclature_views.py:319`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `_render_detail`, `barcode_formset`, `barcodes.is_valid`, `form.add_error`, `form.is_valid`, `form_class`, `get_object_or_404`, `logger.exception`, `messages.info`, `messages.success`, `model.objects.select_related`, `model.objects.select_related(*related_fields).get`, `model.objects.select_related(*related_fields).prefetch_related`, `redirect`, `request.user.has_perm`, `update_product_card`.

### `cd_detail(request, pk)`

Исходник: `catalog/nomenclature_views.py:378`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_product_detail`, `permission_required_any`.

### `tech_detail(request, pk)`

Исходник: `catalog/nomenclature_views.py:383`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_product_detail`, `permission_required_any`.

### `_can_view_product_media(user)`

Исходник: `catalog/nomenclature_views.py:387`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `user.has_perm`.

### `_require_media_change(request, product_kind)`

Исходник: `catalog/nomenclature_views.py:401`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `request.user.has_perm`.

### `_media_response(field_file)`

Исходник: `catalog/nomenclature_views.py:409`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FileResponse`, `Http404`, `field_file.open`, `mimetypes.guess_type`.

### `product_title_image(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:422`.

Декораторы: `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Http404`, `PermissionDenied`, `_can_view_product_media`, `_media_response`, `get_object_or_404`, `product_model`.

### `product_gallery_image(request, product_kind, pk, image_id)`

Исходник: `catalog/nomenclature_views.py:436`.

Декораторы: `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Http404`, `PermissionDenied`, `_can_view_product_media`, `_media_response`, `get_object_or_404`, `product_model`.

### `product_title_upload(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:455`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Http404`, `_require_media_change`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.FILES.get`, `set_title_image`.

### `product_title_delete(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:475`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Http404`, `_require_media_change`, `delete_title_image`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `product_gallery_upload(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:492`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Http404`, `_require_media_change`, `add_gallery_images`, `len`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.FILES.getlist`, `request.POST.get`.

### `product_gallery_delete(request, product_kind, pk, image_id)`

Исходник: `catalog/nomenclature_views.py:513`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Http404`, `_require_media_change`, `delete_gallery_image`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `product_delete(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:533`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Http404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `remove_product`, `request.user.has_perm`.

### `barcode_generate(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:558`.

Декораторы: `require_POST`; `permission_required_any('catalog.change_cd_barcode', 'catalog.change_tech_barcode')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `generate_unique_barcode`, `locals`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.user.has_perm`.

### `barcode_print(request, barcode_id)`

Исходник: `catalog/nomenclature_views.py:577`.

Декораторы: `require_GET`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `get_object_or_404`, `messages.error`, `permission_required_any`, `redirect`, `render`, `render_barcode_svg_data_url`.

### `barcode_print_legacy(request, product_kind, pk)`

Исходник: `catalog/nomenclature_views.py:590`.

Декораторы: `require_GET`; `permission_required_any('catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `messages.error`, `permission_required_any`, `product.barcodes.order_by`, `product.barcodes.order_by('id').first`, `redirect`, `render`, `render_barcode_svg_data_url`.

## `catalog/packaging_defaults.py`

Стандартная упаковка CD и геймпадов, заданная пользователем CRM.

Импорты: `decimal`, `django.core.exceptions`.

### `default_dimensions_for(product)`

Исходник: `catalog/packaging_defaults.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `product.product_type.name.strip`, `product.product_type.name.strip().casefold`.

### `fill_new_product_dimensions(product)`

Исходник: `catalog/packaging_defaults.py:24`.

Заполняет пустые размеры при создании, сохраняя указанные вручную.

Статические вызовы: `default_dimensions_for`, `default_dimensions_for(product).items`, `getattr`, `setattr`.

## `catalog/product_fields.py`

Единая конфигурация полей карточки и прав их просмотра/изменения; используется несколькими интерфейсами.

### `card_fields_for(model)`

Исходник: `catalog/product_fields.py:88`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `field_permissions_for(model)`

Исходник: `catalog/product_fields.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `catalog/product_filters.py`

Общие GET-фильтры товарных списков склада, номенклатуры и цен.

Импорты: `dataclasses`, `models`, `product_search`, `urllib.parse`.

### `ProductFilterState.is_active(self)`

Исходник: `catalog/product_filters.py:23`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `ProductFilterState.tech_filters_active(self)`

Исходник: `catalog/product_filters.py:30`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `_integer(value)`

Исходник: `catalog/product_filters.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`.

### `product_filter_context(params, *, include_game_series=False)`

Исходник: `catalog/product_filters.py:42`.

Возвращает нормализованное состояние и динамические варианты фильтров.

Статические вызовы: `(params.get('search') or params.get('q') or '').strip`, `Brand.objects.order_by`, `GameSeries.objects.order_by`, `Platform.objects.order_by`, `ProductFilterState`, `ProductType.objects.order_by`, `_integer`, `list`, `params.get`, `str`.

### `filter_product_querysets(cd_queryset, tech_queryset, state)`

Исходник: `catalog/product_filters.py:86`.

Применяет одинаковые правила к уже разрешённым view queryset-ам.

Статические вызовы: `cd_queryset.filter`, `cd_queryset.none`, `search_product_querysets`, `tech_queryset.filter`, `tech_queryset.none`.

### `product_filter_query_string(params, *, extra_keys=())`

Исходник: `catalog/product_filters.py:106`.

Сохраняет только разрешённые параметры после inline POST на Pricing.

Статические вызовы: `params.get`, `urlencode`.

## `catalog/product_identifiers.py`

Атомарные операции с весом, артикулами и общим реестром штрихкодов.

Импорты: `audit`, `barcode.writer`, `django.core.exceptions`, `django.db`, `io`, `models`.

### `product_configuration(product_kind)`

Исходник: `catalog/product_identifiers.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_registry_lookup(product)`

Исходник: `catalog/product_identifiers.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`.

### `add_product_barcode(*, actor, product_kind, product_id, value)`

Исходник: `catalog/product_identifiers.py:33`.

Декораторы: `transaction.atomic`.

Добавить код в общий реестр, сохранив прежние коды и запись аудита.

Статические вызовы: `BarcodeRegistry`, `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(value=value).first`, `ValidationError`, `_registry_lookup`, `entry.full_clean`, `entry.save`, `field_change`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().get`, `product_configuration`, `record_product_changes`, `str`, `str(value or '').strip`, `transaction.atomic`.

### `validate_barcode_uniqueness(*, product, barcode)`

Исходник: `catalog/product_identifiers.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.filter`, `ValidationError`, `isinstance`, `registry.exclude`, `registry.exists`, `str`, `str(barcode or '').strip`.

### `set_product_barcode(*, product, barcode)`

Исходник: `catalog/product_identifiers.py:82`.

Compatibility helper: replaces all product barcodes with one value.

Статические вызовы: `BarcodeRegistry.objects.create`, `BarcodeRegistry.objects.select_for_update`, `BarcodeRegistry.objects.select_for_update().filter`, `BarcodeRegistry.objects.select_for_update().filter(**lookup).delete`, `ValidationError`, `_registry_lookup`, `transaction.atomic`, `validate_barcode_uniqueness`.

### `save_barcode_formset(*, product, formset)`

Исходник: `catalog/product_identifiers.py:102`.

Saves a validated barcode formset and returns audit field changes.

Статические вызовы: `BarcodeRegistry`, `BarcodeRegistry.objects.select_for_update`, `BarcodeRegistry.objects.select_for_update().filter`, `_registry_lookup`, `changes.append`, `existing.get`, `existing.pop`, `field_change`, `form.cleaned_data.get`, `instance.delete`, `instance.save`.

### `ensure_product_article(product)`

Исходник: `catalog/product_identifiers.py:158`.

Генерирует стабильный артикул только для новой карточки с пустым значением.

Статические вызовы: `CD.objects.filter`, `CD.objects.filter(sku=candidate).exclude`, `CD.objects.filter(sku=candidate).exclude(pk=product.pk).exists`, `Tech.objects.filter`, `Tech.objects.filter(sku=candidate).exclude`, `Tech.objects.filter(sku=candidate).exclude(pk=product.pk).exists`, `isinstance`, `product.save`, `product.sku.strip`, `str`, `str(product.sku or '').strip`.

### `_positive_weight(value)`

Исходник: `catalog/product_identifiers.py:177`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`, `raw.isdecimal`, `str`, `str(value or '').strip`.

### `set_product_weight(*, actor, product_kind, product_id, weight_grams)`

Исходник: `catalog/product_identifiers.py:188`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_positive_weight`, `field_change`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().get`, `product.full_clean`, `product.save`, `product_configuration`, `record_product_changes`.

### `generate_unique_barcode(*, actor, product_kind, product_id)`

Исходник: `catalog/product_identifiers.py:217`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_registry_lookup`, `allocate_unique_barcode`, `field_change`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().get`, `product_configuration`, `record_product_changes`.

### `allocate_unique_barcode(registry_model, **owner)`

Исходник: `catalog/product_identifiers.py:232`.

Общий генератор реестра, также работающий с исторической моделью миграции.

Статические вызовы: `''.join`, `ValidationError`, `range`, `registry_model.objects.create`, `secrets.choice`, `transaction.atomic`.

### `render_barcode_svg_data_url(value)`

Исходник: `catalog/product_identifiers.py:246`.

Возвращает настоящий Code 128 без человекочитаемой строки.

Статические вызовы: `BytesIO`, `SVGWriter`, `ValidationError`, `barcode.get`, `barcode.get('code128', value, writer=SVGWriter()).write`, `base64.b64encode`, `base64.b64encode(output.getvalue()).decode`, `output.getvalue`, `str`, `str(value or '').strip`.

## `catalog/product_media.py`

Проверка и атомарное управление изображениями номенклатуры.

Импорты: `PIL`, `audit`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`, `pathlib`.

### `product_model(product_kind)`

Исходник: `catalog/product_media.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `validate_product_image(upload)`

Исходник: `catalog/product_media.py:29`.

Проверяет реальное содержимое изображения, а не только расширение файла.

Статические вызовы: `Image.open`, `Path`, `ValidationError`, `getattr`, `image.verify`, `upload.seek`.

### `_delete_file(storage, name)`

Исходник: `catalog/product_media.py:55`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `storage.delete`.

### `set_title_image(*, actor, product_kind, product_id, upload)`

Исходник: `catalog/product_media.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `ValidationError`, `_delete_file`, `field_change`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `product.save`, `product.title_image.save`, `product_model`, `record_product_changes`, `storage.delete`, `transaction.atomic`, `transaction.on_commit`, `validate_product_image`.

### `delete_title_image(*, actor, product_kind, product_id)`

Исходник: `catalog/product_media.py:96`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `ValidationError`, `_delete_file`, `field_change`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `product.save`, `product_model`, `record_product_changes`, `transaction.atomic`, `transaction.on_commit`.

### `add_gallery_images(*, actor, product_kind, product_id, image_kind, uploads)`

Исходник: `catalog/product_media.py:123`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Max`, `Path`, `ProductImage`, `ProductImage.objects.filter`, `ProductImage.objects.filter(product_kind=product_kind, image_kind=image_kind, **relation).aggregate`, `ValidationError`, `created.append`, `created_files.append`, `dict`, `enumerate`, `field_change`, `item.image.save`, `item.save`, `len`, `list`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `product_model`, `record_product_changes`, `storage.delete`, `transaction.atomic`, `validate_product_image`.

### `delete_gallery_image(*, actor, product_kind, product_id, image_id)`

Исходник: `catalog/product_media.py:179`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `ProductImage.objects.select_for_update`, `ProductImage.objects.select_for_update().get`, `ValidationError`, `_delete_file`, `field_change`, `item.delete`, `item.get_image_kind_display`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `product_model`, `record_product_changes`, `transaction.atomic`, `transaction.on_commit`.

## `catalog/product_ordering.py`

Общий порядок прайса и таблиц CRM без изменения состава выборок.

Импорты: `collections`, `price.sony_gamepad_sorting`.

### `normalized_order_name(value)`

Исходник: `catalog/product_ordering.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `str`, `str(value or '').casefold`, `str(value or '').casefold().replace`, `str(value or '').casefold().replace('ё', 'е').split`.

### `is_portable(product_type_name, brand_name='')`

Исходник: `catalog/product_ordering.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `normalized_order_name`.

### `type_rank(value, rules, default=999)`

Исходник: `catalog/product_ordering.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `next`, `normalized_order_name`.

### `tech_section(product)`

Исходник: `catalog/product_ordering.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `is_portable`, `normalized_order_name`.

### `tech_price_order(product, *, for_excel=False)`

Исходник: `catalog/product_ordering.py:48`.

Общий порядок CRM; отдельные правила Edge и VR применяются только к XLSX.

Статические вызовы: `any`, `is_sony_gamepad`, `normalize_product_name`, `normalize_product_name(product_type).startswith`, `normalized_order_name`, `sony_gamepad_sort_key`, `tech_section`, `type_rank`.

### `platform_order_key(platform)`

Исходник: `catalog/product_ordering.py:80`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `hasattr`, `normalized_order_name`.

### `cd_order_key(product)`

Исходник: `catalog/product_ordering.py:88`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalized_order_name`, `platform_order_key`.

### `tech_brand_groups(items, *, product_of=lambda item: item)`

Исходник: `catalog/product_ordering.py:93`.

Группирует уже разрешённые строки по бренду и типу, сохраняя поля строк.

Статические вызовы: `OrderedDict`, `brand['types'][type_id][1].append`, `brands.values`, `grouping['types'].values`, `list`, `product_of`, `result.append`, `sorted`, `tech_price_order`.

## `catalog/product_search.py`

Единый регистронезависимый поиск CD и Tech для складских операций.

Импорты: `models`.

### `filter_products_by_text(queryset, query, *, product_kind)`

Исходник: `catalog/product_search.py:6`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.exclude`, `BarcodeRegistry.objects.exclude(**{barcode_owner_field: None}).values_list`, `BarcodeRegistry.objects.exclude(**{barcode_owner_field: None}).values_list(barcode_owner_field, 'value').iterator`, `any`, `int`, `len`, `matches.append`, `matches.extend`, `query.casefold`, `query.isdecimal`, `queryset.filter`, `queryset.values_list`, `queryset.values_list('id', *fields).iterator`, `str`, `str(query or '').strip`, `str(value or '').casefold`, `value.casefold`.

### `search_product_querysets(cd_queryset, tech_queryset, query)`

Исходник: `catalog/product_search.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cd_queryset.active`, `filter_products_by_text`, `tech_queryset.active`.

## `catalog/profit_defaults.py`

Начальная желаемая прибыль FBS для новых карточек товаров.

Импорты: `decimal`, `django.core.exceptions`.

### `fill_new_product_desired_profit(product)`

Исходник: `catalog/profit_defaults.py:12`.

Выбирает прибыль по типу при создании, сохраняя введённую сумму.

Статические вызовы: `product.product_type.name.strip`, `product.product_type.name.strip().casefold`.

## `catalog/removal.py`

Единое безопасное удаление карточек CD и Tech.

Новые связи с товаром по умолчанию считаются историей: только перечисленные
технические связи разрешено удалять вместе с никогда не использованной карточкой.

Импорты: `dataclasses`, `django.core.exceptions`, `django.db`, `django.db.models.deletion`, `django.utils`, `integrations.models`, `models`, `warehouse.models`.

### `normalize_removal_selection(selection)`

Исходник: `catalog/removal.py:62`.

Проверяет весь список до начала удаления и убирает повторные ID.

Статические вызовы: `ValidationError`, `int`, `isinstance`, `len`, `re.fullmatch`, `seen.add`, `set`, `token.split`, `tokens.append`, `tuple`.

### `remove_products(*, selection, actor)`

Исходник: `catalog/removal.py:85`.

Декораторы: `transaction.atomic`.

Удаляет группу штатным сервисом; защищённые карточки остаются с пояснением.

Статические вызовы: `BulkRemovalItem`, `PermissionDenied`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().order_by`, `actor.has_perm`, `any`, `int`, `list`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `model.objects.select_for_update().filter(pk=product_id).only`, `model.objects.select_for_update().filter(pk=product_id).only('name').first`, `normalize_removal_selection`, `remove_product`, `results.append`, `sorted`, `token.split`, `tuple`.

### `_product_kind(product)`

Исходник: `catalog/removal.py:119`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TypeError`, `isinstance`.

### `has_product_history(product)`

Исходник: `catalog/removal.py:127`.

Возвращает реальные бизнес-связи; неизвестная новая связь безопасно считается историей.

Статические вызовы: `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(**{_product_kind(product): product}).first`, `_product_kind`, `avito_profile.photos.exists`, `avito_profile.sync_jobs.exists`, `avito_profile.sync_logs.exists`, `found.append`, `product.change_events.exclude`, `product.change_events.exclude(action_kind='').exists`, `product.change_events.filter`, `product.change_events.filter(field_changes__field_name__startswith='warehouse_stock_').exists`, `relation.get_accessor_name`, `relation.related_model.objects.filter`, `relation.related_model.objects.filter(**{relation.field.name: product}).exists`, `tuple`.

### `evaluate_product_removal(product)`

Исходник: `catalog/removal.py:156`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.filter`, `AvitoListingConnection.objects.filter(**{f'profile__{kind}_id': product.pk}).exists`, `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(**{kind: product}).exists`, `RemovalAssessment`, `_product_kind`, `has_product_history`, `product.consignment_stocks.filter`, `product.consignment_stocks.filter(quantity__gt=0).exists`, `product.warehouse_stocks.filter`, `product.warehouse_stocks.filter(quantity__gt=0).exists`, `product.warehouse_transfer_items.filter`, `product.warehouse_transfer_items.filter(transfer__status__in=(WarehouseTransfer.Status.CREATED, WarehouseTransfer.Status.ASSEMBLED, WarehouseTransfer.Status.SHIPPED)).exists`, `product.yandex_connections.filter`, `product.yandex_connections.filter(active=True).exists`, `reasons.append`, `tuple`.

### `remove_product(*, product_kind, product_id, actor)`

Исходник: `catalog/removal.py:187`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(**{product_kind: product}).delete`, `ProductRemovalEvent.objects.create`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().order_by`, `dict`, `evaluate_product_removal`, `list`, `media_files.append`, `media_files.extend`, `model.objects.select_for_update`, `model.objects.select_for_update().get`, `product.catalog_images.all`, `product.change_events.all`, `product.change_events.all().delete`, `product.consignment_stocks.all`, `product.consignment_stocks.all().delete`, `product.consignment_stocks.select_for_update`, `product.delete`, `product.save`, `product.supplier_prices.all`, `product.supplier_prices.all().delete`, `product.warehouse_stocks.all`, `product.warehouse_stocks.all().delete`, `product.warehouse_stocks.select_for_update`, `storage.delete`, `timezone.now`, `transaction.on_commit`.

## `catalog/supplier_exclusions.py`

Допуск поставщиков к новым назначениям; цены и исторические снимки сохраняются.

Импорты: `audit`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`, `partners.models`.

### `exclusion_keys(product_keys=None)`

Исходник: `catalog/supplier_exclusions.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductSupplierExclusion.objects.all`, `Q`, `rows.filter`, `rows.values_list`, `set`.

### `validate_supplier_assignments(assignments)`

Исходник: `catalog/supplier_exclusions.py:21`.

Одна выборка исключений для всего нового состава, включая источник цены.

Статические вызовы: `ValidationError`, `exclusion_keys`, `list`.

### `set_supplier_exclusions(*, product, supplier_ids, actor, creating=False)`

Исходник: `catalog/supplier_exclusions.py:31`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `ProductSupplierExclusion.objects.create`, `ProductSupplierExclusion.objects.select_for_update`, `ProductSupplierExclusion.objects.select_for_update().select_related`, `ProductSupplierExclusion.objects.select_for_update().select_related('supplier').filter`, `Supplier.objects.filter`, `ValidationError`, `actor.has_perm`, `bool`, `changes.append`, `field_change`, `int`, `old[supplier_id].delete`, `record_product_changes`, `set`, `sorted`, `type`, `type(product).objects.select_for_update`, `type(product).objects.select_for_update().get`.

## `catalog/system_products.py`

Идемпотентная инициализация двух внутренних позиций и их штрихкодов.

Импорты: `django.db`, `models`, `product_identifiers`.

### `ensure_system_products()`

Исходник: `catalog/system_products.py:11`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(system_product=product).exists`, `SystemProduct.objects.get_or_create`, `SystemProduct.objects.select_related`, `SystemProduct.objects.select_related('barcode_entry').order_by`, `allocate_unique_barcode`, `logging.getLogger`, `logging.getLogger('gamebat.business').info`.

## `catalog/urls.py`

Именованные HTTP-маршруты приложения номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry.

Импорты: `django.urls`.

## `catalog/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю номенклатуры.

Карточка описывает товар; физическое количество хранится в warehouse, штрихкоды — в BarcodeRegistry.

Импорты: `warehouse.views`.

### `warehouse(request)`

Исходник: `catalog/views.py:7`.

Сохраняет прежний URL склада, показывая новую страницу общих остатков.

Статические вызовы: `global_stock`.

## `consignment/admin.py`

Регистрация моделей и разрешённых действий в Django Admin реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `django.contrib`, `models`.

### `CurrentStockAdmin.has_add_permission(self, request)`

Исходник: `consignment/admin.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CurrentStockAdmin.has_change_permission(self, request, obj=None)`

Исходник: `consignment/admin.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CurrentStockAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `consignment/admin.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ConsignmentMovementItemInline.has_add_permission(self, request, obj=None)`

Исходник: `consignment/admin.py:45`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `consignment/apps.py`

Конфигурация приложения и его регистрация в Django реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `django.apps`.

## `consignment/excel.py`

Экспорт актуальных партий реализации без себестоимости и финансовых снимков.

Импорты: `decimal`, `django.db`, `django.utils`, `io`, `itertools`, `models`, `openpyxl`, `openpyxl.styles`, `openpyxl.worksheet.datavalidation`, `price.excel`, `reports`, `textwrap`, `uuid`.

### `_stock_rows(platform, user)`

Исходник: `consignment/excel.py:19`.

Явный список разрешённых полей: ни стоимость, ни история не загружаются.

Статические вызовы: `list`, `model.objects.filter`, `model.objects.filter(platform=platform, quantity__gt=0).values`, `row[f'{product}__name'].casefold`, `row[f'{product}__{category}__name'].casefold`, `rows.sort`, `sections.append`, `transaction.atomic`, `user.has_perm`.

### `generate_consignment_xlsx(*, platform, user)`

Исходник: `consignment/excel.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `Border`, `BytesIO`, `DataValidation`, `Decimal`, `Font`, `PatternFill`, `Side`, `Workbook`, `_stock_rows`, `enumerate`, `group_heading`, `groupby`, `identities.append`, `len`, `list`, `max`, `metadata.append`, `output.getvalue`, `range`, `safe_text`, `sheet.add_data_validation`, `sheet.append`, `sheet.cell`, `sheet.merge_cells`, `sign_report`, `str`, `timezone.localtime`, `uuid4`, `validation.add`, `workbook.close`, `workbook.create_sheet`, `workbook.save`, `wrap`, `zip`.

## `consignment/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `django`, `partners.models`, `warehouse.form_defaults`, `warehouse.models`.

## `consignment/management/commands/import_itech_consignment.py`

Адресный импорт партий реализации из файла; повторный запуск не является штатной проверкой.

Импорты: `catalog.management.commands.import_catalog_names`, `catalog.models`, `consignment.models`, `consignment.services`, `dataclasses`, `decimal`, `django.contrib.auth`, `django.core.management.base`, `django.db`, `openpyxl`, `partners.models`, `pathlib`, `warehouse.models`.

### `_decimal(value, *, row, label)`

Исходник: `consignment/management/commands/import_itech_consignment.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `Decimal(str(value)).quantize`, `str`.

### `_read_source(path)`

Исходник: `consignment/management/commands/import_itech_consignment.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `CommandError`, `SourceLine`, `_decimal`, `enumerate`, `int`, `load_workbook`, `result.append`, `sheet.iter_rows`, `str`, `str(name).split`, `workbook.close`.

### `_match_line(line)`

Исходник: `consignment/management/commands/import_itech_consignment.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').filter`, `CommandError`, `Tech.objects.active`, `Tech.objects.active().select_related`, `_base_normalize`, `_is_same_product`, `iter`, `len`, `list`, `next`, `unique.values`.

### `Command.add_arguments(self, parser)`

Исходник: `consignment/management/commands/import_itech_consignment.py:98`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `consignment/management/commands/import_itech_consignment.py:103`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `Brand.objects.get`, `CommandError`, `ProductType.objects.get`, `SalesPlatform.objects.get`, `Tech.objects.create`, `TechWarehouseStock.objects.create`, `User.objects.get`, `Warehouse.objects.count`, `Warehouse.objects.get`, `_match_line`, `_read_source`, `already_present.append`, `get_user_model`, `len`, `matched.get`, `missing.append`, `options['xlsx'].resolve`, `path.is_file`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `stock_model.objects.filter`, `stock_model.objects.filter(warehouse=warehouse, platform=platform, **{product_field: product}).first`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().get_or_create`, `sum`, `transaction.atomic`, `transfer_lines.append`, `transfer_many_to_consignment`, `warehouse_stock.full_clean`, `warehouse_stock.save`.

## `consignment/management/commands/replace_playbox_consignment.py`

Адресная замена состава PlayBox; потенциально меняет партии и требует прямого поручения на данные.

Импорты: `catalog.management.commands.import_catalog_names`, `catalog.models`, `collections`, `consignment.models`, `consignment.services`, `dataclasses`, `decimal`, `django.contrib.auth`, `django.core.management.base`, `django.db`, `openpyxl`, `partners.models`, `pathlib`, `warehouse.models`.

### `_money(value, *, row, label)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Decimal`, `Decimal(str(value)).quantize`, `str`.

### `_quantity(value, *, row)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `int`.

### `_read_source(path)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SourceLine`, `_money`, `_quantity`, `lines.append`, `load_workbook`, `range`, `sheet.cell`, `str`, `str(name).split`, `workbook.close`.

### `_match_line(line)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').filter`, `CommandError`, `Tech.objects.active`, `_base_normalize`, `_is_same_product`, `iter`, `len`, `list`, `matches.values`, `next`.

### `_prepare(lines)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:120`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(source_total / quantity).quantize`, `PreparedLine`, `_match_line`, `defaultdict`, `grouped.items`, `grouped[key].append`, `item.product_name.casefold`, `len`, `prepared.append`, `prepared.sort`, `sum`, `tuple`, `weighted.append`.

### `_stock_config(kind)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:151`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_current_lines(platform, warehouse)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:157`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PreparedLine`, `_stock_config`, `consignment_model.objects.filter`, `consignment_model.objects.filter(platform=platform, warehouse=warehouse, quantity__gt=0).select_related`, `getattr`, `result.append`.

### `_signature(lines)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:177`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Command.add_arguments(self, parser)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:187`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `consignment/management/commands/replace_playbox_consignment.py:192`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CommandError`, `SalesPlatform.objects.get`, `User.objects.get`, `Warehouse.objects.count`, `Warehouse.objects.get`, `_current_lines`, `_prepare`, `_read_source`, `_signature`, `_stock_config`, `baseline.items`, `consignment_model.objects.filter`, `consignment_model.objects.filter(platform=platform, warehouse=warehouse, quantity=0).delete`, `expected_by_key.get`, `get_user_model`, `len`, `map`, `options['xlsx'].resolve`, `path.is_file`, `return_from_consignment`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `set`, `sorted`, `sum`, `transaction.atomic`, `transfer_many_to_consignment`, `warehouse_model.objects.get`, `warehouse_model.objects.select_for_update`, `warehouse_model.objects.select_for_update().get`, `warehouse_model.objects.select_for_update().get_or_create`, `warehouse_stock.full_clean`, `warehouse_stock.save`.

## `consignment/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `catalog.models`, `django.conf`, `django.core.validators`, `django.db`, `partners.models`, `warehouse.models`.

### `ConsignmentStockBase.potential_receivable(self)`

Исходник: `consignment/models.py:45`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CDConsignmentStock.__str__(self)`

Исходник: `consignment/models.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TechConsignmentStock.__str__(self)`

Исходник: `consignment/models.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ConsignmentMovement.position_count(self)`

Исходник: `consignment/models.py:114`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.items.count`.

### `ConsignmentMovement.total_units(self)`

Исходник: `consignment/models.py:118`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.items.all`, `sum`.

### `ConsignmentMovement.number(self)`

Исходник: `consignment/models.py:122`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ConsignmentMovement.action_label(self)`

Исходник: `consignment/models.py:126`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_operation_type_display`.

### `ConsignmentMovement.__str__(self)`

Исходник: `consignment/models.py:129`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ConsignmentMovementItem.product(self)`

Исходник: `consignment/models.py:190`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ConsignmentMovementItem.__str__(self)`

Исходник: `consignment/models.py:193`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `consignment/opening_balances.py`

Ввод ранее переданной реализации без повторного списания физического склада.

Импорты: `catalog.audit`, `catalog.models`, `decimal`, `django.core.exceptions`, `django.db`, `partners.models`, `services`, `warehouse.models`.

### `add_opening_balances(*, actor, warehouse_id, source_key, rows)`

Исходник: `consignment/opening_balances.py:13`.

Декораторы: `transaction.atomic`.

Создать партии по подтверждённому источнику и обновить агрегат товара.

Источник и номер строки образуют устойчивый ключ против повторного импорта.
Одинаковые товары с разным вознаграждением остаются разными партиями.
Сервис не является обычной передачей и не создаёт денежную операцию.

Статические вызовы: `Decimal`, `SalesPlatform.objects.get`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_configuration`, `_positive_quantity`, `_positive_receivable`, `dict`, `field_change`, `len`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().get`, `product.save`, `record_product_changes`, `results.append`, `row.get`, `stock.full_clean`, `stock.save`, `stock_model`, `stock_model.objects.filter`, `stock_model.objects.filter(**lookup).exists`, `str`.

## `consignment/report_views.py`

Отчёт площадки и создание партнёра при первой частичной оплате.

Импорты: `core.decorators`, `decimal`, `django.contrib`, `django.core`, `django.core.exceptions`, `django.db`, `django.shortcuts`, `django.urls`, `partners.forms`, `partners.models`, `reports`, `sales.forms`, `sales.models`, `sales.partner_payments`, `sales.services`.

### `report_import(request, pk)`

Исходник: `consignment/report_views.py:19`.

Декораторы: `permission_required_all('sales.create_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(platform=platform, is_archived=False).first`, `ValidationError`, `WholesalePriceImportForm`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `get_object_or_404`, `import_report`, `isinstance`, `pending.update`, `permission_required_all`, `redirect`, `render`, `request.POST.get`, `request.session.get`, `request.session.pop`, `reverse`, `str`.

### `needs_report_partner(sale, received)`

Исходник: `consignment/report_views.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `money`.

### `report_partner_payment(request, pk)`

Исходник: `consignment/report_views.py:56`.

Декораторы: `permission_required_all('sales.mark_sale_paid', 'partners.add_partner', 'partners.view_partner_contacts', 'creditors.change_debt')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(platform=platform).exists`, `PartnerForm`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `Sale.objects.select_related`, `SalesPlatform.objects.select_for_update`, `SalesPlatform.objects.select_for_update().get`, `ValidationError`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `form.save`, `get_object_or_404`, `isinstance`, `locked.save`, `mark_sale_paid`, `messages.success`, `money`, `needs_report_partner`, `partner.save`, `permission_required_all`, `quote`, `redirect`, `render`, `request.POST.get`, `request.session.get`, `request.session.pop`, `signing.dumps`, `str`, `str(request.POST.get('payment_note') or '').strip`, `transaction.atomic`.

## `consignment/reports.py`

Проверка подписанного отчёта; продажи проводятся штатным сервисом Sale.

Импорты: `decimal`, `django.core`, `django.core.exceptions`, `django.db`, `models`, `openpyxl`, `partners.models`, `sales.models`, `sales.services`, `uuid`, `zipfile`.

### `sign_report(value)`

Исходник: `consignment/reports.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `signing.dumps`.

### `unsign_report(value)`

Исходник: `consignment/reports.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `signing.loads`.

### `_quantity(value)`

Исходник: `consignment/reports.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `int`, `isinstance`, `result.is_finite`, `result.to_integral_value`, `str`.

### `current_report_rows(*, platform_id, rows, actor)`

Исходник: `consignment/reports.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `_quantity`, `actor.has_perm`, `getattr`, `model.objects.select_for_update`, `model.objects.select_for_update().select_related`, `model.objects.select_for_update().select_related(kind).get`, `result.append`, `seen.add`, `set`, `str`.

### `import_report(*, upload, platform_id, actor)`

Исходник: `consignment/reports.py:70`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `''.join`, `Partner.objects.filter`, `Partner.objects.filter(platform_id=platform_id, is_archived=False).first`, `Sale.objects.filter`, `Sale.objects.filter(consignment_report_id=manifest['report_id']).exists`, `UUID`, `ValidationError`, `_quantity`, `any`, `book.close`, `current_report_rows`, `load_workbook`, `locals`, `manifest.get`, `meta.iter_rows`, `next`, `rows.append`, `seen.add`, `set`, `sheet.iter_rows`, `str`, `str(values[3]).startswith`, `unsign_report`.

### `create_report_sale(*, actor, draft, **kwargs)`

Исходник: `consignment/reports.py:116`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(platform=platform, is_archived=False).first`, `Sale.objects.filter`, `Sale.objects.filter(consignment_report_id=draft['report_id']).first`, `SalesPlatform.objects.select_for_update`, `SalesPlatform.objects.select_for_update().get`, `ValidationError`, `any`, `create_sale`, `current_report_rows`, `kwargs.update`, `sale.save`, `zip`.

## `consignment/row_actions.py`

Подписанные снимки партий и защита штатных операций от повторной отправки.

Импорты: `django.core`, `django.core.exceptions`, `django.db`, `models`, `services`, `uuid`.

### `stock_queryset(kind)`

Исходник: `consignment/row_actions.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CDConsignmentStock.objects.select_related`, `TechConsignmentStock.objects.select_related`, `ValidationError`.

### `action_token(stock, kind, user)`

Исходник: `consignment/row_actions.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `signing.dumps`, `str`, `uuid4`.

### `perform_row_action(*, actor, kind, stock_id, token, action, quantity, warehouse_id=None, payment_method=None)`

Исходник: `consignment/row_actions.py:29`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ConsignmentActionReceipt.objects.create`, `ValidationError`, `record_consignment_sale`, `return_from_consignment`, `signing.loads`, `snapshot.get`, `stock_queryset`, `stock_queryset(kind).select_for_update`, `stock_queryset(kind).select_for_update().filter`, `stock_queryset(kind).select_for_update().filter(pk=stock_id).first`, `str`.

## `consignment/services.py`

Атомарные операции передачи, возврата и продажи товара с реализации.

Импорты: `cash.services`, `catalog.audit`, `catalog.models`, `decimal`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `partners.models`, `sales.models`, `warehouse.models`, `warehouse.storage_services`, `warehouse.valuation`.

### `_configuration(product_type)`

Исходник: `consignment/services.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_positive_quantity(value)`

Исходник: `consignment/services.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`, `str`, `str(value).strip`, `text.isdecimal`.

### `_positive_receivable(value)`

Исходник: `consignment/services.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `str`.

### `_nonnegative_receivable(value)`

Исходник: `consignment/services.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `str`.

### `_normalise_transfer_lines(raw_lines)`

Исходник: `consignment/services.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_positive_quantity`, `_positive_receivable`, `grouped.values`, `int`, `list`, `raw.get`, `str`, `str(raw.get('product_type', '')).lower`.

### `transfer_many_to_consignment(*, actor, warehouse_id, platform_id, lines)`

Исходник: `consignment/services.py:98`.

Декораторы: `transaction.atomic`.

Передаёт несколько товаров на одну площадку единым документом.

Статические вызовы: `ConsignmentMovement.objects.create`, `ConsignmentMovementItem`, `ConsignmentMovementItem.objects.bulk_create`, `SalesPlatform.objects.get`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_configuration`, `_normalise_transfer_lines`, `clear_storage_locations_if_zero`, `consignment_model`, `consignment_model.objects.select_for_update`, `consignment_model.objects.select_for_update().filter`, `consignment_model.objects.select_for_update().filter(warehouse=warehouse, platform=platform, lot_key='', **{f'{product_field}_id__in': ids}).order_by`, `consignment_stock.full_clean`, `consignment_stock.save`, `consignment_stocks.get`, `consignment_stocks.update`, `field_change`, `getattr`, `len`, `logger.info`, `movement_items.append`, `product.full_clean`, `product.save`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().filter`, `product_model.objects.active().select_for_update().filter(pk__in=ids).order_by`, `products.update`, `record_product_changes`, `stock_change`, `sum`, `warehouse_stock.full_clean`, `warehouse_stock.save`, `warehouse_stock_model.objects.select_for_update`, `warehouse_stock_model.objects.select_for_update().filter`, `warehouse_stock_model.objects.select_for_update().filter(warehouse=warehouse, **{f'{product_field}_id__in': ids}).order_by`, `warehouse_stocks.get`, `warehouse_stocks.update`, `weighted_warehouse_cost`.

### `transfer_to_consignment(*, actor, warehouse_id, platform_id, product_type, product_id, quantity, receivable_per_unit=None, reward_per_unit=None)`

Исходник: `consignment/services.py:244`.

Совместимый однострочный вызов; интерфейс использует массовую операцию.

Статические вызовы: `_configuration`, `stock_model.objects.get`, `transfer_many_to_consignment`.

### `update_consignment_reward(*, actor, product_type, stock_id, value)`

Исходник: `consignment/services.py:271`.

Декораторы: `transaction.atomic`.

Меняет сумму только у активной связки площадка + склад + товар и пишет Product audit.

Статические вызовы: `ValidationError`, `_configuration`, `_nonnegative_receivable`, `field_change`, `getattr`, `logger.info`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().get`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().select_related`, `stock_model.objects.select_for_update().select_related('platform', 'warehouse', product_field).get`.

### `return_from_consignment(*, actor, warehouse_id, platform_id, product_type, product_id, quantity, target_warehouse_id=None, stock_id=None)`

Исходник: `consignment/services.py:309`.

Декораторы: `transaction.atomic`.

Return a specific source lot to the chosen warehouse; legacy callers default to the source.

Статические вызовы: `ConsignmentMovement.objects.create`, `ConsignmentMovementItem.objects.create`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_configuration`, `_positive_quantity`, `consignment_model.objects.select_for_update`, `consignment_model.objects.select_for_update().select_related`, `consignment_model.objects.select_for_update().select_related('platform').get`, `field_change`, `logger.info`, `product.full_clean`, `product.save`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().get`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_change`, `warehouse_owned_quantity`, `warehouse_stock.full_clean`, `warehouse_stock.save`, `warehouse_stock_model`, `warehouse_stock_model.objects.select_for_update`, `warehouse_stock_model.objects.select_for_update().filter`, `warehouse_stock_model.objects.select_for_update().filter(warehouse=warehouse, **{product_field: product}).first`, `weighted_warehouse_cost`.

### `consume_consignment_sale_lines(*, actor, sale, lines)`

Исходник: `consignment/services.py:415`.

Списывает точные stock_id и создаёт снимки площадки/цены/стоимости. Вызывается внутри транзакции продажи; агрегат реализации меняется вместе с партией.

Статические вызовы: `(unit_price * quantity).quantize`, `SaleConsignmentItem.objects.create`, `ValidationError`, `_configuration`, `_positive_quantity`, `created.append`, `field_change`, `getattr`, `grouped.get`, `grouped.items`, `int`, `product.full_clean`, `product.save`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().get`, `raw.get`, `record_product_changes`, `sorted`, `stock.full_clean`, `stock.receivable_per_unit.quantize`, `stock.save`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().select_related`, `stock_model.objects.select_for_update().select_related('warehouse', 'platform', product_field).get`, `str`, `str(raw.get('product_kind') or raw.get('product_type') or '').lower`.

### `quote_consignment_sale_lines(lines)`

Исходник: `consignment/services.py:484`.

Блокирует партии и возвращает сумму; consume повторно проверяет те же строки.

Статические вызовы: `Decimal`, `ValidationError`, `_configuration`, `_positive_quantity`, `grouped.get`, `grouped.items`, `int`, `raw.get`, `sorted`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().select_related`, `stock_model.objects.select_for_update().select_related(product_field).get`, `str`, `str(raw.get('product_kind') or raw.get('product_type') or '').lower`, `total.quantize`.

### `restore_consignment_sale_lines(*, actor, sale, delete=False)`

Исходник: `consignment/services.py:509`.

Восстанавливает исходные партии строк данной продажи, а не произвольную партию того же товара. delete используется штатным редактированием после восстановления.

Статические вызовы: `SaleConsignmentItem.objects.filter`, `SaleConsignmentItem.objects.filter(sale=sale).delete`, `ValidationError`, `_configuration`, `field_change`, `getattr`, `list`, `product.save`, `product_model.objects.select_for_update`, `product_model.objects.select_for_update().get`, `record_product_changes`, `sale.consignment_items.select_for_update`, `sale.consignment_items.select_for_update().order_by`, `stock.save`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().select_related`, `stock_model.objects.select_for_update().select_related('platform', 'warehouse').get`.

### `record_consignment_sale(*, actor, product_type, stock_id, quantity, payment_method)`

Исходник: `consignment/services.py:552`.

Декораторы: `transaction.atomic`.

Фиксирует продажу с реализации без повторного списания со склада.

Статические вызовы: `Decimal`, `Partner.objects.filter`, `Partner.objects.filter(platform=stock.platform).first`, `Sale.objects.create`, `ValidationError`, `_configuration`, `consume_consignment_sale_lines`, `credit_sale_payment`, `sale.save`, `sale_item_model.objects.create`, `stock_model.objects.select_related`, `stock_model.objects.select_related('warehouse', 'platform').get`, `timezone.now`.

## `consignment/urls.py`

Именованные HTTP-маршруты приложения реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `django.urls`, `partners.platform_views`.

## `consignment/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю реализации.

Операции адресуют конкретную партию stock_id; разные условия партий не объединяются.

Импорты: `catalog.models`, `catalog.product_filters`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.template.loader`, `django.utils`, `django.utils.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `excel`, `forms`, `models`, `partners.models`, `row_actions`, `sales.models`, `services`, `warehouse.models`.

### `_can_record_sale(user)`

Исходник: `consignment/views.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `user.has_perm`.

### `_stock_row(stock, product_kind, user)`

Исходник: `consignment/views.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `action_token`.

### `_group_stocks(stocks, *, product_kind, user)`

Исходник: `consignment/views.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_stock_row`, `grouped.items`, `grouped.setdefault`, `grouped.setdefault(group, []).append`, `item[0].name.casefold`, `row['name'].casefold`, `row['warehouse'].name.casefold`, `sorted`.

### `_platform_presentations(user, platform_queryset, filters)`

Исходник: `consignment/views.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.filter`, `CD.objects.filter(consignment_stocks__platform_id__in=platform_ids, consignment_stocks__quantity__gt=0).distinct`, `CDConsignmentStock.objects.filter`, `CDConsignmentStock.objects.filter(platform_id__in=platform_ids, quantity__gt=0, cd_id__in=cds.values('pk')).select_related`, `Tech.objects.filter`, `Tech.objects.filter(consignment_stocks__platform_id__in=platform_ids, consignment_stocks__quantity__gt=0).distinct`, `TechConsignmentStock.objects.filter`, `TechConsignmentStock.objects.filter(platform_id__in=platform_ids, quantity__gt=0, tech_id__in=techs.values('pk')).select_related`, `_group_stocks`, `cd_by_platform[stock.platform_id].append`, `cds.values`, `filter_product_querysets`, `len`, `list`, `result.append`, `sum`, `tech_by_platform[stock.platform_id].append`, `techs.values`, `user.has_perm`.

### `_consignment_context(request, platform_queryset, *, selected_platform=None)`

Исходник: `consignment/views.py:97`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Warehouse.objects.all`, `_can_record_sale`, `_platform_presentations`, `any`, `product_filter_context`, `request.user.has_perm`.

### `_parse_transfer_lines(post)`

Исходник: `consignment/views.py:116`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `all`, `len`, `post.getlist`, `range`.

### `_submitted_transfer_lines(post)`

Исходник: `consignment/views.py:134`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enumerate`, `len`, `model.objects.active`, `model.objects.active().select_related`, `model.objects.active().select_related('platform' if product_type == 'cd' else 'product_type').get`, `post.getlist`, `rows.append`, `value`.

### `consignment_list(request)`

Исходник: `consignment/views.py:172`.

Декораторы: `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SalesPlatform.objects.all`, `_consignment_context`, `permission_required_any`, `render`.

### `consignment_platform(request, pk)`

Исходник: `consignment/views.py:180`.

Декораторы: `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SalesPlatform.objects.filter`, `_consignment_context`, `get_object_or_404`, `permission_required_any`, `render`.

### `platform_export(request, pk)`

Исходник: `consignment/views.py:193`.

Декораторы: `never_cache`; `require_GET`; `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `content_disposition_header`, `generate_consignment_xlsx`, `get_object_or_404`, `permission_required_any`, `timezone.localdate`.

### `reward_update(request, product_kind, pk)`

Исходник: `consignment/views.py:206`.

Декораторы: `require_POST`; `permission_required_any('consignment.change_consignment_reward')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `_row_response`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `request.get_host`, `request.headers.get`, `request.is_secure`, `return_to.startswith`, `stock_queryset`, `update_consignment_reward`, `url_has_allowed_host_and_scheme`.

### `transfer(request)`

Исходник: `consignment/views.py:238`.

Декораторы: `permission_required_any('consignment.transfer_stock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TransferForm`, `_parse_transfer_lines`, `_submitted_transfer_lines`, `form.add_error`, `form.is_valid`, `messages.success`, `permission_required_any`, `redirect`, `render`, `transfer_many_to_consignment`.

### `return_stock(request)`

Исходник: `consignment/views.py:264`.

Декораторы: `require_GET`; `permission_required_any('consignment.return_stock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `permission_required_any`, `redirect`.

### `consignment_sale(request, product_kind, pk)`

Исходник: `consignment/views.py:270`.

Декораторы: `require_GET`; `permission_required_any('sales.create_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `permission_required_any`, `redirect`, `stock_queryset`.

### `_row_response(request, kind, pk, success, message, status=200)`

Исходник: `consignment/views.py:277`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `_can_record_sale`, `_stock_row`, `bool`, `render_to_string`, `request.POST.get`, `request.POST.get('return_to', '').split`, `request.user.has_perm`, `stock_queryset`, `stock_queryset(kind).filter`, `stock_queryset(kind).filter(pk=pk).first`.

### `row_action(request, product_kind, pk)`

Исходник: `consignment/views.py:296`.

Декораторы: `require_POST`; `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `_row_response`, `perform_row_action`, `permission_required_any`, `request.POST.get`, `request.user.has_perm`, `{'return': 'consignment.return_stock', 'sold': 'sales.create_sale'}.get`.

### `movement_detail(request, pk)`

Исходник: `consignment/views.py:328`.

Декораторы: `permission_required_any('catalog.view_nomenclature', 'consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ConsignmentMovement.objects.select_related`, `ConsignmentMovement.objects.select_related('created_by', 'warehouse', 'platform').prefetch_related`, `get_object_or_404`, `permission_required_any`, `render`.

## `core/admin.py`

Регистрация моделей и разрешённых действий в Django Admin общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев.

Импорты: `django.contrib`, `models`.

## `core/admin_site.py`

Допуск к Admin по специальному праву без превращения сотрудника в staff/superuser.

Импорты: `django.contrib.admin.forms`, `django.core.exceptions`.

### `GameBATAdminAuthenticationForm.confirm_login_allowed(self, user)`

Исходник: `core/admin_site.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

## `core/allocation.py`

Детерминированное распределение денежной суммы методом наибольших остатков.

Импорты: `decimal`, `django.core.exceptions`.

### `allocate_amount(amount, weights)`

Исходник: `core/allocation.py:8`.

Распределяет сумму в целых копейках по неотрицательным весам методом наибольших остатков. Порядок равных остатков устойчив, сумма долей строго равна исходной.

Статические вызовы: `Decimal`, `ValidationError`, `ValueError`, `amount.is_finite`, `amount.quantize`, `any`, `int`, `len`, `range`, `sorted`, `str`, `sum`, `value.to_integral_value`, `weight.is_finite`.

## `core/apps.py`

Конфигурация приложения и его регистрация в Django общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев.

Импорты: `django.apps`.

## `core/context_processors.py`

Контекст общей шапки: доступные пункты, склады и локальные счётчики; видимость не заменяет backend-защиту.

Импорты: `django.db.utils`, `integrations.required_actions`, `partners.models`, `sales.models`, `warehouse.models`.

### `crm_header(request)`

Исходник: `core/context_processors.py:8`.

Единый контекст шапки без каких-либо внешних сетевых запросов.

Статические вызовы: `MarketOrderAttention.objects.filter`, `MarketOrderAttention.objects.filter(acknowledged_at__isnull=True).count`, `SalesPlatform.objects.values`, `Warehouse.objects.values`, `get_avito_required_action_counts`, `getattr`, `len`, `list`, `user.has_perm`.

## `core/db_retry.py`

Повтор целой атомарной операции при кратком конфликте записи SQLite.

Импорты: `django.db`, `functools`.

### `retry_database_lock(function)`

Исходник: `core/db_retry.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `function`, `range`, `str`, `str(exc).lower`, `time.sleep`, `wraps`.

## `core/decorators.py`

Общие проверки аутентификации и permissions для HTTP-обработчиков CRM.

Импорты: `django.contrib.auth.views`, `django.core.exceptions`, `functools`.

### `permission_required_any(*permissions)`

Исходник: `core/decorators.py:8`.

Проверяет наличие хотя бы одного права и защищает прямой URL.

Статические вызовы: `PermissionDenied`, `any`, `redirect_to_login`, `request.get_full_path`, `request.user.has_perm`, `view_func`, `wraps`.

### `permission_required_all(*permissions)`

Исходник: `core/decorators.py:22`.

Требует все перечисленные права; superuser проходит штатно.

Статические вызовы: `PermissionDenied`, `all`, `redirect_to_login`, `request.get_full_path`, `request.user.has_perm`, `view_func`, `wraps`.

## `core/environment_context.py`

Режим для HTML задаётся сервером и не читается из GET/cookie/JavaScript.

Импорты: `django.conf`, `django.core.exceptions`, `django.http`.

### `environment(request)`

Исходник: `core/environment_context.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TestEnvironmentMiddleware.__init__(self, get_response)`

Исходник: `core/environment_context.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TestEnvironmentMiddleware.__call__(self, request)`

Исходник: `core/environment_context.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_response`.

### `TestEnvironmentMiddleware.process_exception(self, request, exception)`

Исходник: `core/environment_context.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `getattr`, `isinstance`.

## `core/excel_layout.py`

Размеры строк XLSX с учётом шрифта, переноса слов и явных переводов строки.

Импорты: `PIL`, `functools`, `math`, `pathlib`.

### `column_width_pixels(width)`

Исходник: `core/excel_layout.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `float`, `int`.

### `_font(name, size, bold)`

Исходник: `core/excel_layout.py:15`.

Декораторы: `lru_cache(maxsize=32)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ImageFont.load_default`, `ImageFont.truetype`, `Path`, `ceil`, `lru_cache`, `names.get`, `os.environ.get`, `str`.

### `text_width_pixels(text, *, font_name='Calibri', font_size=11, bold=False)`

Исходник: `core/excel_layout.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_font`, `font.getlength`, `max`, `str`, `str(text or '').splitlines`.

### `wrapped_text_height(text, width, *, font_name='Calibri', font_size=11, bold=False, padding_pixels=12, padding_points=4, min_height=24)`

Исходник: `core/excel_layout.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_font`, `ceil`, `column_width_pixels`, `font.getlength`, `len`, `max`, `paragraph.rstrip`, `remaining.rfind`, `remaining[cut:].lstrip`, `str`, `str(text or '').split`.

## `core/external_policy.py`

Одна политика перед реальным внешним эффектом, включая клиент с подменённым transport.

Импорты: `django.conf`, `django.core.exceptions`.

### `require_live_operation(operation)`

Исходник: `core/external_policy.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

## `core/management/commands/initialize_local_test.py`

Только синтетические пользователь/склад, без копирования рабочей базы.

Импорты: `django.conf`, `django.contrib.auth`, `django.core.management.base`, `django.db`, `warehouse.models`.

### `Command.handle(self, *args, **options)`

Исходник: `core/management/commands/initialize_local_test.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `User.objects.create_superuser`, `User.objects.filter`, `User.objects.filter(username='test-admin').exists`, `Warehouse.objects.get_or_create`, `get_user_model`, `json.dump`, `path.open`, `secrets.token_urlsafe`, `self.stdout.write`, `transaction.atomic`.

## `core/management/commands/seed_demo_data.py`

Заполнение локальной базы демонстрационными данными GameBAT CRM.

Импорты: `accounts.models`, `catalog.models`, `consignment.models`, `consignment.services`, `core.models`, `datetime`, `decimal`, `django.contrib.auth.models`, `django.core.management.base`, `django.db`, `django.utils`, `partners.models`, `supplies.models`, `supplies.services`, `warehouse.models`.

### `Command._permission(self, app_label, codename)`

Исходник: `core/management/commands/seed_demo_data.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Permission.objects.get`.

### `Command._reference(self, model, name)`

Исходник: `core/management/commands/seed_demo_data.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `model.objects.update_or_create`.

### `Command._supplier(self, letter, **defaults)`

Исходник: `core/management/commands/seed_demo_data.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Supplier.objects.update_or_create`.

### `Command._sales_platform(self, name, **defaults)`

Исходник: `core/management/commands/seed_demo_data.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SalesPlatform.objects.create`, `SalesPlatform.objects.filter`, `SalesPlatform.objects.filter(name=name).first`, `defaults.items`, `obj.save`, `setattr`.

### `Command._product(self, model, sku, defaults)`

Исходник: `core/management/commands/seed_demo_data.py:42`.

Обновляет описание демо-товара, не повреждая рассчитанные остатки.

Статические вызовы: `defaults.items`, `model.objects.create`, `model.objects.filter`, `model.objects.filter(sku=sku).first`, `product.save`, `setattr`, `tuple`.

### `Command._worker(self, username, **defaults)`

Исходник: `core/management/commands/seed_demo_data.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `User`, `User.objects.filter`, `User.objects.filter(username=username).first`, `defaults.items`, `setattr`, `tuple`, `worker.save`, `worker.set_unusable_password`.

### `Command.handle(self, *args, **options)`

Исходник: `core/management/commands/seed_demo_data.py:65`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.count`, `CDConsignmentStock.objects.count`, `CurrencyRate.objects.update_or_create`, `Decimal`, `Group.objects.get_or_create`, `PermissionSetMetadata.objects.update_or_create`, `Supplier.objects.count`, `Supply.objects.count`, `Supply.objects.filter`, `Supply.objects.filter(cd_items__product__sku=marker_sku).exists`, `Supply.objects.filter(pk=supply.pk).update`, `Supply.objects.filter(tech_items__product__sku=marker_sku).exists`, `Tech.objects.count`, `TechConsignmentStock.objects.count`, `User.objects.count`, `User.objects.filter`, `User.objects.filter(username='admin').first`, `Warehouse.objects.get_or_create`, `accept_supply`, `admin.save`, `group.permissions.set`, `manager.groups.add`, `manager.user_permissions.add`, `self._permission`, `self._product`, `self._reference`, `self._sales_platform`, `self._supplier`, `self._worker`, `self.stderr.write`, `self.stdout.write`, `self.style.SUCCESS`, `stock_model.objects.filter`, `stock_model.objects.filter(platform=platform, **{product_field: product}).first`, `supply_worker.groups.add`, `timedelta`, `timezone.now`, `transfer_to_consignment`, `warehouse_worker.groups.add`.

## `core/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев.

Импорты: `django.core.validators`, `django.db`.

### `CurrencyRate.__str__(self)`

Исходник: `core/models.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_pair_display`.

## `core/services/__init__.py`

Интеграции core с внешними сервисами.

## `core/services/coinbase.py`

Получение валютной оценки для шапки из Coinbase; курсы старых документов этим не пересчитываются.

Импорты: `core.external_policy`, `decimal`, `django.conf`, `django.core.cache`, `django.utils`, `urllib.error`, `urllib.parse`, `urllib.request`.

### `_exchange_rates_url()`

Исходник: `core/services/coinbase.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `dict`, `parse_qsl`, `parts._replace`, `urlencode`, `urlsplit`, `urlunsplit`.

### `fetch_usdt_aed_rate()`

Исходник: `core/services/coinbase.py:33`.

Получает прямой курс: количество AED за один USDT.

Статические вызовы: `CoinbaseAPIError`, `Decimal`, `Request`, `_exchange_rates_url`, `data.get`, `getattr`, `isinstance`, `json.loads`, `payload.get`, `rate.is_finite`, `raw_body.decode`, `require_live_operation`, `response.getcode`, `response.read`, `str`, `urlopen`.

### `_unavailable_snapshot()`

Исходник: `core/services/coinbase.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `get_cached_usdt_aed_rate()`

Исходник: `core/services/coinbase.py:93`.

Возвращает 30-секундный cache курса и сохраняет last-known-good.

Статические вызовы: `_unavailable_snapshot`, `cache.add`, `cache.delete`, `cache.get`, `cache.set`, `fetch_usdt_aed_rate`, `int`, `logger.warning`, `max`, `timezone.now`, `timezone.now().isoformat`.

## `core/services/rapira.py`

Получение USDT/RUB для шапки из Rapira; сетевые ошибки обрабатываются отдельно от учётных операций.

Импорты: `core.external_policy`, `decimal`, `django.conf`, `django.core.cache`, `django.utils`, `urllib.error`, `urllib.request`.

### `_number(value, *, allow_negative=False)`

Исходник: `core/services/rapira.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `format`, `isinstance`, `number.is_finite`, `str`.

### `fetch_market_rates(symbols=HEADER_RATE_SYMBOLS)`

Исходник: `core/services/rapira.py:38`.

Получает из Rapira только запрошенные пары и поля close/change.

Статические вызовы: `Decimal`, `RapiraAPIError`, `Request`, `_number`, `getattr`, `isinstance`, `item.get`, `json.loads`, `payload.get`, `raw_body.decode`, `require_live_operation`, `response.getcode`, `response.read`, `tuple`, `urlopen`.

### `_unavailable_snapshot()`

Исходник: `core/services/rapira.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `get_cached_market_rates()`

Исходник: `core/services/rapira.py:91`.

Возвращает общий 15-секундный кэш, сохраняя последний успешный ответ.

Статические вызовы: `_unavailable_snapshot`, `cache.add`, `cache.delete`, `cache.get`, `cache.set`, `fetch_market_rates`, `int`, `logger.warning`, `max`, `timezone.now`, `timezone.now().isoformat`.

## `core/update_health.py`

Короткая проверка версии/БД/worker для менеджера, без внешних API и изменений данных.

Импорты: `deployment.version`, `django.conf`, `django.db`, `django.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `integrations.worker_monitoring`.

### `update_health(request)`

Исходник: `core/update_health.py:13`.

Декораторы: `require_GET`; `never_cache`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `all`, `bool`, `connection.ensure_connection`, `connection.is_usable`, `current_version`, `monitoring_snapshot`.

## `core/update_views.py`

Страница создаёт только ограниченную заявку; Git/Docker в HTTP не вызываются.

Импорты: `datetime`, `deployment`, `deployment.gateway`, `deployment.store`, `deployment.version`, `django.conf`, `django.contrib`, `django.contrib.auth.decorators`, `django.core.exceptions`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.http`, `pathlib`.

### `update_state()`

Исходник: `core/update_views.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `UpdateError`, `getattr`, `json.loads`, `path.is_absolute`, `path.read_text`, `path.resolve`, `path.stat`.

### `manager_ready(heartbeat)`

Исходник: `core/update_views.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(datetime.now(timezone.utc) - datetime.fromisoformat(heartbeat['at'])).total_seconds`, `datetime.fromisoformat`, `datetime.now`.

### `updates(request)`

Исходник: `core/update_views.py:49`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `never_cache`; `login_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ACTION_LABELS.get`, `PermissionDenied`, `STAGE_LABELS.get`, `UpdateError`, `any`, `candidate.get`, `context.update`, `current_version`, `getattr`, `isinstance`, `manager_ready`, `messages.error`, `messages.info`, `messages.success`, `operation.get`, `redirect`, `render`, `request.POST.get`, `require_http_methods`, `state.get`, `str`, `submit`, `update_state`, `uuid.uuid4`.

## `core/urls.py`

Именованные HTTP-маршруты приложения общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев.

Импорты: `django.urls`, `update_health`.

## `core/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю общего ядра.

Общие компоненты не должны получать складскую логику отдельных сценариев.

Импорты: `cash.models`, `core.services.coinbase`, `core.services.rapira`, `django.contrib.auth.decorators`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `warehouse.models`.

### `exchange_rates(request)`

Исходник: `core/views.py:17`.

Декораторы: `login_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `get_cached_market_rates`, `get_cached_usdt_aed_rate`.

### `home(request)`

Исходник: `core/views.py:43`.

Декораторы: `login_required`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.select_related`, `CashRegister.objects.select_related('warehouse').first`, `Warehouse.objects.first`, `any`, `redirect`, `render`, `request.user.has_perm`.

### `permission_denied(request, exception=None)`

Исходник: `core/views.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `render`.

## `creditors/admin.py`

Регистрация моделей и разрешённых действий в Django Admin задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `django.contrib`, `models`.

### `CreditorAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `creditors/admin.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CreditorAdmin.save_model(self, request, obj, form, change)`

Исходник: `creditors/admin.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `logger.info`, `super`, `super().save_model`.

### `CreditorTransactionAdmin.has_add_permission(self, request)`

Исходник: `creditors/admin.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CreditorTransactionAdmin.has_change_permission(self, request, obj=None)`

Исходник: `creditors/admin.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CreditorTransactionAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `creditors/admin.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `creditors/apps.py`

Конфигурация приложения и его регистрация в Django задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `django.apps`.

## `creditors/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `decimal`, `django`, `models`, `warehouse.form_defaults`, `warehouse.models`.

### `DebtAdjustmentForm.clean(self)`

Исходник: `creditors/forms.py:54`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `self.add_error`, `super`, `super().clean`.

## `creditors/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `cash.models`, `django.conf`, `django.core.validators`, `django.db`, `django.db.models.functions`, `warehouse.models`.

### `Creditor.__str__(self)`

Исходник: `creditors/models.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Creditor.display_name(self)`

Исходник: `creditors/models.py:39`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`.

### `Creditor.debt_direction(self)`

Исходник: `creditors/models.py:44`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Creditor.debt_amount(self)`

Исходник: `creditors/models.py:48`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `abs`.

### `CreditorTransaction.__str__(self)`

Исходник: `creditors/models.py:115`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `creditors/services.py`

Атомарные расчёты с кредиторами через существующие кассу и сейф.

Импорты: `cash.models`, `core.db_retry`, `decimal`, `django.core.exceptions`, `django.db`, `models`, `warehouse.models`.

### `_debt(value, *, signed=False)`

Исходник: `creditors/services.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `abs`, `result.is_finite`, `str`.

### `adjust_creditor_debt(*, actor, creditor_id, warehouse_id, money_source_type, new_debt=None, debt_delta=None, comment='')`

Исходник: `creditors/services.py:31`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Корректирует абсолютный долг или дельту под блокировкой с журналом. Движение наличных/сейфа выбирается отдельно от банка и взаимозачёта.

Статические вызовы: `(new_debt - old_debt).quantize`, `CashRegister.objects.select_for_update`, `CashRegister.objects.select_for_update().get`, `CashTransaction.objects.create`, `Creditor.objects.select_for_update`, `Creditor.objects.select_for_update().get`, `CreditorTransaction.objects.create`, `PermissionDenied`, `Safe.objects.select_for_update`, `Safe.objects.select_for_update().get`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_debt`, `abs`, `actor.has_perm`, `creditor.full_clean`, `creditor.save`, `f"Кредитор «{creditor.name}». {action}. {str(comment or '').strip()}".strip`, `getattr`, `logger.info`, `storage.full_clean`, `storage.save`, `str`, `str(comment or '').strip`.

## `creditors/urls.py`

Именованные HTTP-маршруты приложения задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `django.urls`.

## `creditors/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю задолженности.

У связанного партнёра положительный долг — нам должны, отрицательный — мы должны.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db.models`, `django.db.models.functions`, `django.shortcuts`, `forms`, `models`, `services`.

### `creditor_list(request)`

Исходник: `creditors/views.py:21`.

Декораторы: `permission_required_any('creditors.view_creditors')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Case`, `Coalesce`, `Creditor.objects.select_related`, `Creditor.objects.select_related('partner').annotate`, `Creditor.objects.select_related('partner').annotate(debt_group=Case(When(current_debt__gt=0, then=Value(0)), When(current_debt__lt=0, then=Value(1)), default=Value(2), output_field=IntegerField()), list_name=Coalesce('partner__name', 'name')).order_by`, `IntegerField`, `Value`, `When`, `permission_required_any`, `render`, `request.user.has_perm`.

### `creditor_create(request)`

Исходник: `creditors/views.py:37`.

Декораторы: `permission_required_any('creditors.add_creditor')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CreditorCreateForm`, `form.is_valid`, `form.save`, `logger.info`, `messages.success`, `permission_required_any`, `redirect`, `render`.

### `creditor_detail(request, pk)`

Исходник: `creditors/views.py:48`.

Декораторы: `permission_required_any('creditors.view_creditors')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Creditor.objects.select_related`, `creditor.transactions.select_related`, `get_object_or_404`, `permission_required_any`, `render`, `request.user.has_perm`.

### `creditor_edit(request, pk)`

Исходник: `creditors/views.py:61`.

Декораторы: `permission_required_any('creditors.change_creditor')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CreditorEditForm`, `form.is_valid`, `form.save`, `get_object_or_404`, `logger.info`, `messages.success`, `permission_required_any`, `redirect`, `render`.

### `creditor_debt(request, pk)`

Исходник: `creditors/views.py:79`.

Декораторы: `permission_required_any('creditors.change_debt')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `DebtAdjustmentForm`, `adjust_creditor_debt`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `messages.success`, `permission_required_any`, `redirect`, `render`.

## `integrations/admin.py`

Регистрация моделей и разрешённых действий в Django Admin Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `django.contrib`, `models`.

### `IntegrationCredentialAdmin.has_add_permission(self, request)`

Исходник: `integrations/admin.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `IntegrationCredentialAdmin.has_change_permission(self, request, obj=None)`

Исходник: `integrations/admin.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadOnlyHistoryAdmin.has_add_permission(self, request)`

Исходник: `integrations/admin.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadOnlyHistoryAdmin.has_change_permission(self, request, obj=None)`

Исходник: `integrations/admin.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadOnlyHistoryAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `integrations/admin.py:68`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `integrations/apps.py`

Конфигурация приложения и его регистрация в Django Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `django.apps`.

### `IntegrationsConfig.ready(self)`

Исходник: `integrations/apps.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `integrations/avito_check.py`

Ручная проверка конкурентных объявлений без изменения товара или Avito-профиля.

Импорты: `catalog.models`, `concurrent.futures`, `datetime`, `decimal`, `django.conf`, `django.db.models`, `django.db.models.functions`, `django.utils`, `models`, `reef_api`, `urllib.parse`.

### `_media_text(row)`

Исходник: `integrations/avito_check.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `''.join`, `_param_text`, `normalize`, `row.get`, `str`, `unicodedata.category`.

### `physical_game(row)`

Исходник: `integrations/avito_check.py:44`.

Неизвестный носитель не считается подтверждённым физическим изданием.

Статические вызовы: `DIGITAL_GAME.search`, `NO_PHYSICAL_GAME.search`, `PHYSICAL_GAME.search`, `_media_text`, `bool`.

### `_fix_mixed_script(match)`

Исходник: `integrations/avito_check.py:75`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `match.group`, `sum`, `token.translate`.

### `normalize(value)`

Исходник: `integrations/avito_check.py:84`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `int`, `match.group`, `re.sub`, `str`, `unicodedata.normalize`, `value.casefold`, `value.casefold().replace`, `value.replace`, `value.split`.

### `_words(value)`

Исходник: `integrations/avito_check.py:108`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize`, `normalize(value).split`, `set`.

### `_price(row)`

Исходник: `integrations/avito_check.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `any`, `isinstance`, `price.is_finite`, `row.get`, `str`.

### `suspicious_price(row, product_price, description='')`

Исходник: `integrations/avito_check.py:128`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `MONEY.findall`, `PLACEHOLDER.search`, `_price`, `any`, `bool`, `raw.replace`, `raw.replace(' ', '').replace`, `str`.

### `_param_text(row)`

Исходник: `integrations/avito_check.py:140`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `isinstance`, `p.get`, `params.items`, `parts.append`, `parts.extend`, `row.get`.

### `new_condition(row)`

Исходник: `integrations/avito_check.py:153`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`, `len`, `normalize`, `p.get`, `row.get`.

### `_variant(value)`

Исходник: `integrations/avito_check.py:161`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_words`, `re.fullmatch`.

### `_game_title(product)`

Исходник: `integrations/avito_check.py:169`.

Убирает только известный платформенный префикс и служебный код карточки.

Статические вызовы: `' '.join`, `_variant`, `getattr`, `iter`, `len`, `next`, `normalize`, `prefixes.get`, `re.escape`, `re.findall`, `re.sub`, `set`, `str`, `str(product.name or '').strip`, `title.split`.

### `_game_identity(product)`

Исходник: `integrations/avito_check.py:186`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_game_title`, `_variant`, `_words`, `any`, `getattr`, `len`, `normalize`, `normalize(profile_title).split`, `normalize(title).split`, `profile_title.split`, `range`, `re.sub`, `set`, `str`, `word.isdecimal`, `zip`.

### `_one_typo(left, right)`

Исходник: `integrations/avito_check.py:224`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `abs`, `any`, `enumerate`, `len`, `range`, `sorted`, `zip`.

### `_game_words_match(game_title, listing_title)`

Исходник: `integrations/avito_check.py:235`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_one_typo`, `actual.update`, `any`, `bool`, `matched.update`, `normalize`, `normalize(game_title).split`, `normalize(listing_title).split`, `set`, `word.isdecimal`, `zip`.

### `product_matches(product, kind, row)`

Исходник: `integrations/avito_check.py:248`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BLOCKED.search`, `DIGITAL_GAME.search`, `GAME_ACCESSORY.search`, `NO_PHYSICAL_GAME.search`, `_game_identity`, `_game_words_match`, `_media_text`, `_param_text`, `_variant`, `_words`, `category.get`, `isinstance`, `re.search`, `row.get`, `str`.

### `queue()`

Исходник: `integrations/avito_check.py:289`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().filter`, `CD.objects.active().filter(avito_profile__connection__isnull=False).annotate`, `CD.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter`, `CD.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related`, `CD.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related('platform', 'game_series', 'avito_profile').order_by`, `Coalesce`, `IntegerField`, `Sum`, `Tech.objects.active`, `Tech.objects.active().filter`, `Tech.objects.active().filter(avito_profile__connection__isnull=False).annotate`, `Tech.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter`, `Tech.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related`, `Tech.objects.active().filter(avito_profile__connection__isnull=False).annotate(check_stock=stock).filter(check_stock__gt=0).select_related('brand', 'product_type', 'avito_profile').order_by`, `Value`.

### `_avito_url(value)`

Исходник: `integrations/avito_check.py:296`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `urlparse`.

### `_image(value)`

Исходник: `integrations/avito_check.py:301`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parsed.hostname.endswith`, `str`, `urlparse`.

### `_city(full, brief)`

Исходник: `integrations/avito_check.py:306`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`, `location.get`, `row.get`, `str`.

### `_search_query(product, kind)`

Исходник: `integrations/avito_check.py:314`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_game_identity`, `normalize`.

### `manual_search_url(product, kind)`

Исходник: `integrations/avito_check.py:320`.

Коды фильтров сверены с формой поиска Avito; платформа остаётся в запросе.

Статические вызовы: `_search_query`, `_variant`, `urlencode`.

### `_search_candidates(client, query, product, kind, own_ids, page_limit, stats)`

Исходник: `integrations/avito_check.py:343`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PLACEHOLDER.search`, `ReefApiError`, `_price`, `ad_id.isdecimal`, `bool`, `candidates.items`, `client.search`, `data.get`, `int`, `isinstance`, `product_matches`, `range`, `row.get`, `sorted`, `str`.

### `_fetch_listing(client, ad_id)`

Исходник: `integrations/avito_check.py:368`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `client.listing`, `client.listing(ad_id).get`.

### `_validated_offer(product, kind, ad_id, brief, full)`

Исходник: `integrations/avito_check.py:377`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_avito_url`, `_city`, `_image`, `_price`, `brief.get`, `full.get`, `isinstance`, `new_condition`, `physical_game`, `product_matches`, `seller.get`, `str`, `str(full.get('status') or '').lower`, `suspicious_price`.

### `_rank_candidates(client, product, kind, ordered, detail_limit, stats, *, force=False)`

Исходник: `integrations/avito_check.py:403`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoCheckListingCache.objects.filter`, `AvitoCheckListingCache.objects.update_or_create`, `Decimal`, `ThreadPoolExecutor`, `_fetch_listing`, `_price`, `_validated_offer`, `brief.get`, `cached[ad_id].get`, `executor.map`, `full.get`, `int`, `isinstance`, `len`, `max`, `min`, `normalize`, `offers.append`, `sorted`, `str`, `timezone.now`, `zip`.

### `search_offers(product, kind, *, client=None, mode='economy', stats=None, force=False)`

Исходник: `integrations/avito_check.py:447`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.values_list`, `ReefApiClient`, `_rank_candidates`, `_search_candidates`, `_search_query`, `set`, `stats.update`.

### `_check_signature(product, kind)`

Исходник: `integrations/avito_check.py:460`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(product.avito_price)).normalize`, `_search_query`, `getattr`, `hashlib.sha256`, `hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest`, `json.dumps`, `json.dumps(values, ensure_ascii=False).encode`, `str`.

### `display_result(product, kind)`

Исходник: `integrations/avito_check.py:467`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoPriceCheckResult.objects.filter`, `AvitoPriceCheckResult.objects.filter(profile=product.avito_profile).first`, `_check_signature`, `result.metadata.get`, `timezone.now`.

### `run_check(product, kind, *, client=None, mode='economy', force=False)`

Исходник: `integrations/avito_check.py:476`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoPriceCheckResult.objects.update_or_create`, `ValueError`, `_check_signature`, `display_result`, `result.metadata.get`, `search_offers`, `stats.update`, `timezone.now`.

## `integrations/client.py`

HTTP-клиент реального Avito: авторизация, таймауты и ошибки API. Для тестов клиент подменяется.

Импорты: `core.external_policy`, `crypto`, `dataclasses`, `django.conf`, `django.core.cache`, `models`, `urllib`.

### `AvitoAPIError.__str__(self)`

Исходник: `integrations/client.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoAPIError.retryable(self)`

Исходник: `integrations/client.py:26`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoClient.__init__(self, credential=None)`

Исходник: `integrations/client.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `IntegrationCredential.objects.get`, `require_live_operation`, `settings.AVITO_API_BASE_URL.rstrip`.

### `AvitoClient._decode(self, response)`

Исходник: `integrations/client.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `json.loads`, `raw.decode`, `response.read`.

### `AvitoClient._execute(self, req, *, retry_network=False)`

Исходник: `integrations/client.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `exc.headers.get`, `int`, `isinstance`, `range`, `req.get_method`, `request.urlopen`, `require_live_operation`, `self._decode`, `str`, `str(reason).lower`, `time.sleep`.

### `AvitoClient._token(self)`

Исходник: `integrations/client.py:89`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `cache.get`, `cache.set`, `data.get`, `decrypt_secret`, `int`, `max`, `parse.urlencode`, `parse.urlencode({'grant_type': 'client_credentials', 'client_id': decrypt_secret(self.credential.encrypted_client_id), 'client_secret': decrypt_secret(self.credential.encrypted_client_secret)}).encode`, `request.Request`, `require_live_operation`, `self._execute`, `self.credential.updated_at.timestamp`.

### `AvitoClient.request_json(self, method, path, *, payload=None, query=None, retry_network=False)`

Исходник: `integrations/client.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `json.dumps`, `json.dumps(payload).encode`, `parse.urlencode`, `request.Request`, `require_live_operation`, `self._execute`, `self._token`.

### `AvitoClient.get_self(self)`

Исходник: `integrations/client.py:128`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.request_json`.

### `AvitoClient.list_items(self, *, page=1, per_page=100)`

Исходник: `integrations/client.py:131`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.request_json`.

### `AvitoClient.find_item(self, item_id)`

Исходник: `integrations/client.py:134`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `data.get`, `int`, `item.get`, `len`, `range`, `self.list_items`.

### `AvitoClient.get_item_details(self, account_id, item_id)`

Исходник: `integrations/client.py:146`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.request_json`.

### `AvitoClient.get_category_tree(self)`

Исходник: `integrations/client.py:149`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.request_json`.

### `AvitoClient.get_category_fields(self, category_slug)`

Исходник: `integrations/client.py:152`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parse.quote`, `self.request_json`, `str`.

### `AvitoClient.get_autoload_profile(self)`

Исходник: `integrations/client.py:156`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.request_json`.

### `AvitoClient.get_stocks(self, item_ids, *, strong_consistency=True)`

Исходник: `integrations/client.py:159`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `self.request_json`.

### `AvitoClient.update_stock(self, item_id, quantity)`

Исходник: `integrations/client.py:166`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `self.request_json`.

### `AvitoClient.update_price(self, item_id, price)`

Исходник: `integrations/client.py:173`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `self.request_json`.

## `integrations/crypto.py`

Шифрование реквизитов интеграций локальным ключом вне Git; утрата ключа не исправляется откатом кода.

Импорты: `cryptography.fernet`, `django.conf`, `django.core.exceptions`, `pathlib`.

### `_key()`

Исходник: `integrations/crypto.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Fernet`, `Fernet.generate_key`, `ImproperlyConfigured`, `Path`, `configured.encode`, `path.chmod`, `path.exists`, `path.read_bytes`, `path.read_bytes().strip`, `path.write_bytes`, `str`, `str(settings.INTEGRATION_ENCRYPTION_KEY or '').strip`.

### `encrypt_secret(value: str)`

Исходник: `integrations/crypto.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Fernet`, `Fernet(_key()).encrypt`, `Fernet(_key()).encrypt(value.encode('utf-8')).decode`, `_key`, `str`, `value.encode`.

### `decrypt_secret(value: str)`

Исходник: `integrations/crypto.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Fernet`, `Fernet(_key()).decrypt`, `Fernet(_key()).decrypt(value.encode('ascii')).decode`, `ImproperlyConfigured`, `_key`, `value.encode`.

## `integrations/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `catalog.models`, `django`, `django.core.exceptions`, `django.db.models`, `models`.

### `AvitoProfileForm.clean_attributes(self)`

Исходник: `integrations/forms.py:39`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(pk=self.instance.pk).values_list`, `AvitoProductProfile.objects.filter(pk=self.instance.pk).values_list('attributes', flat=True).first`, `ValidationError`, `isinstance`, `self.cleaned_data.get`.

### `AvitoPhotoForm.clean_image(self)`

Исходник: `integrations/forms.py:57`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `getattr`.

### `ProductTargetForm.__init__(self, *args, query='', exclude_connected=True, **kwargs)`

Исходник: `integrations/forms.py:70`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().select_related`, `Q`, `Tech.objects.active`, `Tech.objects.active().select_related`, `cd_qs.distinct`, `cd_qs.filter`, `str`, `str(query or '').strip`, `super`, `super().__init__`, `tech_qs.distinct`, `tech_qs.filter`.

### `ProductTargetForm.clean_product_ref(self)`

Исходник: `integrations/forms.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `hasattr`, `int`, `model.objects.active`, `model.objects.active().filter`, `model.objects.active().filter(pk=product_id).first`, `value.split`.

## `integrations/google_sheets.py`

Односторонняя публикация номенклатуры/физического наличия в Google Sheets; лист не источник складских движений.

Импорты: `catalog.models`, `core.external_policy`, `decimal`, `django.conf`, `django.core.exceptions`, `django.db.models`, `django.db.models.functions`, `django.utils`, `google.oauth2`, `googleapiclient.discovery`, `models`.

### `extract_spreadsheet_id(url)`

Исходник: `integrations/google_sheets.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SPREADSHEET_ID_RE.search`, `ValidationError`, `match.group`, `str`, `str(url or '').strip`.

### `get_google_sheets_integration()`

Исходник: `integrations/google_sheets.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GoogleSheetsIntegration.objects.get_or_create`, `bool`, `extract_spreadsheet_id`, `str`, `str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or '').strip`.

### `save_google_sheets_settings(*, spreadsheet_url, sheet_name, enabled)`

Исходник: `integrations/google_sheets.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `NOMENCLATURE_SHEET_NAME.casefold`, `ValidationError`, `bool`, `extract_spreadsheet_id`, `get_google_sheets_integration`, `integration.full_clean`, `integration.save`, `integration.sheet_name.casefold`, `str`, `str(sheet_name or '').strip`, `str(spreadsheet_url or '').strip`.

### `_calendar_month_before(value)`

Исходник: `integrations/google_sheets.py:67`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `calendar.monthrange`, `min`, `value.replace`.

### `_sheet_money(value)`

Исходник: `integrations/google_sheets.py:75`.

Передаёт денежное значение числом через точную формулу, без преобразования Decimal во float.

Статические вызовы: `Decimal`, `Decimal(value).quantize`, `int`.

### `_all_products(model, related)`

Исходник: `integrations/google_sheets.py:81`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Coalesce`, `OuterRef`, `ProductFieldChange.objects.filter`, `ProductFieldChange.objects.filter(field_name='created', **{f'event__{model._meta.model_name}_id': OuterRef('pk')}).order_by`, `ProductFieldChange.objects.filter(field_name='created', **{f'event__{model._meta.model_name}_id': OuterRef('pk')}).order_by('event__created_at', 'pk').values`, `Subquery`, `Sum`, `list`, `model.objects.active`, `model.objects.active().select_related`, `model.objects.active().select_related(*related).annotate`, `model.objects.active().select_related(*related).annotate(global_quantity=Coalesce(Sum('warehouse_stocks__quantity'), 0), catalog_created_at=Subquery(created)).order_by`.

### `_available_product(product, cutoff)`

Исходник: `integrations/google_sheets.py:95`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `build_price_rows(*, nomenclature=False, tech=None, cds=None, now=None)`

Исходник: `integrations/google_sheets.py:107`.

Строит номенклатуру или наличие; заголовки добавляются только к выбранным товарам.

Статические вызовы: `_all_products`, `_available_product`, `_calendar_month_before`, `_sheet_money`, `heading_rows.add`, `int`, `len`, `rows.append`, `timezone.now`, `zero_rows.append`.

### `_google_service()`

Исходник: `integrations/google_sheets.py:157`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RuntimeError`, `build`, `require_live_operation`, `service_account.Credentials.from_service_account_file`, `str`, `str(settings.GOOGLE_SERVICE_ACCOUNT_FILE or '').strip`.

### `_row_ranges(row_numbers)`

Исходник: `integrations/google_sheets.py:169`.

Объединяет соседние строки, чтобы не отправлять тысячи отдельных запросов оформления.

Статические вызовы: `sorted`.

### `_sheet_format_requests(sheet_id, rows, heading_rows, zero_rows, basic_filter)`

Исходник: `integrations/google_sheets.py:183`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_row_ranges`, `dict`, `expanded_filter.pop`, `expanded_filter['range'].pop`, `filter_range.get`, `len`, `requests.append`, `requests.extend`.

### `_sheet_range(name, cells='A:D')`

Исходник: `integrations/google_sheets.py:258`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `name.replace`.

### `sync_price_sheet(integration=None)`

Исходник: `integrations/google_sheets.py:263`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `NOMENCLATURE_SHEET_NAME.casefold`, `ValidationError`, `_all_products`, `_google_service`, `_sheet_format_requests`, `_sheet_range`, `build_price_rows`, `exports.items`, `filter_state.get`, `filters.get`, `get_google_sheets_integration`, `integration.save`, `integration.sheet_name.casefold`, `item.get`, `len`, `list`, `max`, `prepare_requests.append`, `prepared.get`, `ranges.values`, `requests.extend`, `require_live_operation`, `service.spreadsheets`, `service.spreadsheets().batchUpdate`, `service.spreadsheets().batchUpdate(spreadsheetId=integration.spreadsheet_id, body={'requests': prepare_requests}).execute`, `service.spreadsheets().batchUpdate(spreadsheetId=integration.spreadsheet_id, body={'requests': requests}).execute`, `service.spreadsheets().get`, `service.spreadsheets().get(spreadsheetId=integration.spreadsheet_id, fields='sheets(properties,basicFilter)').execute`, `service.spreadsheets().get(spreadsheetId=integration.spreadsheet_id, fields='sheets(properties.sheetId,basicFilter)').execute`, `service.spreadsheets().values`, `service.spreadsheets().values().batchClear`, `service.spreadsheets().values().batchClear(spreadsheetId=integration.spreadsheet_id, body={'ranges': list(ranges.values())}).execute`, `service.spreadsheets().values().batchUpdate`, `service.spreadsheets().values().batchUpdate(spreadsheetId=integration.spreadsheet_id, body={'valueInputOption': 'RAW', 'data': [{'range': _sheet_range(name, 'E1'), 'values': [[timestamp]]} for name in exports]}).execute`, `service.spreadsheets().values().batchUpdate(spreadsheetId=integration.spreadsheet_id, body={'valueInputOption': 'USER_ENTERED', 'data': [{'range': ranges[name], 'values': data[0]} for name, data in exports.items()]}).execute`, `spreadsheet.get`, `str`, `timezone.localtime`, `timezone.localtime(synced_at).strftime`, `timezone.now`.

## `integrations/google_tasks.py`

Назначение и выполнение заданий Sheets с периодичностью и защитой от повторного запуска.

Импорты: `datetime`, `django.db`, `django.utils`, `google_sheets`, `models`.

### `enqueue_google_sheets_sync(*, requested_by=None, manual=False)`

Исходник: `integrations/google_tasks.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GoogleSheetsSyncJob.objects.get_or_create`, `get_google_sheets_integration`, `integration.save`, `job.save`, `timezone.now`.

### `ensure_periodic_google_sheets_job()`

Исходник: `integrations/google_tasks.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GoogleSheetsSyncJob.objects.filter`, `GoogleSheetsSyncJob.objects.filter(status=GoogleSheetsSyncJob.Status.RUNNING, updated_at__lt=now - timedelta(minutes=15)).update`, `GoogleSheetsSyncJob.objects.get_or_create`, `get_google_sheets_integration`, `job.save`, `timedelta`, `timezone.now`.

### `process_one_google_sheets_job()`

Исходник: `integrations/google_tasks.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GoogleSheetsSyncJob.objects.select_for_update`, `GoogleSheetsSyncJob.objects.select_for_update().filter`, `GoogleSheetsSyncJob.objects.select_for_update().filter(status=GoogleSheetsSyncJob.Status.PENDING, run_after__lte=timezone.now()).order_by`, `GoogleSheetsSyncJob.objects.select_for_update().filter(status=GoogleSheetsSyncJob.Status.PENDING, run_after__lte=timezone.now()).order_by('run_after', 'id').first`, `ensure_periodic_google_sheets_job`, `job.save`, `len`, `str`, `sync_price_sheet`, `timedelta`, `timezone.now`, `transaction.atomic`.

## `integrations/linux_processes.py`

Локальные процессы одного Linux PID namespace; доступ к Docker socket не нужен.

Импорты: `core.external_policy`, `django.conf`, `pathlib`, `worker_runtime`.

### `LinuxProcesses.__init__(self, proc_root=Path('/proc'))`

Исходник: `integrations/linux_processes.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`.

### `LinuxProcesses.inventory(self)`

Исходник: `integrations/linux_processes.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(proc / 'cmdline').read_bytes`, `(proc / 'cmdline').read_bytes().decode`, `(proc / 'cmdline').read_bytes().decode().rstrip`, `(proc / 'cmdline').read_bytes().decode().rstrip('\x00').split`, `(proc / 'stat').read_text`, `(proc / 'stat').read_text().rsplit`, `(proc / 'stat').read_text().rsplit(')', 1)[1].split`, `Path`, `Path(settings.BASE_DIR).resolve`, `any`, `dict`, `enumerate`, `int`, `next`, `os.readlink`, `p.name.isdigit`, `proc.name.isdigit`, `require_live_operation`, `rows.append`, `script.is_absolute`, `script.resolve`, `self._option`, `self.proc_root.iterdir`, `sorted`, `str`, `uuid.UUID`.

### `LinuxProcesses._option(args, name)`

Исходник: `integrations/linux_processes.py:57`.

Декораторы: `staticmethod`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `arg.split`, `arg.startswith`, `enumerate`.

### `LinuxProcesses.launch(self, service, instance)`

Исходник: `integrations/linux_processes.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(folder / f'{instance}.stderr.log').open`, `(folder / f'{instance}.stdout.log').open`, `Path`, `ValueError`, `folder.mkdir`, `require_live_operation`, `str`, `subprocess.Popen`, `uuid.UUID`.

## `integrations/management/commands/configure_worker_monitoring.py`

Явная политика штатного запуска, не изменяющая настройки бизнес-интеграций.

Импорты: `django.core.management.base`, `django.db`, `django.utils`, `integrations.worker_models`, `integrations.worker_runtime`.

### `Command.add_arguments(self, parser)`

Исходник: `integrations/management/commands/configure_worker_monitoring.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `integrations/management/commands/configure_worker_monitoring.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `WorkerController.objects.get_or_create`, `WorkerController.objects.update_or_create`, `controller.save`, `process_lock`, `timezone.now`.

## `integrations/management/commands/import_avito_credentials.py`

Перенос секретных реквизитов Avito в защищённое хранилище; значения не выводить и не коммитить.

Импорты: `django.core.management.base`, `integrations.services`, `pathlib`.

### `Command.add_arguments(self, parser)`

Исходник: `integrations/management/commands/import_avito_credentials.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `integrations/management/commands/import_avito_credentials.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `Path`, `match.group`, `path.is_file`, `path.read_text`, `re.search`, `save_avito_credentials`, `self.stdout.write`, `self.style.SUCCESS`.

## `integrations/management/commands/run_integration_worker.py`

Фоновый исполнитель очередей Avito/Яндекс/Sheets; даже --once может менять реальные внешние данные.

Импорты: `django.core.management.base`, `django.db`, `integrations.google_tasks`, `integrations.tasks`, `integrations.worker_heartbeat`, `integrations.worker_runtime`, `yandex_market.tasks`.

### `Command.add_arguments(self, parser)`

Исходник: `integrations/management/commands/run_integration_worker.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `integrations/management/commands/run_integration_worker.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `close_old_connections`, `connections.close_all`, `graceful_shutdown`, `max`, `monitored_worker`, `processors[service]`, `self.stdout.write`, `stop.is_set`, `stop.wait`, `tuple`.

## `integrations/management/commands/run_worker_supervisor.py`

Единственный локальный владелец восстановления; может возобновлять реальные очереди.

Импорты: `django.core.management.base`, `django.db`, `integrations.worker_monitoring`, `integrations.worker_processes`, `integrations.worker_runtime`.

### `Command.add_arguments(self, parser)`

Исходник: `integrations/management/commands/run_worker_supervisor.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `integrations/management/commands/run_worker_supervisor.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `close_old_connections`, `connections.close_all`, `process_adapter`, `process_lock`, `self.stderr.write`, `self.stdout.write`, `supervise_once`, `time.sleep`, `uuid.uuid4`.

## `integrations/management/commands/verify_avito_sync.py`

Сверка с реальным Avito; без --fix остаётся сетевой операцией, с --fix может менять объявления.

Импорты: `dataclasses`, `django.core.management.base`, `django.utils`, `integrations.client`, `integrations.verification`, `pathlib`.

### `Command.add_arguments(self, parser)`

Исходник: `integrations/management/commands/verify_avito_sync.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `integrations/management/commands/verify_avito_sync.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CommandError`, `Path`, `asdict`, `csv.DictWriter`, `output.open`, `output.parent.mkdir`, `output.resolve`, `self.stdout.write`, `str`, `timezone.now`, `verification_summary`, `verify_avito_connections`, `writer.writeheader`, `writer.writerow`.

## `integrations/manual_sync.py`

Сверка связанных активных объявлений с фактическим состоянием Avito.

Импорты: `client`, `django.utils`, `models`, `services`, `verification`.

### `_update_progress(job, **values)`

Исходник: `integrations/manual_sync.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `job.save`, `setattr`, `values.items`, `values.keys`.

### `_api_error(exc)`

Исходник: `integrations/manual_sync.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`.

### `_accepted(payload, *, field)`

Исходник: `integrations/manual_sync.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `any`, `isinstance`, `payload.get`, `result.get`, `row.get`.

### `reconcile_active_listings(*, job=None, client=None)`

Исходник: `integrations/manual_sync.py:37`.

Сравнить, исправить только расхождения и повторно прочитать Avito.

Неактивные/исчезнувшие объявления не меняются: их цену нельзя надёжно
прочитать из актуального списка. Ошибка одного товара не прерывает остальные.

Статические вызовы: `' '.join`, `AvitoClient`, `AvitoListingConnection.objects.select_related`, `AvitoListingConnection.objects.select_related('profile__cd', 'profile__tech', 'remote_listing').order_by`, `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(pk=profile.pk).update`, `_accepted`, `_api_error`, `_update_progress`, `any`, `bool`, `client.update_price`, `client.update_stock`, `connection.remote_listing.status.lower`, `desired_state`, `details.append`, `errors.append`, `expected_price.to_integral_value`, `fetch_remote_stocks`, `final_read_errors.get`, `final_read_errors.update`, `final_stocks.get`, `global_stock`, `initial_read_errors.get`, `initial_read_errors.update`, `initial_stocks.get`, `int`, `len`, `list`, `listing.refresh_from_db`, `listing.status.lower`, `refresh_remote_listings`, `states.append`, `timezone.now`.

## `integrations/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `django.conf`, `django.core.exceptions`, `django.db`, `django.db.models`, `schema`, `worker_models`.

### `IntegrationCredential.is_configured(self)`

Исходник: `integrations/models.py:50`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `IntegrationCredential.masked_client_id(self)`

Исходник: `integrations/models.py:54`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `IntegrationCredential.masked_client_secret(self)`

Исходник: `integrations/models.py:58`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `IntegrationCredential.__str__(self)`

Исходник: `integrations/models.py:61`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.get_provider_display`.

### `ReefApiCredential.is_configured(self)`

Исходник: `integrations/models.py:72`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `AvitoProductProfile.product(self)`

Исходник: `integrations/models.py:162`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoProductProfile.product_kind(self)`

Исходник: `integrations/models.py:166`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoProductProfile.product_id(self)`

Исходник: `integrations/models.py:170`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoProductProfile.clean(self)`

Исходник: `integrations/models.py:173`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `bool`, `isinstance`, `super`, `super().clean`, `validate_attributes`.

### `AvitoProductProfile.__str__(self)`

Исходник: `integrations/models.py:183`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `avito_photo_upload_to(instance, filename)`

Исходник: `integrations/models.py:187`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `f"{instance.pk or 'new'}-{filename}".replace`.

### `AvitoRemoteListing.__str__(self)`

Исходник: `integrations/models.py:235`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `AvitoListingConnection.__str__(self)`

Исходник: `integrations/models.py:255`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `GoogleSheetsIntegration.__str__(self)`

Исходник: `integrations/models.py:377`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `integrations/queue.py`

Отложенная дедуплицированная очередь Avito. Изменение товара назначается после commit, не внутри откатываемой операции.

Импорты: `datetime`, `django.conf`, `django.db`, `django.db.utils`, `django.utils`, `models`.

### `ensure_required_actions_refresh()`

Исходник: `integrations/queue.py:13`.

Декораторы: `transaction.atomic`.

Одна общая задача ручной и автоматической проверки статусов каждые 15 минут.

Статические вызовы: `AvitoSyncJob.objects.select_for_update`, `AvitoSyncJob.objects.select_for_update().get_or_create`, `IntegrationCredential.objects.filter`, `IntegrationCredential.objects.filter(provider='avito').exclude`, `IntegrationCredential.objects.filter(provider='avito').exclude(encrypted_client_id='').exclude`, `IntegrationCredential.objects.filter(provider='avito').exclude(encrypted_client_id='').exclude(encrypted_client_secret='').exists`, `job.save`, `timedelta`, `timezone.now`.

### `enqueue_profile_sync(profile_id, *, delay_seconds=None)`

Исходник: `integrations/queue.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(pk=profile_id).update`, `AvitoProductProfile.objects.get`, `AvitoSyncJob.objects.update_or_create`, `timedelta`, `timezone.now`.

### `enqueue_profile_sync_after_commit(profile_id, *, delay_seconds=None)`

Исходник: `integrations/queue.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_profile_sync`, `transaction.on_commit`.

### `enqueue_periodic(job_type, *, delay_seconds=0)`

Исходник: `integrations/queue.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.update_or_create`, `timedelta`, `timezone.now`.

## `integrations/reef_api.py`

HTTP-клиент ReefAPI. Секрет и тело ответа не попадают в исключения и журналы.

Импорты: `core.external_policy`, `crypto`, `django.core.exceptions`, `models`.

### `ReefApiError.__init__(self, message, *, code='')`

Исходник: `integrations/reef_api.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `ReefApiClient.__init__(self, key=None, transport=None)`

Исходник: `integrations/reef_api.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReefApiCredential.objects.filter`, `ReefApiCredential.objects.filter(pk=1).first`, `ReefApiError`, `decrypt_secret`, `require_live_operation`.

### `ReefApiClient._post(self, action, payload)`

Исходник: `integrations/reef_api.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReefApiError`, `any`, `code.upper`, `detail.get`, `envelope.get`, `isinstance`, `require_live_operation`, `response.json`, `self._transport`, `str`.

### `ReefApiClient.search(self, query, page, *, price_max=None)`

Исходник: `integrations/reef_api.py:70`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReefApiError`, `data.get`, `int`, `isinstance`, `self._post`.

### `ReefApiClient.listing(self, ad_id)`

Исходник: `integrations/reef_api.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReefApiError`, `data.get`, `isinstance`, `self._post`, `str`.

## `integrations/required_actions.py`

Список необходимых действий со связанными объявлениями без изменения публикаций.

Импорты: `dataclasses`, `django.db.models`, `enum`, `models`, `services`, `urllib.parse`, `warehouse.models`.

### `normalize_remote_status(status)`

Исходник: `integrations/required_actions.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `str(status or '').strip`, `str(status or '').strip().lower`, `{'active': RemotePublicationState.PUBLISHED, 'old': RemotePublicationState.ARCHIVED}.get`.

### `is_remote_published(status)`

Исходник: `integrations/required_actions.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize_remote_status`.

### `is_remote_archived(status)`

Исходник: `integrations/required_actions.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize_remote_status`.

### `_required_action(status, stock, sell_on_avito)`

Исходник: `integrations/required_actions.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `is_remote_archived`, `is_remote_published`.

### `_stock_totals(product_keys)`

Исходник: `integrations/required_actions.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `model.objects.filter`, `model.objects.filter(**{f'{kind}_id__in': ids}).values`, `model.objects.filter(**{f'{kind}_id__in': ids}).values(f'{kind}_id').annotate`, `set`, `totals.update`.

### `get_avito_required_action_counts(*, actions=None, include_keys=False)`

Исходник: `integrations/required_actions.py:61`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.values`, `_required_action`, `_stock_totals`, `action_keys.append`, `actions.append`, `int`, `list`, `sorted`, `totals.get`, `zip`.

### `safe_listing_url(listing)`

Исходник: `integrations/required_actions.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `isinstance`, `ord`, `snapshot.get`, `urlsplit`.

### `RequiredActionRow.label(self)`

Исходник: `integrations/required_actions.py:120`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `get_avito_required_actions()`

Исходник: `integrations/required_actions.py:124`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.select_related`, `RequiredActionRow`, `_required_action`, `_stock_totals`, `actions.append`, `global_stock`, `list`, `row.listing.title.casefold`, `safe_listing_url`, `sorted`.

## `integrations/schema.py`

Определения полей/контрактов профиля Avito, используемые формами и API-преобразованиями.

Импорты: `django.core.exceptions`.

### `schema_fields(schema)`

Исходник: `integrations/schema.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(schema or {}).get`, `fields.get`, `isinstance`.

### `validate_attributes(attributes, schema)`

Исходник: `integrations/schema.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `ValidationError`, `attributes.get`, `definitions.items`, `errors.append`, `field.get`, `isinstance`, `option.get`, `schema_fields`, `set`, `sorted`, `str`, `str(field.get('type') or '').lower`.

## `integrations/services.py`

Оркестрация привязок, профилей и подтверждённой сверки Avito; реальные изменения API требуют разрешённого сценария.

Импорты: `client`, `core.external_policy`, `crypto`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `manual_sync`, `models`, `queue`, `schema`, `warehouse.inventory`.

### `_remote_listing_is_active(status)`

Исходник: `integrations/services.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `str(status or '').strip`, `str(status or '').strip().lower`.

### `_remote_price(value)`

Исходник: `integrations/services.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `str`.

### `_import_remote_price_if_empty(product, remote_price)`

Исходник: `integrations/services.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `product.save`.

### `_delete_profile_photos(profile)`

Исходник: `integrations/services.py:55`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `profile.photos.all`, `profile.photos.all().delete`, `storage.delete`, `transaction.on_commit`.

### `_audit(action, *, actor=None, profile=None, details=None)`

Исходник: `integrations/services.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `IntegrationAuditEvent.objects.create`, `getattr`.

### `get_avito_credential()`

Исходник: `integrations/services.py:72`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `IntegrationCredential.objects.filter`, `IntegrationCredential.objects.filter(provider=IntegrationCredential.Provider.AVITO).first`.

### `save_avito_credentials(*, client_id, client_secret, actor=None)`

Исходник: `integrations/services.py:76`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `IntegrationCredential.objects.get_or_create`, `ValidationError`, `_audit`, `check_avito_connection`, `client_id.strip`, `client_secret.strip`, `credential.save`, `encrypt_secret`, `require_live_operation`.

### `check_avito_connection(*, credential=None, actor=None)`

Исходник: `integrations/services.py:94`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoClient`, `AvitoClient(credential).get_self`, `ValidationError`, `_audit`, `account.get`, `credential.save`, `get_avito_credential`, `str`, `timezone.now`.

### `get_or_create_profile(product, product_kind)`

Исходник: `integrations/services.py:122`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoProductProfile.objects.get_or_create`, `ValidationError`.

### `global_stock(profile, *, stock_totals=None)`

Исходник: `integrations/services.py:130`.

Доступный для Avito физический запас: сумма складов, без реализации и пути.

Статические вызовы: `int`, `product_global_stock`, `stock_totals.get`.

### `validate_profile(profile)`

Исходник: `integrations/services.py:138`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `errors.append`, `field.get`, `isinstance`, `profile.attributes.get`, `profile.product.avito_price.to_integral_value`, `schema_fields`, `str`.

### `refresh_category_schema(profile)`

Исходник: `integrations/services.py:155`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoClient`, `AvitoClient().get_category_fields`, `isinstance`.

### `update_profile(*, profile, data, actor=None, refresh_schema=False)`

Исходник: `integrations/services.py:164`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_audit`, `bool`, `data.get`, `enqueue_profile_sync_after_commit`, `profile.full_clean`, `profile.save`, `refresh_category_schema`, `str`, `str(data.get('category_slug') or '').strip`, `str(data.get('listing_description') or '').strip`, `str(data.get('listing_title') or '').strip`.

### `refresh_remote_listings(*, check_linked_statuses=False)`

Исходник: `integrations/services.py:197`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `AvitoClient`, `AvitoListingConnection.objects.exists`, `AvitoListingConnection.objects.filter`, `AvitoListingConnection.objects.filter(remote_listing=listing).exists`, `AvitoRemoteListing.objects.exclude`, `AvitoRemoteListing.objects.update_or_create`, `Q`, `_remote_price`, `candidates.filter`, `client.get_item_details`, `client.list_items`, `data.get`, `details.get`, `found.items`, `get_avito_credential`, `int`, `isinstance`, `item.get`, `len`, `listing.save`, `missing.exclude`, `missing.filter`, `missing.filter(connection__isnull=False).exists`, `missing.filter(missing_since__isnull=True).update`, `range`, `str`, `str(details.get('status') or '').strip`, `str(details.get('status') or '').strip().lower`, `timezone.now`.

### `_remote_snapshot(listing)`

Исходник: `integrations/services.py:276`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `AvitoClient`, `_remote_price`, `check_avito_connection`, `client.find_item`, `client.get_item_details`, `details.get`, `get_avito_credential`, `item.get`, `str`.

### `bind_listing(*, listing, product, product_kind, actor=None)`

Исходник: `integrations/services.py:316`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.create`, `AvitoListingConnection.objects.filter`, `AvitoListingConnection.objects.filter(profile=profile).exists`, `AvitoListingConnection.objects.filter(remote_listing=listing).exists`, `AvitoProductProfile.objects.select_for_update`, `AvitoProductProfile.objects.select_for_update().get`, `AvitoRemoteListing.objects.select_for_update`, `AvitoRemoteListing.objects.select_for_update().get`, `ValidationError`, `_audit`, `_delete_profile_photos`, `_import_remote_price_if_empty`, `_remote_listing_is_active`, `_remote_snapshot`, `enqueue_profile_sync_after_commit`, `get_or_create_profile`, `listing.save`, `profile.full_clean`, `profile.save`, `snapshot.get`, `transaction.atomic`.

### `import_connection_price_if_empty(*, connection, actor=None)`

Исходник: `integrations/services.py:353`.

Подтягивает цену для ранее созданной связи, не перезаписывая цену CRM.

Статические вызовы: `AvitoListingConnection.objects.select_for_update`, `AvitoListingConnection.objects.select_for_update().select_related`, `AvitoListingConnection.objects.select_for_update().select_related('profile__cd', 'profile__tech', 'remote_listing').get`, `_audit`, `_import_remote_price_if_empty`, `_remote_snapshot`, `connection.profile.product.__class__.objects.select_for_update`, `connection.profile.product.__class__.objects.select_for_update().get`, `connection.remote_listing.save`, `enqueue_profile_sync_after_commit`, `snapshot.get`, `transaction.atomic`.

### `rebind_listing(*, connection, product, product_kind, actor=None)`

Исходник: `integrations/services.py:375`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.filter`, `AvitoListingConnection.objects.filter(profile=target).exists`, `AvitoListingConnection.objects.select_for_update`, `AvitoListingConnection.objects.select_for_update().select_related`, `AvitoListingConnection.objects.select_for_update().select_related('profile', 'remote_listing').get`, `AvitoProductProfile.objects.select_for_update`, `AvitoProductProfile.objects.select_for_update().get`, `ValidationError`, `_audit`, `_delete_profile_photos`, `_import_remote_price_if_empty`, `_remote_listing_is_active`, `_remote_snapshot`, `connection.remote_listing.save`, `connection.save`, `enqueue_profile_sync_after_commit`, `get_or_create_profile`, `old_profile.save`, `snapshot.get`, `target.full_clean`, `target.save`, `transaction.atomic`.

### `unbind_listing(*, connection, actor=None)`

Исходник: `integrations/services.py:430`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.select_for_update`, `AvitoListingConnection.objects.select_for_update().select_related`, `AvitoListingConnection.objects.select_for_update().select_related('remote_listing').get`, `AvitoProductProfile.objects.select_for_update`, `AvitoProductProfile.objects.select_for_update().get`, `_audit`, `connection.delete`, `profile.save`.

### `desired_state(profile)`

Исходник: `integrations/services.py:445`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `global_stock`, `hashlib.sha256`, `hashlib.sha256(encoded).hexdigest`, `json.dumps`, `json.dumps(state, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode`, `list`, `profile.photos.order_by`, `profile.photos.order_by('sort_order', 'id').values_list`, `str`.

### `sync_profile(profile_id, *, retry_number=0, force_remote_check=False)`

Исходник: `integrations/services.py:462`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `AvitoAPIError`, `AvitoClient`, `AvitoClient().update_stock`, `AvitoListingConnection.objects.select_related`, `AvitoListingConnection.objects.select_related('remote_listing').filter`, `AvitoListingConnection.objects.select_related('remote_listing').filter(profile=profile).first`, `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(pk=profile.pk).update`, `AvitoProductProfile.objects.select_related`, `AvitoProductProfile.objects.select_related('cd', 'tech').get`, `AvitoSyncLog.objects.create`, `Decimal`, `any`, `client.update_price`, `client.update_stock`, `connection.remote_listing.status.lower`, `desired_state`, `errors.append`, `global_stock`, `isinstance`, `price_result.get`, `result_payload.get`, `row.get`, `stock_result.get`, `stock_rows.get`, `str`, `timezone.now`, `validate_profile`.

### `reconcile_all(*, job=None)`

Исходник: `integrations/services.py:582`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `reconcile_active_listings`.

## `integrations/signals.py`

Реакции на сохранение моделей и запуск связанных действий Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `catalog.models`, `django.core.exceptions`, `django.db.models.signals`, `django.dispatch`, `queue`, `warehouse.models`.

### `_enqueue_for_product(product)`

Исходник: `integrations/signals.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_profile_sync_after_commit`.

### `product_changed(sender, instance, update_fields=None, **kwargs)`

Исходник: `integrations/signals.py:34`.

Декораторы: `receiver(post_save, sender=CD, dispatch_uid='avito_sync_cd')`; `receiver(post_save, sender=Tech, dispatch_uid='avito_sync_tech')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_enqueue_for_product`, `receiver`, `set`, `set(update_fields).issubset`.

### `cd_stock_changed(sender, instance, **kwargs)`

Исходник: `integrations/signals.py:42`.

Декораторы: `receiver(post_save, sender=CDWarehouseStock, dispatch_uid='avito_sync_cd_stock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_enqueue_for_product`, `receiver`.

### `tech_stock_changed(sender, instance, **kwargs)`

Исходник: `integrations/signals.py:47`.

Декораторы: `receiver(post_save, sender=TechWarehouseStock, dispatch_uid='avito_sync_tech_stock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_enqueue_for_product`, `receiver`.

## `integrations/tasks.py`

Исполнение очереди интеграций отдельным worker с фазами, ошибками и повторными попытками.

Импорты: `client`, `datetime`, `django.db`, `django.utils`, `manual_sync`, `models`, `queue`, `services`.

### `_reschedule_after_database_lock(job)`

Исходник: `integrations/tasks.py:21`.

Вернуть задание в очередь после временного конфликта записей SQLite.

Статические вызовы: `job.save`, `logger.exception`, `range`, `str`, `str(save_exc).lower`, `time.sleep`, `timedelta`, `timezone.now`.

### `ensure_periodic_jobs()`

Исходник: `integrations/tasks.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.filter`, `AvitoSyncJob.objects.filter(status=AvitoSyncJob.Status.RUNNING, updated_at__lt=now - timedelta(minutes=15)).update`, `AvitoSyncJob.objects.get_or_create`, `ensure_required_actions_refresh`, `timedelta`, `timezone.now`.

### `claim_next_job()`

Исходник: `integrations/tasks.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.select_for_update`, `AvitoSyncJob.objects.select_for_update().filter`, `due_jobs.filter`, `due_jobs.filter(job_type__in=INTERACTIVE_JOBS).order_by`, `due_jobs.filter(job_type__in=INTERACTIVE_JOBS).order_by('run_after', 'id').first`, `due_jobs.order_by`, `due_jobs.order_by('run_after', 'id').first`, `job.save`, `timezone.now`, `transaction.atomic`.

### `process_one_job()`

Исходник: `integrations/tasks.py:80`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_reschedule_after_database_lock`, `claim_next_job`, `ensure_periodic_jobs`, `job.refresh_from_db`, `job.save`, `len`, `logger.exception`, `logger.warning`, `min`, `reconcile_active_listings`, `reconcile_all`, `refresh_remote_listings`, `str`, `str(exc).lower`, `sync_profile`, `timedelta`, `timezone.now`.

## `integrations/urls.py`

Именованные HTTP-маршруты приложения Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `core.update_views`, `django.urls`.

## `integrations/verification.py`

Сверка локальных целей с реальным Avito. Диагностика выполняет сеть, режим исправления может менять объявления.

Импорты: `client`, `dataclasses`, `decimal`, `django.utils`, `models`, `services`.

### `_chunks(values, size=10)`

Исходник: `integrations/verification.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `range`.

### `fetch_remote_stocks(item_ids, *, client=None, progress=None, tolerate_errors=False, on_error=None, batch_retries=0)`

Исходник: `integrations/verification.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoAPIError`, `AvitoClient`, `_chunks`, `client.get_stocks`, `int`, `isinstance`, `len`, `list`, `on_error`, `payload.get`, `progress`, `range`, `time.sleep`.

### `_fresh_remote_prices(connections)`

Исходник: `integrations/verification.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `connection.remote_listing.refresh_from_db`, `refresh_remote_listings`, `timezone.now`.

### `_status(expected, remote)`

Исходник: `integrations/verification.py:106`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_final_status(initial_status, expected, remote, *, fix_requested)`

Исходник: `integrations/verification.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `verify_avito_connections(*, fix=False, client=None)`

Исходник: `integrations/verification.py:124`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoClient`, `AvitoListingConnection.objects.select_related`, `AvitoListingConnection.objects.select_related('profile__cd', 'profile__tech', 'remote_listing').order_by`, `AvitoVerificationRow`, `_final_status`, `_fresh_remote_prices`, `_status`, `fetch_remote_stocks`, `final_prices.get`, `final_stocks.get`, `global_stock`, `initial_prices.get`, `initial_stocks.get`, `list`, `profiles_to_fix.append`, `rows.append`, `state.append`, `str`, `sync_profile`.

### `verification_summary(rows)`

Исходник: `integrations/verification.py:217`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `sum`.

## `integrations/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю Avito, ReefAPI и Google Sheets.

Внешние вызовы могут менять реальные данные; тесты подменяют API, обмен выполняет worker.

Импорты: `catalog.models`, `client`, `core.decorators`, `django.conf`, `django.contrib`, `django.core.exceptions`, `django.core.paginator`, `django.db`, `django.db.models`, `django.db.utils`, `django.http`, `django.shortcuts`, `django.urls`, `django.utils`, `django.views.decorators.cache`, `django.views.decorators.debug`, `django.views.decorators.http`, `forms`, `google_sheets`, `google_tasks`, `models`, `queue`, `reef_api`, `reef_settings`, `required_actions`, `services`, `uuid`.

### `_error_text(exc)`

Исходник: `integrations/views.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `isinstance`, `str`.

### `api_keys(request)`

Исходник: `integrations/views.py:66`.

Декораторы: `permission_required_any('integrations.view_integrations')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CredentialForm`, `GoogleSheetsSyncJob.objects.order_by`, `GoogleSheetsSyncJob.objects.order_by('-created_at', '-pk').first`, `ReefApiCredential.objects.filter`, `ReefApiCredential.objects.filter(pk=1).first`, `bool`, `get_avito_credential`, `get_google_sheets_integration`, `permission_required_any`, `render`.

### `reef_key_save(request)`

Исходник: `integrations/views.py:83`.

Декораторы: `require_POST`; `sensitive_post_parameters('api_key')`; `permission_required_any('integrations.manage_integration_credentials')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `save_reef_key`, `sensitive_post_parameters`.

### `reef_connection_check(request)`

Исходник: `integrations/views.py:95`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `check_reef_connection`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `str`.

### `google_sheets_settings_save(request)`

Исходник: `integrations/views.py:107`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `save_google_sheets_settings`.

### `google_sheets_sync(request)`

Исходник: `integrations/views.py:123`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_google_sheets_sync')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_google_sheets_sync`, `get_google_sheets_integration`, `logger.info`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `credentials_save(request)`

Исходник: `integrations/views.py:141`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CredentialForm`, `_error_text`, `form.is_valid`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `save_avito_credentials`.

### `credentials_check(request)`

Исходник: `integrations/views.py:157`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_error_text`, `check_avito_connection`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `avito_dashboard(request)`

Исходник: `integrations/views.py:168`.

Декораторы: `permission_required_any('integrations.view_avito_integration')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.count`, `AvitoProductProfile.objects.filter`, `AvitoProductProfile.objects.filter(Q(cd__is_archived=False) | Q(tech__is_archived=False), sync_status=AvitoProductProfile.SyncStatus.ERROR).count`, `AvitoRemoteListing.objects.filter`, `AvitoRemoteListing.objects.filter(connection__isnull=True).exclude`, `AvitoRemoteListing.objects.filter(connection__isnull=True).exclude(status__iexact='removed').count`, `AvitoSyncJob.objects.filter`, `AvitoSyncJob.objects.filter(job_type=AvitoSyncJob.JobType.STATUS_REFRESH).first`, `AvitoSyncJob.objects.filter(status=AvitoSyncJob.Status.PENDING).count`, `AvitoSyncLog.objects.filter`, `AvitoSyncLog.objects.filter(result=AvitoSyncLog.Result.SUCCESS).first`, `Q`, `get_avito_credential`, `get_avito_required_action_counts`, `get_avito_required_actions`, `int`, `manual_jobs.filter`, `manual_jobs.filter(pk=int(requested_run)).first`, `manual_jobs.filter(status__in=(AvitoSyncJob.Status.PENDING, AvitoSyncJob.Status.RUNNING)).order_by`, `manual_jobs.filter(status__in=(AvitoSyncJob.Status.PENDING, AvitoSyncJob.Status.RUNNING)).order_by('-created_at', '-pk').first`, `manual_jobs.order_by`, `manual_jobs.order_by('-created_at', '-pk').first`, `permission_required_any`, `render`, `request.GET.get`, `requested_run.isdigit`.

### `required_actions_count(request)`

Исходник: `integrations/views.py:201`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('integrations.view_avito_integration')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `get_avito_required_action_counts`, `permission_required_any`, `request.GET.get`, `timezone.now`, `timezone.now().isoformat`.

### `required_actions_refresh(request)`

Исходник: `integrations/views.py:213`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.select_for_update`, `AvitoSyncJob.objects.select_for_update().get_or_create`, `get_avito_credential`, `job.save`, `messages.error`, `permission_required_any`, `redirect`, `reverse`, `timezone.now`, `transaction.atomic`.

### `required_actions_status(request, pk)`

Исходник: `integrations/views.py:237`.

Декораторы: `require_GET`; `permission_required_any('integrations.view_avito_integration')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `get_object_or_404`, `permission_required_any`, `timezone.localtime`, `timezone.localtime(job.run_after).strftime`.

### `manual_sync(request)`

Исходник: `integrations/views.py:250`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.create`, `AvitoSyncJob.objects.filter`, `AvitoSyncJob.objects.filter(job_type=AvitoSyncJob.JobType.MANUAL, status__in=(AvitoSyncJob.Status.PENDING, AvitoSyncJob.Status.RUNNING)).order_by`, `AvitoSyncJob.objects.filter(job_type=AvitoSyncJob.JobType.MANUAL, status__in=(AvitoSyncJob.Status.PENDING, AvitoSyncJob.Status.RUNNING)).order_by('-created_at', '-pk').first`, `get_avito_credential`, `messages.error`, `permission_required_any`, `redirect`, `reverse`, `timezone.now`, `uuid4`.

### `manual_sync_status(request, pk)`

Исходник: `integrations/views.py:271`.

Декораторы: `require_GET`; `permission_required_any('integrations.view_avito_integration')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `get_object_or_404`, `job.get_status_display`, `permission_required_any`, `timezone.localtime`, `timezone.localtime(job.run_after).strftime`.

### `connections(request)`

Исходник: `integrations/views.py:292`.

Декораторы: `permission_required_any('integrations.view_avito_integration')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.select_related`, `AvitoRemoteListing.objects.filter`, `AvitoRemoteListing.objects.filter(connection__isnull=True).exclude`, `Paginator`, `Paginator(linked, 25).get_page`, `Paginator(unlinked, 25).get_page`, `Q`, `int`, `linked.filter`, `permission_required_any`, `query.isdigit`, `render`, `request.GET.get`, `str`, `str(request.GET.get('q') or '').strip`, `unlinked.filter`.

### `listings_refresh(request)`

Исходник: `integrations/views.py:319`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_periodic`, `messages.success`, `permission_required_any`, `redirect`.

### `listing_bind(request, pk)`

Исходник: `integrations/views.py:326`.

Декораторы: `permission_required_any('integrations.bind_avito_listing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductTargetForm`, `_error_text`, `bind_listing`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `messages.success`, `permission_required_any`, `redirect`, `render`, `request.GET.get`.

### `listing_rebind(request, pk)`

Исходник: `integrations/views.py:344`.

Декораторы: `permission_required_any('integrations.rebind_avito_listing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.select_related`, `ProductTargetForm`, `_error_text`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `messages.success`, `permission_required_any`, `rebind_listing`, `redirect`, `render`, `request.GET.get`.

### `listing_unbind(request, pk)`

Исходник: `integrations/views.py:364`.

Декораторы: `permission_required_any('integrations.rebind_avito_listing')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `messages.success`, `permission_required_any`, `redirect`, `unbind_listing`.

### `product_avito_context(product, product_kind, user)`

Исходник: `integrations/views.py:371`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoPhotoForm`, `AvitoProfileForm`, `get_or_create_profile`, `global_stock`, `user.has_perm`.

### `_product_and_profile(product_kind, pk)`

Исходник: `integrations/views.py:387`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `get_object_or_404`, `get_or_create_profile`, `model.objects.active`.

### `product_profile_save(request, product_kind, pk)`

Исходник: `integrations/views.py:397`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `AvitoProfileForm`, `_error_text`, `_product_and_profile`, `form.errors.values`, `form.is_valid`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `sum`, `update_profile`.

### `product_photo_add(request, product_kind, pk)`

Исходник: `integrations/views.py:414`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `AvitoPhotoForm`, `_product_and_profile`, `enqueue_profile_sync_after_commit`, `form.errors.values`, `form.is_valid`, `form.save`, `messages.error`, `messages.success`, `permission_required_any`, `photo.save`, `profile.photos.order_by`, `profile.photos.order_by('-sort_order').values_list`, `profile.photos.order_by('-sort_order').values_list('sort_order', flat=True).first`, `redirect`, `sum`, `transaction.atomic`.

### `product_photo_delete(request, product_kind, pk, photo_id)`

Исходник: `integrations/views.py:432`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_product_and_profile`, `enqueue_profile_sync_after_commit`, `get_object_or_404`, `messages.success`, `permission_required_any`, `photo.delete`, `redirect`, `storage.delete`, `transaction.atomic`, `transaction.on_commit`.

### `product_photo_move(request, product_kind, pk, photo_id)`

Исходник: `integrations/views.py:446`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoProductPhoto.objects.filter`, `AvitoProductPhoto.objects.filter(pk=item.pk).update`, `AvitoProductPhoto.objects.filter(profile=profile).update`, `F`, `_product_and_profile`, `enqueue_profile_sync_after_commit`, `enumerate`, `get_object_or_404`, `len`, `list`, `ordered.index`, `permission_required_any`, `profile.photos.order_by`, `redirect`, `request.POST.get`, `transaction.atomic`.

## `integrations/worker_heartbeat.py`

Независимое подтверждение живого worker с отдельным Django-соединением.

Импорты: `contextlib`, `django.db`, `django.utils`, `worker_models`, `worker_processes`, `worker_runtime`.

### `Heartbeat.__init__(self, services, instance, birth)`

Исходник: `integrations/worker_heartbeat.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `list`, `threading.Event`, `threading.current_thread`.

### `Heartbeat.write(self)`

Исходник: `integrations/worker_heartbeat.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WorkerProcess.objects.update_or_create`, `close_old_connections`, `connections.close_all`, `logger.warning`, `os.getpid`, `timezone.now`.

### `Heartbeat.run(self)`

Исходник: `integrations/worker_heartbeat.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.main.is_alive`, `self.stop.wait`, `self.write`.

### `monitored_worker(services, instance=None, adapter=None)`

Исходник: `integrations/worker_heartbeat.py:43`.

Декораторы: `contextmanager`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AlreadyRunning`, `ExitStack`, `Heartbeat`, `OSError`, `adapter.inventory`, `any`, `heartbeat.run`, `heartbeat.stop.set`, `heartbeat.write`, `next`, `os.getpid`, `os.getppid`, `process_adapter`, `process_lock`, `set`, `sorted`, `stack.enter_context`, `str`, `thread.join`, `thread.start`, `threading.Thread`, `uuid.UUID`, `uuid.uuid4`.

## `integrations/worker_models.py`

Технические состояния процессов; не связаны с товарным и денежным учётом.

Импорты: `django.conf`, `django.db`, `django.db.models`.

## `integrations/worker_monitoring.py`

Контроллер и читаемое представление: запуск только через фиксированный OS-адаптер.

Импорты: `core.db_retry`, `datetime`, `django.conf`, `django.core.exceptions`, `django.db`, `django.utils`, `sales.print_agents`, `worker_models`, `worker_policy`, `worker_runtime`, `worker_schedule`.

### `event(service, kind, result='', command=None)`

Исходник: `integrations/worker_monitoring.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WorkerEvent.objects.create`, `logger.info`.

### `_finish(command, state, result, now)`

Исходник: `integrations/worker_monitoring.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `command.save`.

### `request_recovery(actor, services, request_id)`

Исходник: `integrations/worker_monitoring.py:44`.

Декораторы: `retry_database_lock`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `WorkerCommand.objects.create`, `WorkerCommand.objects.filter`, `WorkerCommand.objects.filter(request_id=request_id, service=code).first`, `WorkerCommand.objects.filter(service=code, state__in=['queued', 'running']).first`, `WorkerController.objects.filter`, `WorkerController.objects.filter(pk=1).first`, `WorkerService.objects.get_or_create`, `_fresh`, `any`, `command_ids.append`, `dict.fromkeys`, `event`, `expected_services`, `str`, `timezone.now`, `transaction.atomic`, `uuid.UUID`.

### `_failed(service, command, reason, now)`

Исходник: `integrations/worker_monitoring.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_finish`, `event`, `min`, `timedelta`.

### `_fresh(at, now)`

Исходник: `integrations/worker_monitoring.py:85`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `timedelta`.

### `supervise_once(adapter, *, now=None, instance=None)`

Исходник: `integrations/worker_monitoring.py:89`.

Один цикл. Вызывающий держит межпроцессную блокировку supervisor весь срок жизни.

Статические вызовы: `WorkerCommand.objects.filter`, `WorkerCommand.objects.filter(service=code, state__in=['queued', 'running']).first`, `WorkerController.objects.get_or_create`, `WorkerEvent.objects.create`, `WorkerProcess.objects.filter`, `WorkerService.objects.get_or_create`, `_failed`, `_finish`, `_fresh`, `adapter.inventory`, `adapter.launch`, `any`, `bool`, `command.save`, `controller.save`, `dict.fromkeys`, `event`, `expected_services`, `list`, `next`, `policy.get`, `service.save`, `str`, `timedelta`, `timezone.now`, `transaction.atomic`, `uuid.uuid4`.

### `monitoring_snapshot(*, now=None, with_history=False)`

Исходник: `integrations/worker_monitoring.py:211`.

GET только читает локальные таблицы; не планирует работу и не проверяет API.

Статические вызовы: `ERROR_LABELS.get`, `WorkerController.objects.filter`, `WorkerController.objects.filter(pk=1).first`, `WorkerService.objects.all`, `_fresh`, `agent_snapshot`, `any`, `bool`, `data['incidents'].append`, `dict.fromkeys`, `expected_services`, `getattr`, `history_snapshot`, `incidents.append`, `known.get`, `len`, `policy.get`, `queue_snapshot`, `services.append`, `str`, `sum`, `timezone.now`.

### `history_snapshot()`

Исходник: `integrations/worker_monitoring.py:267`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ERROR_LABELS.get`, `RESULT_LABELS.get`, `STATUS_LABELS.get`, `WorkerEvent.objects.select_related`, `WorkerEvent.objects.select_related('actor').all`, `dict`, `kinds.get`, `names.get`.

## `integrations/worker_policy.py`

Только чтение конфигурации. Ошибка внешнего API не выключает ожидаемый worker.

Импорты: `django.conf`, `django.core.exceptions`, `models`, `pathlib`, `sales.label_printing`, `sales.models`, `telegram_bots.configuration`, `worker_runtime`, `yandex_market.models`.

### `expected_services()`

Исходник: `integrations/worker_policy.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `GoogleSheetsIntegration.objects.first`, `Integration.objects.all`, `IntegrationCredential.objects.filter`, `IntegrationCredential.objects.filter(provider='avito').first`, `Path`, `Path(settings.GOOGLE_SERVICE_ACCOUNT_FILE).is_file`, `Path(settings.YANDEX_MARKET_KEY_FILE).is_file`, `PrintAgent.objects.filter`, `PrintAgent.objects.filter(enabled=True).exists`, `dict.fromkeys`, `expected_status`, `getattr`, `printer_configuration`, `yandex.exists`, `yandex.filter`, `yandex.filter(enabled=True).exists`.

## `integrations/worker_processes.py`

Адаптер локальных процессов. Ни view, ни модель не вызывают команды ОС.

Импорты: `core.external_policy`, `django.conf`, `linux_processes`, `pathlib`, `worker_runtime`.

### `process_adapter()`

Исходник: `integrations/worker_processes.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `LinuxProcesses`, `WindowsProcesses`.

### `WindowsProcesses.inventory(self)`

Исходник: `integrations/worker_processes.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OSError`, `any`, `isinstance`, `json.loads`, `require_live_operation`, `row.get`, `str`, `subprocess.run`.

### `WindowsProcesses.launch(self, service, instance)`

Исходник: `integrations/worker_processes.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(folder / f'{instance}.stderr.log').open`, `(folder / f'{instance}.stdout.log').open`, `Path`, `ValueError`, `folder.mkdir`, `require_live_operation`, `str`, `subprocess.Popen`.

## `integrations/worker_runtime.py`

Блокировки Windows/Linux и параметры локального контроля. Файлы блокировок не удаляются.

Импорты: `contextlib`, `django.conf`, `pathlib`.

### `graceful_shutdown()`

Исходник: `integrations/worker_runtime.py:25`.

Декораторы: `contextmanager`.

SIGTERM прекращает получение новых задач, но не обрывает текущий внешний вызов.

Статические вызовы: `handlers.items`, `signal.signal`, `stop.set`, `threading.Event`, `threading.current_thread`, `threading.main_thread`.

### `process_lock(name)`

Исходник: `integrations/worker_runtime.py:40`.

Декораторы: `contextmanager`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(folder / f'{name}.lock').open`, `AlreadyRunning`, `Path`, `ValueError`, `fcntl.flock`, `folder.mkdir`, `getattr`, `msvcrt.locking`, `stream.fileno`, `stream.flush`, `stream.seek`, `stream.tell`, `stream.write`.

## `integrations/worker_schedule.py`

Безопасные сведения о фактически назначенных заданиях; никаких ensure/enqueue.

Импорты: `django.db.models`, `models`, `sales.models`, `telegram_bots.monitoring`, `yandex_market.models`.

### `_nearest(query, state, now)`

Исходник: `integrations/worker_schedule.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `pending.filter`, `pending.filter(run_after__lte=now).order_by`, `pending.filter(run_after__lte=now).order_by('priority', 'run_after', 'pk').first`, `pending.order_by`, `pending.order_by('run_after', 'priority', 'pk').first`, `query.filter`.

### `queue_snapshot(code, *, now, enabled=True)`

Исходник: `integrations/worker_schedule.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoSyncJob.objects.all`, `AvitoSyncJob.objects.filter`, `AvitoSyncJob.objects.filter(status='done').aggregate`, `Case`, `GoogleSheetsIntegration.objects.aggregate`, `GoogleSheetsSyncJob.objects.all`, `IntegerField`, `MarketPrintJob.objects.all`, `Max`, `SyncJob.objects.all`, `Value`, `When`, `YANDEX_NAMES.get`, `_nearest`, `data.update`, `getattr`, `job.get_job_type_display`, `jobs.aggregate`, `jobs.annotate`, `jobs.exclude`, `jobs.exclude(state__in=['done', 'error', 'uncertain']).order_by`, `jobs.exclude(state__in=['done', 'error', 'uncertain']).order_by('pk').first`, `jobs.filter`, `jobs.filter(**{state: 'error'}).exists`, `jobs.filter(**{state: 'pending'}).exclude`, `jobs.filter(**{state: 'pending'}).exclude(last_error='').exists`, `jobs.filter(**{state: 'running'}).order_by`, `jobs.filter(**{state: 'running'}).order_by('updated_at', 'pk').first`, `jobs.filter(state='done').aggregate`, `jobs.filter(state__in=['error', 'uncertain']).exists`, `names.get`, `telegram_snapshot`, `title`.

## `integrations/worker_views.py`

Чтение состояния для сотрудников, очередь команд только для superuser.

Импорты: `django.contrib.auth.decorators`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.http`, `sales.models`, `worker_models`, `worker_monitoring`, `worker_runtime`.

### `_active(request)`

Исходник: `integrations/worker_views.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `workers(request)`

Исходник: `integrations/worker_views.py:23`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(state='uncertain').select_related`, `_active`, `monitoring_snapshot`, `render`, `request.user.has_perm`.

### `worker_status(request)`

Исходник: `integrations/worker_views.py:38`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ERROR_LABELS.get`, `JsonResponse`, `RESULT_LABELS.get`, `WorkerCommand.objects.order_by`, `_active`, `history_snapshot`, `monitoring_snapshot`.

### `worker_start(request, service=None)`

Исходник: `integrations/worker_views.py:54`.

Декораторы: `login_required`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `WorkerCommand.objects.filter`, `_active`, `all`, `any`, `list`, `request.POST.get`, `request_recovery`.

### `worker_command(request, pk)`

Исходник: `integrations/worker_views.py:74`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ERROR_LABELS.get`, `JsonResponse`, `RESULT_LABELS.get`, `_active`, `get_object_or_404`, `str`.

## `orders/admin.py`

Регистрация моделей и разрешённых действий в Django Admin импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `django.contrib`, `models`.

### `_can_view_supplier_snapshots(request)`

Исходник: `orders/admin.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`.

### `SupplierSnapshotAdminMixin.has_module_permission(self, request)`

Исходник: `orders/admin.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_module_permission`.

### `SupplierSnapshotAdminMixin.has_view_permission(self, request, obj=None)`

Исходник: `orders/admin.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_view_permission`.

### `SupplierSnapshotAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `orders/admin.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_change_permission`.

### `ReadonlyHistoryAdmin.has_add_permission(self, request)`

Исходник: `orders/admin.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ReadonlyHistoryAdmin.has_change_permission(self, request, obj=None)`

Исходник: `orders/admin.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`.

### `ReadonlyHistoryAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `orders/admin.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `OrderItemInline.has_add_permission(self, request, obj=None)`

Исходник: `orders/admin.py:54`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderAdmin.get_queryset(self, request)`

Исходник: `orders/admin.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `queryset.filter`, `request.user.has_perm`, `super`, `super().get_queryset`.

### `CustomerProcurementOrderAdmin.get_inline_instances(self, request, obj=None)`

Исходник: `orders/admin.py:75`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().get_inline_instances`.

### `AdjustmentChangeInline.has_add_permission(self, request, obj=None)`

Исходник: `orders/admin.py:103`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `BatchLineInline.has_add_permission(self, request, obj=None)`

Исходник: `orders/admin.py:126`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `orders/apps.py`

Конфигурация приложения и его регистрация в Django импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `django.apps`.

### `OrdersConfig.ready(self)`

Исходник: `orders/apps.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `orders/arrival.py`

Единый расчёт фактической доставки; изменения сериализуются на уровне рейса.

Импорты: `arrival_documents`, `arrival_math`, `arrival_models`, `core.allocation`, `core.db_retry`, `decimal`, `django`, `django.core.exceptions`, `django.db`, `django.utils`, `fulfillment`, `models`, `trips`.

### `require_arrival_permissions(actor, *, finalization=False)`

Исходник: `orders/arrival.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `actor.has_perm`, `all`, `required.append`.

### `_parameters(values)`

Исходник: `orders/arrival.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ArrivalForm`, `ValidationError`, `form.errors.values`, `form.is_valid`, `str`.

### `assert_document_finalized(document)`

Исходник: `orders/arrival.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `document_waits_finalization`.

### `document_waits_finalization(document)`

Исходник: `orders/arrival.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip__trip_orders=operation.order, arrived_at__isnull=False, finalized_at__isnull=True).exists`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(**{key: document}, active=True).first`, `bool`.

### `lock_document_trip(kind, document_id)`

Исходник: `orders/arrival.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(**{kind + '_id': document_id}, active=True).first`, `lock_arrival`, `operation.calculation.get`.

### `_revision(actual, expected)`

Исходник: `orders/arrival.py:57`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`.

### `lock_arrival(arrival_id, expected_revision=None, *, finalized_allowed=False)`

Исходник: `orders/arrival.py:66`.

Сериализует изменения сначала блокировкой рейса, затем прибытия. Проверяет revision, факт прибытия и запрет правки финализированных затрат.

Статические вызовы: `SupplierOrderBatch.objects.select_for_update`, `SupplierOrderBatch.objects.select_for_update().get`, `TripArrival.objects.select_for_update`, `TripArrival.objects.select_for_update().get`, `TripArrival.objects.values_list`, `TripArrival.objects.values_list('trip_id', flat=True).get`, `ValidationError`, `_revision`.

### `arrival_preview(*, actor, batch_id, **parameters)`

Исходник: `orders/arrival.py:80`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `SupplierOrderBatch.objects.get`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(order__trip=trip, active=True).exists`, `ValidationError`, `_assert_balances`, `_parameters`, `allocate_amount`, `calculation`, `forms.DecimalField`, `forms.DecimalField(min_value=0, max_digits=20, decimal_places=2).clean`, `order.items.select_related`, `purchase_cost`, `require_arrival_permissions`, `rows.append`, `sum`, `trip.trip_orders.filter`, `trip.trip_orders.filter(status='completed').exists`, `trip.trip_orders.filter(supply__isnull=False).exists`, `trip.trip_orders.order_by`, `zip`.

### `confirm_arrival(*, actor, batch_id, expected_revision, **parameters)`

Исходник: `orders/arrival.py:116`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Фиксирует единые USDT-курсы, D и первоначальные источники рейса. После первой операции основания прибытия нельзя незаметно заменить.

Статические вызовы: `SupplierOrderBatch.objects.select_for_update`, `SupplierOrderBatch.objects.select_for_update().get`, `TripArrival.objects.create`, `TripArrival.objects.select_for_update`, `TripArrival.objects.select_for_update().filter`, `TripArrival.objects.select_for_update().filter(trip=trip).first`, `TripCostRow.objects.create`, `ValidationError`, `_record_trip_change`, `_revision`, `arrival.rows.all`, `arrival_preview`, `existing.rows.all`, `existing.rows.all().delete`, `existing.save`, `setattr`, `str`, `timezone.now`, `values.items`, `values.update`.

### `unconfirm_arrival(*, actor, arrival_id, expected_revision)`

Исходник: `orders/arrival.py:154`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(order__trip_id=arrival.trip_id, calculation__arrival_id=arrival.pk).exists`, `ValidationError`, `_record_trip_change`, `arrival.save`, `lock_arrival`, `require_arrival_permissions`.

### `recalculate_arrival(arrival, *, actor=None)`

Исходник: `orders/arrival.py:166`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(order__trip_id=arrival.trip_id, active=True).exists`, `ValidationError`, `allocate_amount`, `arrival.rows.select_for_update`, `arrival.rows.select_for_update().order_by`, `arrival.save`, `list`, `refresh_documents`, `row.save`, `sum`, `zip`.

### `reduce_received(*, actor, arrival_id, order_id, quantities, expected_revision)`

Исходник: `orders/arrival.py:187`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Уменьшает фактический состав с проверкой ревизии и общим перераспределением D. Исходный заказ остаётся в истории.

Статические вызовы: `ValidationError`, `_record_trip_change`, `arrival.rows.select_for_update`, `arrival.rows.select_for_update().filter`, `arrival.trip.trip_orders.filter`, `arrival.trip.trip_orders.filter(pk=order_id).first`, `changes.append`, `int`, `list`, `lock_arrival`, `quantities.items`, `recalculate_arrival`, `require_permissions`, `row.save`, `set`, `sorted`.

## `orders/arrival_documents.py`

Документы фактического состава рейса; складские дополнения учитываются отдельно.

Импорты: `arrival`, `arrival_math`, `arrival_models`, `catalog.game_codes`, `catalog.models`, `core.db_retry`, `decimal`, `django`, `django.core.exceptions`, `django.db`, `fulfillment`, `models`, `operation_changes`, `price.services`, `sales.models`, `sales.services`, `supplies.models`, `supplies.services`, `trips`, `uuid`, `warehouse.valuation`.

### `cohort_rows(arrival, order_id)`

Исходник: `orders/arrival_documents.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `arrival.rows.filter`, `arrival.rows.filter(order_id=order_id).select_related`, `enumerate`, `rows.append`, `str`, `unit_cohorts`.

### `form_rows(arrival, order_id)`

Исходник: `orders/arrival_documents.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(row.final_total / row.actual_quantity).quantize`, `Decimal`, `arrival.rows.filter`, `arrival.rows.filter(order_id=order_id).select_related`, `getattr`, `str`.

### `operation_snapshot(arrival, order, rows)`

Исходник: `orders/arrival_documents.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `decimal_value`, `str`.

### `build_draft(*, actor, order)`

Исходник: `orders/arrival_documents.py:51`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip_id=order.trip_id, arrived_at__isnull=False).first`, `ValidationError`, `form_rows`, `operation_snapshot`, `prepaid_amount`, `require_permissions`, `snapshot.update`, `str`, `uuid4`.

### `_prior(actor, order_id, draft_key, kind)`

Исходник: `orders/arrival_documents.py:63`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(draft_key=draft_key).first`, `ValidationError`, `getattr`, `require_permissions`.

### `_order(actor, arrival, order_id, stock)`

Исходник: `orders/arrival_documents.py:74`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `arrival.trip.trip_orders.filter`, `arrival.trip.trip_orders.filter(pk=order_id).first`, `order.operations.filter`, `order.operations.filter(active=True).exists`, `require_permissions`.

### `_prepare(actor, arrival, order, lines, *, stock=False)`

Исходник: `orders/arrival_documents.py:86`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `arrival.rows.select_for_update`, `arrival.rows.select_for_update().filter`, `changes.append`, `cohort_rows`, `configs.items`, `extras.append`, `form_rows`, `forms.DecimalField`, `forms.DecimalField(max_digits=20, decimal_places=2).clean`, `getattr`, `int`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().filter`, `model.objects.active().select_for_update().filter(pk=product_id).first`, `raw.get`, `reduce_received`, `source.save`, `sources.get`, `sources.items`, `str`, `str(raw.get('line_note') or '').strip`, `{'cd': CD, 'tech': Tech}.get`.

### `_confirm(actor, arrival, order, rows, changes, key, confirmation, details)`

Исходник: `orders/arrival_documents.py:140`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `confirm_changes`, `form_rows`, `str`.

### `create_arrival_sale(*, actor, arrival_id, order_id, expected_revision, warehouse_id, lines=None, draft_key=None, payment_method='cash_postpay', note='', changes_confirmation='')`

Исходник: `orders/arrival_documents.py:149`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Создаёт связанную незавершённую продажу с подтверждением отклонений и идемпотентностью. Рейсовые direct-delivery и добавленные складские строки различаются.

Статические вызовы: `ValidationError`, `_confirm`, `_create_sale`, `_link`, `_order`, `_prepare`, `_prior`, `lock_arrival`, `operation_snapshot`, `prepaid_amount`, `str`, `uuid4`.

### `create_arrival_supply(*, actor, arrival_id, order_id, expected_revision, warehouse_id, lines=None, draft_key=None, changes_confirmation='')`

Исходник: `orders/arrival_documents.py:180`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Создаёт ожидающий рейсовый приход из складского назначения. До общей финализации/проверки цен физического поступления нет.

Статические вызовы: `_confirm`, `_link`, `_order`, `_prepare`, `_prior`, `accept_supply`, `arrival.rows.filter`, `getattr`, `getattr(supply, kind + '_items').order_by`, `item.save`, `lock_arrival`, `operation_snapshot`, `str`, `supply.save`, `uuid4`, `validate_supply_game_codes`, `zip`.

### `refresh_supply_calculations(supply, *, rebase=False)`

Исходник: `orders/arrival_documents.py:210`.

Переиспользует штатный средневзвешенный расчёт без движения товара.

Статические вызовы: `(CD if kind == 'cd' else Tech).objects.select_for_update`, `(CD if kind == 'cd' else Tech).objects.select_for_update().get`, `SupplyCostCalculation.objects.create`, `_calculation_values`, `current.delete`, `current.save`, `existing.get`, `existing.items`, `getattr`, `getattr(supply, kind + '_items').select_related`, `list`, `set`, `setattr`, `sorted`, `sum`, `supply.cost_calculations.select_for_update`, `values.items`, `wanted.add`, `warehouse_owned_quantity`.

### `_refresh_sale(sale, rows)`

Исходник: `orders/arrival_documents.py:241`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(CD if kind == 'cd' else Tech).objects.get`, `Decimal`, `ValidationError`, `existing.get`, `existing.items`, `item.delete`, `item.save`, `list`, `manager.all`, `model.objects.create`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `sale.save`, `set`, `setattr`, `sum`, `values.items`, `wanted.add`.

### `_refresh_supply(supply, rows)`

Исходник: `orders/arrival_documents.py:275`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `existing.get`, `existing.items`, `item.delete`, `item.save`, `list`, `model`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `refresh_supply_calculations`, `set`, `sum`, `supply.cd_items.all`, `supply.procurement_order.arrival_rows.select_related`, `supply.procurement_order.arrival_rows.select_related('supplier', 'cd', 'tech').get`, `supply.save`, `supply.tech_items.all`, `wanted.add`.

### `refresh_documents(arrival, *, actor=None)`

Исходник: `orders/arrival_documents.py:310`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.select_for_update`, `TripOrderOperation.objects.select_for_update().filter`, `TripOrderOperation.objects.select_for_update().filter(order__trip_id=arrival.trip_id, active=True).select_related`, `_refresh_sale`, `_refresh_supply`, `cancel_sale`, `cancel_supply`, `cohort_rows`, `operation.save`, `operation_snapshot`, `warehouse_rows`.

### `warehouse_rows(sale)`

Исходник: `orders/arrival_documents.py:334`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `getattr(sale, kind + '_items').filter`, `str`.

### `synchronize_sale_discounts(*, actor, sale)`

Исходник: `orders/arrival_documents.py:341`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.select_related`, `TripOrderOperation.objects.select_related('order').filter`, `TripOrderOperation.objects.select_related('order').filter(sale=sale, active=True).first`, `ValidationError`, `_record_trip_change`, `arrival.rows.select_for_update`, `arrival.rows.select_for_update().filter`, `arrival.save`, `changes.append`, `cohort_rows`, `getattr`, `getattr(sale, kind + '_items').filter`, `lock_arrival`, `operation.calculation.get`, `operation.save`, `operation_snapshot`, `source.save`, `str`, `warehouse_rows`.

## `orders/arrival_finalization.py`

Общая финализация с переиспользованием инструментов штатного прихода.

Импорты: `arrival`, `arrival_documents`, `arrival_math`, `arrival_models`, `core.allocation`, `core.db_retry`, `dataclasses`, `decimal`, `django`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `supplies.finalization`, `supplies.models`, `supplies.services`, `trips`.

### `TripFinalizationRow.delivery_unit(self)`

Исходник: `orders/arrival_finalization.py:22`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `readiness(arrival)`

Исходник: `orders/arrival_finalization.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `any`, `arrival.rows.all`, `arrival.trip.trip_orders.count`, `arrival.trip.trip_orders.order_by`, `errors.append`, `list`, `order.operations.filter`, `order.operations.filter(active=True).select_related`, `order.operations.filter(active=True).select_related('sale', 'supply').first`, `sum`.

### `finalization_rows(arrival)`

Исходник: `orders/arrival_finalization.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripFinalizationRow`, `arrival.rows.select_related`, `arrival.rows.select_related('order', 'supplier', 'cd', 'tech').order_by`, `enumerate`, `rows.append`, `unit_cohorts`.

### `_checked_rows(arrival, raw_rows)`

Исходник: `orders/arrival_finalization.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `finalization_rows`, `parse_finalization_inputs`, `readiness`, `rows_from_inputs`.

### `distribute_arrival(*, actor, arrival_id, expected_revision, raw_rows, selected_keys)`

Исходник: `orders/arrival_finalization.py:78`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_checked_rows`, `auto_distribute_penalty`, `lock_arrival`, `require_arrival_permissions`, `transaction.atomic`.

### `finalize_arrival(*, actor, arrival_id, expected_revision, raw_rows, proposed_prices=None)`

Исходник: `orders/arrival_finalization.py:87`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Атомарно закрепляет затраты всех связанных партий с точным общим итогом. Не принимает приход и не применяет продажные цены карточек.

Статические вызовы: `Decimal`, `ValidationError`, `_checked_rows`, `_record_trip_change`, `_revision`, `arrival.rows.select_for_update`, `arrival.save`, `calculate_finalization_penalty`, `changes.append`, `lock_arrival`, `refresh_documents`, `require_arrival_permissions`, `source.save`, `str`, `sum`, `timezone.now`, `totals.get`, `totals.values`.

### `prepare_supply_posting(supply, *, actor, independent_expenses=None)`

Исходник: `orders/arrival_finalization.py:124`.

Готовит штатную приёмку по окончательным затратам, не проводя товар.

Статические вызовы: `TripArrival.objects.select_for_update`, `TripArrival.objects.select_for_update().get`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(supply=supply, active=True).first`, `_independent_expenses`, `assert_document_finalized`, `refresh_supply_calculations`, `supply.save`.

### `prepare_supply_price_review(*, actor, supply_id, expected_revision_number=None, independent_expenses=None)`

Исходник: `orders/arrival_finalization.py:145`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Открывает обычную проверку цен рейсового прихода по актуальной средней физического склада. Независимые расходы не дублируют D; склад до подтверждения не меняется.

Статические вызовы: `PermissionDenied`, `Supply.objects.select_for_update`, `Supply.objects.select_for_update().get`, `ValidationError`, `_independent_expenses`, `_revision`, `actor.has_perm`, `assert_document_finalized`, `list`, `lock_document_trip`, `prepare_supply_posting`, `refresh_supply_calculations`, `snapshot`, `supply.cost_calculations.order_by`, `supply.cost_calculations.order_by('product_kind', 'cd_id', 'tech_id').values_list`, `supply.save`.

### `_independent_expenses(supply, raw_expenses, actor, arrival)`

Исходник: `orders/arrival_finalization.py:180`.

Независимые расходы конкретного поступления не повторяют доставку рейса.

Статические вызовы: `(allocated / item.quantity).quantize`, `(item.final_line_total / item.quantity).quantize`, `Decimal`, `SupplyExpense.objects.create`, `_normalise_expenses`, `_record_trip_change`, `allocate_amount`, `amount.clean`, `forms.DecimalField`, `item.save`, `list`, `raw.get`, `str`, `str(raw.get('name') or '').strip`, `sum`, `supply.cd_items.order_by`, `supply.expenses.all`, `supply.expenses.all().delete`, `supply.save`, `supply.tech_items.order_by`, `validated.append`, `zip`.

## `orders/arrival_math.py`

Расчёт закупки через USDT и точное представление строк в копейках.

Импорты: `decimal`, `django.core.exceptions`, `price.services`.

### `purchase_cost(aed, usdt_aed, usdt_rub)`

Исходник: `orders/arrival_math.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `ValueError`, `any`, `decimal_value`, `map`, `str`, `value.is_finite`.

### `unit_cohorts(amount, quantity)`

Исходник: `orders/arrival_math.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `amount.is_finite`, `amount.quantize`, `divmod`, `int`, `isinstance`, `str`.

### `preliminary_delivery(source)`

Исходник: `orders/arrival_math.py:28`.

Сохранённые тарифы задают пропорции; актуальные курсы их не изменяют.

Статические вызовы: `ValidationError`, `decimal_value`, `original_rate.is_finite`, `str`, `weighted_procurement_delivery`.

## `orders/arrival_models.py`

Фактические затраты рейса: исходные количества отдельно от сверенного состава.

Импорты: `django.conf`, `django.core.exceptions`, `django.db`, `models`.

### `TripArrival.arrived(self)`

Исходник: `orders/arrival_models.py:31`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TripArrival.finalized(self)`

Исходник: `orders/arrival_models.py:35`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TripArrival.save(self, *args, **kwargs)`

Исходник: `orders/arrival_models.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `getattr`, `self.trip.trip_orders.filter`, `self.trip.trip_orders.filter(operations__calculation__arrival_id=self.pk).exists`, `super`, `super().save`, `type`, `type(self).objects.get`.

### `TripCostRow.missing_quantity(self)`

Исходник: `orders/arrival_models.py:82`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TripCostRow.purchase_total(self)`

Исходник: `orders/arrival_models.py:86`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TripCostRow.save(self, *args, **kwargs)`

Исходник: `orders/arrival_models.py:89`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `getattr`, `super`, `super().save`, `type`, `type(self).objects.select_related`, `type(self).objects.select_related('arrival').get`.

## `orders/arrival_views.py`

Страницы прибытия, сверки и общей финализации рейса.

Импорты: `arrival`, `arrival_documents`, `arrival_finalization`, `arrival_models`, `catalog.product_identifiers`, `core.decorators`, `decimal`, `django`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.urls`, `django.views.decorators.http`, `fulfillment`, `fulfillment_views`, `models`, `operation_changes`, `sales.forms`, `sales.views`, `supplies.models`, `supplies.views`, `warehouse.form_defaults`, `warehouse.models`.

### `missing_weights(batch)`

Исходник: `orders/arrival_views.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `batch.lines.select_related`, `batch.lines.select_related('cd', 'tech').filter`, `products.items`.

### `panel_context(request, batch)`

Исходник: `orders/arrival_views.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ArrivalForm`, `TripArrival.objects.filter`, `TripArrival.objects.filter(trip=batch).first`, `all`, `batch.trip_orders.filter`, `batch.trip_orders.filter(operations__calculation__arrival_id=arrival.pk).exists`, `bool`, `missing_weights`, `readiness`, `request.session.get`, `request.user.has_perm`.

### `update_arrival(request, pk)`

Исходник: `orders/arrival_views.py:46`.

Декораторы: `require_POST`; `permission_required_any('orders.generate_supplier_orders')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SupplierOrderBatch.objects.trips`, `ValidationError`, `arrival_preview`, `confirm_arrival`, `forms.IntegerField`, `forms.IntegerField(min_value=1).clean`, `get_object_or_404`, `isinstance`, `messages.error`, `messages.success`, `missing_weights`, `permission_required_any`, `redirect`, `request.POST.get`, `request.session.pop`, `require_arrival_permissions`, `set_product_weight`, `str`, `transaction.atomic`, `unconfirm_arrival`.

### `prepare_document(request, pk)`

Исходник: `orders/arrival_views.py:78`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('orders.view_order_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_metadata_forms`, `_save_metadata`, `all`, `build_draft`, `dict`, `drafts.items`, `get_object_or_404`, `list`, `messages.error`, `permission_required_any`, `redirect`, `render`, `request.session.get`, `require_http_methods`, `reverse`, `row['form'].is_valid`, `transaction.atomic`.

### `receipt(request, pk)`

Исходник: `orders/arrival_views.py:105`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('orders.view_order_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ValidationError`, `arrival.rows.filter`, `arrival.rows.filter(order=order).select_related`, `dict`, `get_object_or_404`, `isinstance`, `len`, `messages.error`, `messages.success`, `order.operations.filter`, `order.operations.filter(active=True).select_related`, `order.operations.filter(active=True).select_related('sale', 'supply').first`, `permission_required_any`, `redirect`, `reduce_received`, `render`, `request.POST.get`, `request.POST.getlist`, `require_http_methods`, `require_permissions`, `set`, `zip`.

### `_posted_rows(request, arrival, order, *, supply=False)`

Исходник: `orders/arrival_views.py:126`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_parse_lines`, `_parse_supply_post`, `amount.clean`, `any`, `expense.get`, `forms.DecimalField`, `len`, `request.POST.getlist`, `zip`.

### `sale_form(request, order, draft)`

Исходник: `orders/arrival_views.py:141`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SaleCreateForm`, `_posted_rows`, `_refresh_draft`, `_sale_destination`, `create_arrival_sale`, `form.add_error`, `form.is_valid`, `form_rows`, `get_object_or_404`, `isinstance`, `messages.success`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `single_warehouse_id`, `str`.

### `supply_form(request, order, draft)`

Исходник: `orders/arrival_views.py:175`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Warehouse.objects.all`, `_posted_rows`, `_refresh_draft`, `_supplier_options`, `create_arrival_supply`, `form_rows`, `get_object_or_404`, `isinstance`, `messages.error`, `messages.success`, `redirect`, `render`, `request.POST.get`, `single_warehouse_id`, `str`.

### `_prices(post, arrival)`

Исходник: `orders/arrival_views.py:204`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `name.startswith`.

### `finalization(request, pk)`

Исходник: `orders/arrival_views.py:212`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('supplies.finalize_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Decimal`, `_parse_finalization_post`, `_prices`, `finalization_rows`, `finalize_arrival`, `get_object_or_404`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `readiness`, `redirect`, `render`, `request.POST.get`, `require_arrival_permissions`, `require_http_methods`.

### `finalization_auto(request, pk)`

Исходник: `orders/arrival_views.py:237`.

Декораторы: `require_POST`; `permission_required_any('supplies.finalize_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `_parse_finalization_post`, `distribute_arrival`, `get_object_or_404`, `int`, `isinstance`, `permission_required_any`, `raw.partition`, `request.POST.get`, `request.POST.getlist`, `selected.add`, `set`.

### `post_supply(request, pk)`

Исходник: `orders/arrival_views.py:256`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ValidationError`, `forms.IntegerField`, `forms.IntegerField(min_value=1).clean`, `get_object_or_404`, `isinstance`, `len`, `messages.error`, `permission_required_any`, `prepare_supply_price_review`, `redirect`, `request.POST.get`, `request.POST.getlist`, `zip`.

### `_refresh_draft(request, order, draft, arrival)`

Исходник: `orders/arrival_views.py:273`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `build_draft`, `request.session.get`.

## `orders/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `django`, `models`, `partners.customers`, `warehouse.form_defaults`, `warehouse.models`.

### `ProcurementOrderUploadForm.clean(self)`

Исходник: `orders/forms.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `forms.ValidationError`, `resolve_customer`, `self.add_error`, `self.files.get`, `super`, `super().clean`.

### `TripAssignmentForm.__init__(self, *args, trips, order, **kwargs)`

Исходник: `orders/forms.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `TripAssignmentForm.clean_target_trip(self)`

Исходник: `orders/forms.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `self.cleaned_data['target_trip'].split`.

### `TripOrdersChoiceField.label_from_instance(self, order)`

Исходник: `orders/forms.py:84`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TripAddOrdersForm.__init__(self, *args, batch, **kwargs)`

Исходник: `orders/forms.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.filter`, `CustomerProcurementOrder.objects.filter(trip__isnull=True, status='created', price_list__is_trip_addition=False).select_related`, `CustomerProcurementOrder.objects.filter(trip__isnull=True, status='created', price_list__is_trip_addition=False).select_related('price_list').order_by`, `orders.filter`, `super`, `super().__init__`.

## `orders/fulfillment.py`

Создание штатных продаж/приходов из рейса без повторного складского и денежного учёта.

Импорты: `arrival_documents`, `arrival_math`, `arrival_models`, `cash.models`, `catalog.game_codes`, `catalog.models`, `collections`, `core.db_retry`, `decimal`, `django`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`, `operation_changes`, `price.services`, `sales.models`, `sales.services`, `supplies.services`, `uuid`.

### `require_permissions(actor, order)`

Исходник: `orders/fulfillment.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `actor.has_perm`, `all`.

### `available(order)`

Исходник: `orders/fulfillment.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `bool`, `order.operations.all`.

### `operation_actions(actor, orders)`

Исходник: `orders/fulfillment.py:35`.

Одинаковые права и доступность кнопок для списка, рейса и карточки заказа.

Статические вызовы: `SupplierOrderBatchLine.objects.filter`, `SupplierOrderBatchLine.objects.filter(batch_id__in=trip_ids, quantity__gt=0).values_list`, `SupplierTripInvoice.objects.filter`, `SupplierTripInvoice.objects.filter(batch_id__in=trip_ids, accepted=True).values_list`, `TripArrival.objects.filter`, `accepted[batch_id].add`, `arrivals.get`, `available`, `bool`, `defaultdict`, `list`, `next`, `order.arrival_rows.filter`, `order.arrival_rows.filter(actual_quantity__gt=0).exists`, `order.operations.all`, `require_permissions`, `suppliers[batch_id].add`, `suppliers[order.trip_id].issubset`.

### `require_available(order)`

Исходник: `orders/fulfillment.py:68`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `available`.

### `_rate(value, label)`

Исходник: `orders/fulfillment.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `field.clean`, `forms.DecimalField`.

### `_round(value)`

Исходник: `orders/fulfillment.py:78`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `decimal_value`, `forms.DecimalField`, `forms.DecimalField(max_digits=20, decimal_places=2, min_value=0).clean`.

### `_delivery(source, usd_rub)`

Исходник: `orders/fulfillment.py:85`.

Тот же тариф × вес; рублёвый тариф диска переводится через сохранённый курс прайса.

Статические вызовы: `Decimal`, `ValidationError`, `_round`, `str`, `weighted_procurement_delivery`.

### `calculation(order, *, usd_rub, usd_aed=None, aed_rub=None, _delivery_weights=False)`

Исходник: `orders/fulfillment.py:111`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.get`, `Decimal`, `ValidationError`, `_delivery`, `_rate`, `_round`, `aed.is_finite`, `decimal_value`, `item.trip_allocations.all`, `order.items.select_related`, `order.items.select_related('price_list_item__price_list', 'cd__platform', 'tech').prefetch_related`, `order.items.select_related('price_list_item__price_list', 'cd__platform', 'tech').prefetch_related('trip_allocations__line').order_by`, `preliminary_delivery`, `prepaid_amount`, `rows.append`, `sorted`, `str`, `sum`.

### `fingerprint(data)`

Исходник: `orders/fulfillment.py:172`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `hashlib.sha256`, `hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False).encode()).hexdigest`, `json.dumps`, `json.dumps(data, sort_keys=True, ensure_ascii=False).encode`.

### `prepaid_amount(order)`

Исходник: `orders/fulfillment.py:176`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Sum`, `dict`, `order.cash_transactions.values`, `order.cash_transactions.values('operation_type').annotate`, `order.cash_transactions.values('operation_type').annotate(total=Sum('amount')).values_list`, `totals.get`.

### `_locked_draft(actor, draft)`

Исходник: `orders/fulfillment.py:184`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(draft_key=draft['key']).first`, `UUID`, `ValidationError`, `calculation`, `fingerprint`, `require_available`, `require_permissions`.

### `_link(actor, order, draft, *, sale=None, supply=None, snapshot=None)`

Исходник: `orders/fulfillment.py:205`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `TripOrderOperation.objects.create`, `UUID`, `synchronize`.

### `_create_legacy_direct_sale(*, actor, draft, changes_confirmation='', **kwargs)`

Исходник: `orders/fulfillment.py:215`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `_create_sale`, `_link`, `_locked_draft`, `_round`, `confirm_changes`, `kwargs.items`, `kwargs.update`, `operation_snapshot`, `resolve_rows`, `str`, `sum`.

### `_create_legacy_order_supply(*, actor, draft, warehouse_id, lines=None, changes_confirmation='', **unused)`

Исходник: `orders/fulfillment.py:245`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `_link`, `_locked_draft`, `_round`, `accept_supply`, `confirm_changes`, `draft_rows`, `model.objects.filter`, `operation_snapshot`, `products.extend`, `resolve_rows`, `str`, `sum`, `validate_supply_game_codes`.

### `validate_supply_snapshot(supply, lines, expenses, weight_transport_cost)`

Исходник: `orders/fulfillment.py:271`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(supply=supply).first`, `ValidationError`, `_normalise_expenses`, `_normalise_lines`, `_normalise_weight_transport_cost`, `sorted`.

### `synchronize(operation, *, actor=None)`

Исходник: `orders/fulfillment.py:285`.

Декораторы: `transaction.atomic`.

Вызывается в транзакции штатного сервиса после фактического изменения документа.

Статические вызовы: `CustomerOrderStatusEvent.objects.create`, `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `operation.save`, `order.save`.

### `edit_direct_sale(*, actor, sale, lines, note, partner_id, partner_name)`

Исходник: `orders/fulfillment.py:311`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `_round`, `_sale_product_lines`, `any`, `existing.get`, `existing.update`, `existing.values`, `getattr`, `int`, `item.full_clean`, `item.save`, `r.get`, `sale.cd_items.select_for_update`, `sale.full_clean`, `sale.save`, `sale.tech_items.select_for_update`, `seen.add`, `set`, `str`, `str(note).strip`, `str(partner_name).strip`, `sum`, `synchronize_sale_discounts`.

### `create_direct_sale(*, actor, draft, changes_confirmation='', **kwargs)`

Исходник: `orders/fulfillment.py:354`.

Новые документы используют только общие зафиксированные затраты рейса.

Статические вызовы: `ValidationError`, `create_arrival_sale`, `draft.get`, `kwargs.get`.

### `create_order_supply(*, actor, draft, warehouse_id, lines=None, changes_confirmation='')`

Исходник: `orders/fulfillment.py:367`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `create_arrival_supply`, `draft.get`.

## `orders/fulfillment_views.py`

Общие реквизиты и переход из заказа в форму документа прибывшего рейса.

Импорты: `arrival_models`, `arrival_views`, `catalog.game_codes`, `catalog.models`, `catalog.product_identifiers`, `core.decorators`, `django`, `django.contrib`, `django.core.exceptions`, `django.shortcuts`, `django.views.decorators.http`, `fulfillment`, `models`.

### `_metadata_forms(order, data=None)`

Исходник: `orders/fulfillment_views.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(**{kind + '_id': product.pk}).exists`, `form.fields.update`, `forms.CharField`, `forms.Form`, `forms.IntegerField`, `order.items.select_related`, `order.items.select_related('cd__platform', 'tech').order_by`, `product.cusa_ppsa_code.strip`, `requires_game_codes`, `result.append`, `seen.add`, `set`.

### `_save_metadata(actor, rows)`

Исходник: `orders/fulfillment_views.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `actor.has_perm`, `add_product_barcode`, `normalize_game_codes`, `set_game_codes`, `set_product_weight`, `values.get`.

### `prepare(request, pk)`

Исходник: `orders/fulfillment_views.py:60`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('orders.view_order_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `permission_required_any`, `prepare_document`, `require_http_methods`.

### `_draft(request)`

Исходник: `orders/fulfillment_views.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(pk=draft['arrival_id'], trip_id=order.trip_id, arrived_at__isnull=False).exists`, `ValidationError`, `draft.get`, `get_object_or_404`, `request.GET.get`, `request.POST.get`, `request.session.get`, `request.session.get(DRAFTS, {}).get`, `require_permissions`.

### `sale_create(request)`

Исходник: `orders/fulfillment_views.py:78`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `_draft`, `messages.error`, `redirect`, `sale_form`.

### `supply_create(request)`

Исходник: `orders/fulfillment_views.py:90`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `_draft`, `messages.error`, `redirect`, `supply_form`.

## `orders/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `arrival_models`, `catalog.models`, `decimal`, `django.conf`, `django.core.exceptions`, `django.core.validators`, `django.db`, `partners.models`, `price.models`, `warehouse.models`.

### `TripOrderOperation.save(self, *args, **kwargs)`

Исходник: `orders/models.py:48`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `getattr`, `super`, `super().save`, `type`, `type(self).objects.get`.

### `ProductReferenceMixin.product(self)`

Исходник: `orders/models.py:75`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProductReferenceMixin.product_id(self)`

Исходник: `orders/models.py:79`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrder.is_stock_order(self)`

Исходник: `orders/models.py:159`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrder.fulfillment_label(self)`

Исходник: `orders/models.py:163`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip_id=self.trip_id, arrived_at__isnull=False).first`, `bool`, `getattr`, `hasattr`, `self.arrival_rows.filter`, `self.arrival_rows.filter(actual_quantity__gt=0).exists`, `self.get_status_display`, `self.trip.invoice_flags.filter`, `self.trip.invoice_flags.filter(accepted=True).values_list`, `self.trip.lines.filter`, `self.trip.lines.filter(quantity__gt=0).values_list`, `set`, `suppliers.issubset`.

### `CustomerProcurementOrder.fulfillment_processing(self)`

Исходник: `orders/models.py:184`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `bool`, `self.operations.all`.

### `CustomerProcurementOrder.fulfillment_completed(self)`

Исходник: `orders/models.py:189`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`.

### `CustomerProcurementOrder.total_units(self)`

Исходник: `orders/models.py:193`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.items.all`, `sum`.

### `CustomerProcurementOrder.__str__(self)`

Исходник: `orders/models.py:196`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderItem.prepayment_line_total(self)`

Исходник: `orders/models.py:244`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderItem.quantity(self)`

Исходник: `orders/models.py:248`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderItem.postpayment_line_total(self)`

Исходник: `orders/models.py:252`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderItem.line_total(self)`

Исходник: `orders/models.py:256`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CustomerProcurementOrderItem.__str__(self)`

Исходник: `orders/models.py:259`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierOrderBatchQuerySet.trips(self)`

Исходник: `orders/models.py:319`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `models.Q`, `self.filter`.

### `SupplierOrderBatch.__str__(self)`

Исходник: `orders/models.py:348`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierOrderBatch.is_trip(self)`

Исходник: `orders/models.py:352`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierOrderBatch.is_completed(self)`

Исходник: `orders/models.py:356`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `all`, `bool`, `list`, `self.source_orders.all`, `self.trip_orders.all`.

### `SupplierOrderBatch.completion_label(self)`

Исходник: `orders/models.py:362`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierOrderBatchLine.__str__(self)`

Исходник: `orders/models.py:422`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierOrderBatchLine.total_aed(self)`

Исходник: `orders/models.py:426`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierTripAllocation.quantity(self)`

Исходник: `orders/models.py:442`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `orders/operation_changes.py`

Проверка редактируемого состава и подписанное подтверждение отличий от заказа.

Импорты: `catalog.models`, `decimal`, `django`, `django.core`, `django.core.exceptions`, `partners.models`.

### `ChangesConfirmationRequired.__init__(self, *, actor, draft, rows, changes, details)`

Исходник: `orders/operation_changes.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `confirmation_values`, `signing.dumps`, `super`, `super().__init__`.

### `confirmation_values(actor, draft, rows, details)`

Исходник: `orders/operation_changes.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `encoded.encode`, `hashlib.sha256`, `hashlib.sha256(encoded.encode()).hexdigest`, `json.dumps`.

### `confirm_changes(*, actor, draft, rows, changes, details, token='')`

Исходник: `orders/operation_changes.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ChangesConfirmationRequired`, `confirmation_values`, `signing.loads`.

### `draft_rows(draft)`

Исходник: `orders/operation_changes.py:39`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enumerate`, `str`.

### `_amount(value, *, precision=2, label='Сумма')`

Исходник: `orders/operation_changes.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `forms.DecimalField`, `forms.DecimalField(max_digits=20, decimal_places=precision, min_value=0).clean`.

### `resolve_rows(*, draft, lines, supply=False)`

Исходник: `orders/operation_changes.py:50`.

Исходные партии сохраняют снимки; добавленные продажи получают цену/стоимость из каталога.

Статические вызовы: `Decimal`, `Supplier.objects.filter`, `Supplier.objects.filter(pk__in=[original['supplier_id'], supplier_id]).values_list`, `Supplier.objects.filter(pk__in=ids).count`, `ValidationError`, `_amount`, `abs`, `any`, `changes.append`, `dict`, `draft_rows`, `enumerate`, `forms.DecimalField`, `forms.DecimalField(max_digits=20, decimal_places=2).clean`, `forms.IntegerField`, `forms.IntegerField(min_value=0, max_value=2147483647).clean`, `forms.IntegerField(min_value=1).clean`, `int`, `len`, `letters.get`, `model.objects.active`, `model.objects.active().select_for_update`, `model.objects.active().select_for_update().filter`, `originals.get`, `originals.items`, `products.update`, `raw.get`, `result.append`, `row.get`, `row.update`, `set`, `str`, `str(raw.get('line_note') or '').strip`, `used.add`, `value.isdecimal`.

### `operation_snapshot(draft, rows, changes)`

Исходник: `orders/operation_changes.py:133`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `orders/order_editing.py`

Граница редактирования закупки по фактическим последующим операциям.

Импорты: `arrival_models`, `django.core.exceptions`.

### `downstream_lock_reason(order)`

Исходник: `orders/order_editing.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip_id=order.trip_id, arrived_at__isnull=False).exists`, `any`, `order.operations.all`.

### `require_untransferred_order(order)`

Исходник: `orders/order_editing.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `downstream_lock_reason`.

## `orders/order_excel.py`

Снимок текущего состава заказа с сохранёнными ценами покупателя.

Импорты: `catalog.nomenclature_grouping`, `core.excel_layout`, `decimal`, `django.utils`, `io`, `openpyxl`, `openpyxl.styles`, `openpyxl.worksheet.page`, `price.excel`, `trip_prices`.

### `order_xlsx(*, order, items)`

Исходник: `orders/order_excel.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `Border`, `BytesIO`, `Decimal`, `Font`, `PageMargins`, `PatternFill`, `Side`, `Workbook`, `book.close`, `book.save`, `chr`, `enumerate`, `headers.append`, `headers.extend`, `isinstance`, `len`, `list`, `nomenclature_product_groups`, `order.get_status_display`, `output.getvalue`, `rows.append`, `safe_text`, `sheet.append`, `sheet.cell`, `sheet.merge_cells`, `stock_purchase_rows`, `sum`, `text_row`, `timezone.localtime`, `value.to_integral_value`, `wrapped_text_height`.

## `orders/order_supplier_excel.py`

Состав одного заказа по фактическим распределениям рейса и сохранённым ценам.

Импорты: `catalog.nomenclature_grouping`, `collections`, `core.excel_layout`, `dataclasses`, `decimal`, `django.core.exceptions`, `django.utils`, `io`, `openpyxl`, `openpyxl.styles`, `price.excel`.

### `SupplierOrderExportRow.product(self)`

Исходник: `orders/order_supplier_excel.py:26`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `build_order_supplier_rows(*, order, items)`

Исходник: `orders/order_supplier_excel.py:30`.

Не использует общий объём строки рейса или актуальные предложения поставщиков.

Статические вызовы: `SupplierOrderExportRow`, `ValidationError`, `item.trip_allocations.all`, `rows.append`, `sum`.

### `order_suppliers_xlsx(*, order, rows, show_supplier_details=False)`

Исходник: `orders/order_supplier_excel.py:57`.

Закупочные суммы считаются один раз по строкам распределения, без повторного итога.

Статические вызовы: `Alignment`, `Border`, `BytesIO`, `Decimal`, `Font`, `OrderedDict`, `PatternFill`, `Side`, `ValidationError`, `Workbook`, `book.close`, `book.save`, `chr`, `data_row`, `enumerate`, `list`, `max`, `nomenclature_product_groups`, `output.getvalue`, `row.supplier.letter.casefold`, `safe_text`, `sheet.append`, `sheet.cell`, `sheet.merge_cells`, `sorted`, `sum`, `suppliers.setdefault`, `suppliers.setdefault(supplier_id, (row.supplier, []))[1].append`, `suppliers.values`, `text_row`, `timezone.localtime`, `value.to_integral_value`, `wrapped_text_height`.

## `orders/services.py`

Транзакционные переходы клиентских закупочных заказов, их предоплаты/приёмки и связанных записей.

Импорты: `cash.models`, `catalog.supplier_exclusions`, `collections`, `decimal`, `django.core.exceptions`, `django.db`, `models`, `order_editing`, `partners.customers`, `price.models`, `supplies.services`, `trip_prices`, `trips`, `warehouse.models`.

### `_quantity(value, label)`

Исходник: `orders/services.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`, `isinstance`, `str`, `str(value).strip`.

### `_normalise_lines(lines)`

Исходник: `orders/services.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_quantity`, `int`, `raw.get`.

### `_validate_stock_quantities(purpose, quantities)`

Исходник: `orders/services.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`.

### `_new_item(order, source, prepayment, postpayment)`

Исходник: `orders/services.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrderItem`.

### `_totals(items)`

Исходник: `orders/services.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `sum`.

### `_save_totals(order, items)`

Исходник: `orders/services.py:88`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_totals`, `order.full_clean`, `order.save`.

### `create_customer_procurement_order(*, actor, price_list_id, recipient, comment, lines, purpose=CustomerProcurementOrder.Purpose.CUSTOMER, partner_id=None, partner_name='')`

Исходник: `orders/services.py:98`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.create`, `CustomerProcurementOrderItem.objects.bulk_create`, `PermissionDenied`, `ProcurementPriceList.objects.select_for_update`, `ProcurementPriceList.objects.select_for_update().get`, `ProcurementPriceListItem.objects.select_for_update`, `ProcurementPriceListItem.objects.select_for_update().select_related`, `ProcurementPriceListItem.objects.select_for_update().select_related('cd', 'tech', 'selected_supplier').filter`, `ValidationError`, `_new_item`, `_normalise_lines`, `_save_totals`, `_validate_stock_quantities`, `actor.has_perm`, `any`, `len`, `logger.info`, `prepared.items`, `prepared.values`, `resolve_customer`, `set`, `source_items.values`, `str`, `str(comment or '').strip`, `str(recipient or '').strip`, `validate_supplier_assignments`.

### `edit_created_order(*, actor, order_id, recipient, comment, lines, partner_id=None, partner_name=None)`

Исходник: `orders/services.py:149`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `CustomerProcurementOrderItem.objects.select_for_update`, `CustomerProcurementOrderItem.objects.select_for_update().filter`, `ProcurementPriceListItem.objects.select_for_update`, `ProcurementPriceListItem.objects.select_for_update().select_related`, `ProcurementPriceListItem.objects.select_for_update().select_related('cd', 'tech', 'selected_supplier').filter`, `ValidationError`, `_new_item`, `_normalise_lines`, `_save_totals`, `_validate_stock_quantities`, `any`, `existing.items`, `item.delete`, `item.full_clean`, `item.save`, `list`, `logger.info`, `order.items.all`, `order.save`, `prepared.get`, `prepared.items`, `prepared.values`, `require_untransferred_order`, `resolve_customer`, `set`, `sources.values`, `str`, `str(comment or '').strip`, `str(recipient or '').strip`, `sum`, `validate_supplier_assignments`.

### `_locked_register(warehouse_id)`

Исходник: `orders/services.py:212`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashRegister.objects.select_for_update`, `CashRegister.objects.select_for_update().select_related`, `CashRegister.objects.select_for_update().select_related('warehouse').get`, `ValidationError`.

### `_select_payment_warehouse(order, warehouse_id, *, required)`

Исходник: `orders/services.py:219`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `Warehouse.objects.filter`, `Warehouse.objects.filter(pk=warehouse_id).exists`, `int`.

### `_status_event(order, actor, old_status, new_status)`

Исходник: `orders/services.py:238`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerOrderStatusEvent.objects.create`.

### `advance_order_status(*, actor, order_id, next_status, warehouse_id=None)`

Исходник: `orders/services.py:245`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashTransaction.objects.create`, `CashTransaction.objects.select_for_update`, `CashTransaction.objects.select_for_update().filter`, `CashTransaction.objects.select_for_update().filter(customer_order=order, operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_POSTPAYMENT).exists`, `CashTransaction.objects.select_for_update().filter(customer_order=order, operation_type=CashTransaction.OperationType.CUSTOMER_ORDER_PREPAYMENT).exists`, `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `ValidationError`, `_locked_register`, `_select_payment_warehouse`, `_status_event`, `logger.info`, `order.save`, `receive_stock_order`, `register.full_clean`, `register.save`, `require_untransferred_order`, `transitions.get`.

### `reduce_receiving_order(*, actor, order_id, comment, rows, allow_refund=True)`

Исходник: `orders/services.py:306`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashTransaction.objects.create`, `CustomerProcurementOrder.objects.filter`, `CustomerProcurementOrder.objects.filter(pk=order_id).values_list`, `CustomerProcurementOrder.objects.filter(pk=order_id).values_list('trip_id', flat=True).first`, `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `CustomerProcurementOrderItem.objects.select_for_update`, `CustomerProcurementOrderItem.objects.select_for_update().filter`, `OrderAdjustment.objects.create`, `OrderAdjustmentChange`, `OrderAdjustmentChange.objects.bulk_create`, `SupplierOrderBatch.objects.select_for_update`, `SupplierOrderBatch.objects.select_for_update().get`, `SupplierOrderBatchLine.objects.select_for_update`, `SupplierOrderBatchLine.objects.select_for_update().get`, `ValidationError`, `_assert_balances`, `_locked_register`, `_quantity`, `_record_trip_change`, `allocation.save`, `changes.append`, `existing.items`, `getattr`, `int`, `item.delete`, `item.save`, `item.trip_allocations.exists`, `item.trip_allocations.select_for_update`, `item.trip_allocations.select_for_update().filter`, `item.trip_allocations.select_for_update().filter(line__batch=batch).order_by`, `line.save`, `list`, `logger.info`, `min`, `order.save`, `raw.get`, `register.full_clean`, `register.save`, `require_untransferred_order`, `set`, `setattr`, `str`, `str(comment or '').strip`, `sum`.

### `receive_stock_order(*, actor, order_id, warehouse_id)`

Исходник: `orders/services.py:434`.

Декораторы: `transaction.atomic`.

Создать один приход по доставленному заказу, сохранив исходную стоимость.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `PermissionDenied`, `ValidationError`, `_status_event`, `accept_supply`, `actor.has_perm`, `allocation_unit_cost`, `item.trip_allocations.select_related`, `item.trip_allocations.select_related('line').order_by`, `lines.append`, `logger.info`, `min`, `order.items.select_for_update`, `order.items.select_for_update().order_by`, `order.save`.

### `create_supplier_order_batch(*, actor, order_ids)`

Исходник: `orders/services.py:489`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(data['supplier_cost_total'] / data['quantity']).quantize`, `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().filter`, `CustomerProcurementOrder.objects.select_for_update().filter(pk__in=ids).order_by`, `CustomerProcurementOrderItem.objects.select_for_update`, `CustomerProcurementOrderItem.objects.select_for_update().select_related`, `CustomerProcurementOrderItem.objects.select_for_update().select_related('cd', 'tech', 'selected_supplier').filter`, `CustomerProcurementOrderItem.objects.select_for_update().select_related('cd', 'tech', 'selected_supplier').filter(order_id__in=ids).order_by`, `Decimal`, `SupplierOrderBatch.objects.create`, `SupplierOrderBatchLine`, `SupplierOrderBatchLine.objects.bulk_create`, `ValidationError`, `aggregated.items`, `batch.source_orders.set`, `int`, `len`, `lines.append`, `list`, `logger.info`, `validate_supplier_assignments`.

## `orders/signals.py`

Состояние заказа следует за штатной продажей/приходом, включая административное сохранение.

Импорты: `django.db.models.signals`, `django.dispatch`, `fulfillment`, `models`, `sales.models`, `supplies.models`.

### `document_saved(sender, instance, raw=False, **kwargs)`

Исходник: `orders/signals.py:11`.

Декораторы: `receiver(post_save, sender=Sale)`; `receiver(post_save, sender=Supply)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(active=True, **lookup).first`, `getattr`, `receiver`, `synchronize`.

## `orders/stock_order_form.py`

Ручной подбор закупки на склад из сохранённой версии импортного прайса.

Импорты: `catalog.nomenclature_grouping`, `catalog.supplier_exclusions`, `django`, `django.db.models`, `models`, `price.models`, `warehouse.models`.

### `StockOrderCreateForm.__init__(self, *args, items, target_trip=None, **kwargs)`

Исходник: `orders/stock_order_form.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `forms.IntegerField`, `forms.NumberInput`, `int`, `super`, `super().__init__`.

### `StockOrderCreateForm.clean(self)`

Исходник: `orders/stock_order_form.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `data.get`, `forms.ValidationError`, `name.startswith`, `self.data.get`, `super`, `super().clean`.

### `StockOrderCreateForm.order_lines(self)`

Исходник: `orders/stock_order_form.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.cleaned_data.get`.

### `stock_order_items(price_list)`

Исходник: `orders/stock_order_form.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Q`, `exclusion_keys`, `len`, `list`, `price_list.items.select_related`, `price_list.items.select_related('cd__platform', 'cd__game_series', 'tech__brand', 'tech__product_type').filter`.

### `previous_trip_stock_quantities(target_trip=None)`

Исходник: `orders/stock_order_form.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrderItem.objects.filter`, `CustomerProcurementOrderItem.objects.filter(order__trip=trip, order__purpose=CustomerProcurementOrder.Purpose.STOCK).values`, `CustomerProcurementOrderItem.objects.filter(order__trip=trip, order__purpose=CustomerProcurementOrder.Purpose.STOCK).values('product_kind', 'cd_id', 'tech_id').annotate`, `Q`, `Sum`, `SupplierOrderBatch.objects.trips`, `trips.filter`, `trips.first`.

### `stock_order_groups(items, form, *, previous_trip_quantities=None)`

Исходник: `orders/stock_order_form.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `model.objects.filter`, `model.objects.filter(**{f'{kind}_id__in': ids}).values`, `model.objects.filter(**{f'{kind}_id__in': ids}).values(f'{kind}_id').annotate`, `nomenclature_product_groups`, `previous_trip_quantities.get`, `totals.get`.

## `orders/stock_order_views.py`

Ручная закупка на склад; клиентские назначения не включаются в подсказку уже заказанного складского объёма.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.http`, `models`, `price.models`, `stock_order_form`, `trips`, `views`.

### `stock_order_create(request, trip_pk=None)`

Исходник: `orders/stock_order_views.py:22`.

Декораторы: `never_cache`; `require_http_methods(['GET', 'POST'])`; `permission_required_all('orders.create_order', 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ProcurementPriceList.objects.filter`, `ProcurementPriceList.objects.filter(is_trip_addition=False).first`, `StockOrderCreateForm`, `StockOrderPriceListForm`, `SupplierOrderBatch.objects.trips`, `_require_editable_trip`, `can_manage_trips`, `choice_form.fields['price_list'].queryset.filter`, `choice_form.is_valid`, `draft.get`, `form.is_valid`, `form.order_lines`, `get_object_or_404`, `messages.error`, `permission_required_all`, `previous_trip_stock_quantities`, `redirect`, `render`, `request.GET.get`, `request.POST.get`, `request.session.get`, `require_http_methods`, `stock_order_groups`, `stock_order_items`, `transaction.atomic`.

## `orders/trip_addition_views.py`

Пошаговая форма дополнительных товаров текущего рейса.

Импорты: `catalog.models`, `catalog.product_search`, `core.decorators`, `decimal`, `django`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.urls`, `django.views.decorators.cache`, `django.views.decorators.http`, `models`, `partners.customers`, `partners.models`, `price.models`, `trip_additions`, `trips`, `uuid`.

### `_url(pk, draft_id, step)`

Исходник: `orders/trip_addition_views.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `reverse`.

### `calculation(request, pk)`

Исходник: `orders/trip_addition_views.py:56`.

Декораторы: `never_cache`; `require_POST`; `permission_required_all(*PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `LineFormSet`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_related`, `enumerate`, `form.cleaned_data.get`, `form.is_valid`, `formset.management_form.is_valid`, `formset.total_form_count`, `get_object_or_404`, `permission_required_all`, `prepare_addition`, `request.POST.get`, `results.append`, `str`.

### `product_search(request, pk)`

Исходник: `orders/trip_addition_views.py:78`.

Декораторы: `never_cache`; `permission_required_all(*PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `SupplierOrderBatch.objects.trips`, `filter_products_by_text`, `filter_products_by_text(model.objects.active(), query, product_kind=kind).select_related`, `filter_products_by_text(model.objects.active(), query, product_kind=kind).select_related(group).order_by`, `get_object_or_404`, `getattr`, `len`, `model.objects.active`, `permission_required_all`, `request.GET.get`, `results.append`, `str`, `str(request.GET.get('q') or '').strip`.

### `addition(request, pk)`

Исходник: `orders/trip_addition_views.py:94`.

Декораторы: `never_cache`; `permission_required_all(*PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `', '.join`, `AdditionCalculationForm`, `AdditionPartnersForm`, `LineFormSet`, `ProcurementPriceList.objects.filter`, `ProcurementPriceList.objects.filter(is_trip_addition=False).values_list`, `ProcurementPriceList.objects.filter(is_trip_addition=False).values_list('pk', flat=True).first`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_related`, `UUID`, `ValidationError`, `_url`, `addition_price_list`, `allocation_form.is_valid`, `calculation_form.is_valid`, `calculation_form['calculation_price_list'].value`, `commit_addition`, `draft.get`, `draft.get('allocations', {}).get`, `enumerate`, `form.cleaned_data.get`, `forms.Form`, `forms.IntegerField`, `get_object_or_404`, `int`, `isinstance`, `len`, `line_formset.is_valid`, `list`, `max`, `messages.success`, `min`, `order_preview.append`, `partner_form.cleaned_data['partners'].values_list`, `partner_form.is_valid`, `permission_required_all`, `prepare_addition`, `redirect`, `render`, `request.GET.get`, `request.session.get`, `row['allocation_fields'].append`, `row['distribution'].get`, `str`, `uuid4`.

## `orders/trip_additions.py`

Дополнительная закупка: новые заказы и партии без перерасчёта прежнего состава.

Импорты: `arrival_models`, `catalog.models`, `catalog.supplier_exclusions`, `decimal`, `django.core.exceptions`, `django.db`, `models`, `partners.models`, `price.models`, `price.services`, `services`, `trip_prices`, `trips`, `uuid`.

### `_fingerprint(value)`

Исходник: `orders/trip_additions.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `hashlib.sha256`, `hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest`, `json.dumps`, `json.dumps(value, sort_keys=True, default=str).encode`.

### `addition_price_list(batch, calculation_price_list_id=None)`

Исходник: `orders/trip_additions.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementPriceList.objects.get`, `ValidationError`, `int`, `str`.

### `prepare_addition(*, batch, lines, partner_ids=(), allocations=None, require_partners=True, calculation_price_list_id=None)`

Исходник: `orders/trip_additions.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Partner.objects.filter`, `Partner.objects.filter(pk__in=ids, is_archived=False).order_by`, `Supplier.objects.get`, `TripArrival.objects.filter`, `TripArrival.objects.filter(trip=batch, arrived_at__isnull=False).exists`, `ValidationError`, `_fingerprint`, `_quantity`, `addition_price_list`, `any`, `decimal_value`, `dict`, `enumerate`, `getattr`, `int`, `len`, `list`, `model.objects.active`, `model.objects.active().select_related`, `model.objects.active().select_related('platform' if kind == 'cd' else 'product_type').get`, `procurement_delivery`, `rate.is_finite`, `row.items`, `row.update`, `row['distribution'].values`, `rows.append`, `seen.add`, `set`, `sorted`, `str`, `str(source['product']).split`, `sum`, `validate_supplier_assignments`, `validated_aed`.

### `commit_addition(*, actor, batch_id, key, lines, partner_ids, allocations, preview_fingerprint, revision, calculation_price_list_id=None)`

Исходник: `orders/trip_additions.py:108`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `ProcurementPriceList.objects.create`, `ProcurementPriceListItem.objects.create`, `ProcurementSupplierOffer.objects.create`, `SupplierOrderBatch.objects.select_for_update`, `SupplierOrderBatch.objects.select_for_update().select_related`, `SupplierOrderBatch.objects.select_for_update().select_related('price_list').get`, `SupplierTripAllocation.objects.create`, `TripAdditionReceipt.objects.create`, `TripAdditionReceipt.objects.filter`, `TripAdditionReceipt.objects.filter(pk=key).first`, `UUID`, `ValidationError`, `_assert_balances`, `_fingerprint`, `_line_for`, `_record_trip_change`, `_require_manage`, `actor.has_perm`, `addition_price_list`, `batch.source_orders.add`, `create_customer_procurement_order`, `existing.orders.all`, `getattr`, `line.save`, `list`, `order.items.select_related`, `order.save`, `order_lines.append`, `orders.append`, `prepare_addition`, `receipt.orders.set`, `row['distribution'].get`, `sources.append`, `str`, `zip`.

## `orders/trip_excel.py`

Общий состав рейса и заказ поставщику из сохранённых строк.

Импорты: `catalog.game_codes`, `catalog.nomenclature_grouping`, `dataclasses`, `decimal`, `io`, `openpyxl`, `openpyxl.styles`, `openpyxl.utils`, `price.excel`, `textwrap`.

### `TripProductRow.supplier_names(self)`

Исходник: `orders/trip_excel.py:27`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `self.suppliers.values`, `sorted`, `supplier.letter.casefold`.

### `trip_order_xlsx(lines)`

Исходник: `orders/trip_excel.py:33`.

Объединяет одинаковые товары с одной ценой независимо от поставщика.

Статические вызовы: `TripProductRow`, `_trip_lines_xlsx`, `rows.values`, `sorted`.

### `supplier_order_xlsx(batch, supplier, lines, *, show_prices=True)`

Исходник: `orders/trip_excel.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_trip_lines_xlsx`.

### `_trip_lines_xlsx(lines, *, title, show_prices, show_suppliers=False, show_codes=False, show_total=False)`

Исходник: `orders/trip_excel.py:57`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `BytesIO`, `Decimal`, `Font`, `PatternFill`, `Workbook`, `book.close`, `book.save`, `display_game_codes`, `enumerate`, `get_column_letter`, `headers.append`, `len`, `list`, `max`, `nomenclature_product_groups`, `ord`, `output.getvalue`, `price.to_integral_value`, `safe_text`, `sheet.append`, `sheet.cell`, `sheet.merge_cells`, `sum`, `values.append`, `wrap`, `zip`.

## `orders/trip_invoice_views.py`

Сохранение отметки поставщика без изменения статусов заказов и ревизии рейса.

Импорты: `core.decorators`, `django.core.exceptions`, `django.db`, `django.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `trip_invoices`, `trips`.

### `invoice_update(request, pk, supplier_pk)`

Исходник: `orders/trip_invoice_views.py:16`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `permission_required_all`, `request.POST.get`, `set_invoice_accepted`.

## `orders/trip_invoices.py`

Отметки и защита редактирования на странице рейса; учётные сервисы их не читают.

Импорты: `django.core.exceptions`, `django.db`, `models`, `trips`.

### `_locked_batch(batch_id)`

Исходник: `orders/trip_invoices.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `ValidationError`.

### `set_invoice_accepted(*, actor, batch_id, supplier_id, accepted)`

Исходник: `orders/trip_invoices.py:21`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierTripInvoice.objects.get_or_create`, `ValidationError`, `_locked_batch`, `_require_manage`, `batch.lines.filter`, `batch.lines.filter(supplier_id=supplier_id).exists`, `flag.save`, `isinstance`, `logger.info`.

### `require_page_editable(*, batch_id, line_id, target_supplier_id=None, returning_to_m=False)`

Исходник: `orders/trip_invoices.py:38`.

Вызывается внутри транзакции HTTP-обработчика; блокировка общая с переключателем.

Статические вызовы: `SupplierOrderBatchLine.objects.get`, `ValidationError`, `_locked_batch`, `batch.invoice_flags.filter`, `batch.invoice_flags.filter(supplier_id__in=supplier_ids, accepted=True).exists`, `int`, `str`, `str(target_supplier_id or '').isdecimal`, `supplier_ids.add`.

## `orders/trip_price_views.py`

Предпросмотр и подтверждённое сохранение закупочной цены выбранной строки.

Импорты: `core.decorators`, `django.core.exceptions`, `django.db`, `django.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `trip_invoices`, `trip_prices`, `trips`.

### `_price_response(request, pk, line_pk, *, save)`

Исходник: `orders/trip_price_views.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `change_trip_price`, `logger.exception`, `preview_trip_price`, `request.POST.get`, `require_page_editable`, `transaction.atomic`.

### `preview(request, pk, line_pk)`

Исходник: `orders/trip_price_views.py:38`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_price_response`, `permission_required_all`.

### `update(request, pk, line_pk)`

Исходник: `orders/trip_price_views.py:45`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_price_response`, `permission_required_all`.

## `orders/trip_prices.py`

Корректировка закупки рейса без изменения согласованных цен покупателей.

Импорты: `arrival_models`, `decimal`, `django.core.exceptions`, `django.core.validators`, `django.db`, `django.utils`, `models`, `order_editing`, `price.services`, `trips`.

### `validated_aed(value)`

Исходник: `orders/trip_prices.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=6)`, `decimal_value`, `str`.

### `historical_rate(source)`

Исходник: `orders/trip_prices.py:23`.

Использует только сохранённые данные той же версии прайса.

Статические вызовы: `ValidationError`, `all`, `decimal_value`, `value.is_finite`.

### `allocation_unit_cost(item, line=None, *, for_supply=False, price_aed=None)`

Исходник: `orders/trip_prices.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `decimal_value`, `historical_rate`.

### `stock_purchase_rows(order, item)`

Исходник: `orders/trip_prices.py:47`.

Отдельные цены партий остаются отдельными строками складского документа.

Статические вызовы: `ValidationError`, `allocation_unit_cost`, `any`, `item.trip_allocations.all`, `sum`.

### `order_financials(order, *, overrides=None)`

Исходник: `orders/trip_prices.py:58`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.get`, `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=2)`, `ValidationError`, `allocation_unit_cost`, `decimal_value`, `item.trip_allocations.all`, `order.items.select_related`, `order.items.select_related('price_list_item__price_list').prefetch_related`, `order.operations.select_related`, `order.operations.select_related('sale').filter`, `order.operations.select_related('sale').filter(active=True).first`, `overrides.get`, `sum`.

### `trip_financials(batch)`

Исходник: `orders/trip_prices.py:91`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `batch.lines.all`, `batch.trip_orders.all`, `order_financials`, `sum`.

### `line_price_lock_reason(line, allocations=None)`

Исходник: `orders/trip_prices.py:104`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip_id=line.batch_id, arrived_at__isnull=False).exists`, `downstream_lock_reason`, `hasattr`, `line.allocations.all`.

### `_locked_context(actor, batch_id, line_id)`

Исходник: `orders/trip_prices.py:119`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().filter`, `CustomerProcurementOrder.objects.select_for_update().filter(pk__in=[row.order_item.order_id for row in allocations]).order_by`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `SupplierOrderBatchLine.objects.select_for_update`, `SupplierOrderBatchLine.objects.select_for_update().select_related`, `SupplierOrderBatchLine.objects.select_for_update().select_related('supplier', 'price_list_item__price_list').get`, `ValidationError`, `_assert_balances`, `_require_manage`, `any`, `historical_rate`, `line.allocations.select_for_update`, `line.allocations.select_for_update().select_related`, `line.allocations.select_for_update().select_related('order_item__order', 'order_item__price_list_item__price_list').order_by`, `line_price_lock_reason`, `list`.

### `_preview(batch, line, allocations, price)`

Исходник: `orders/trip_prices.py:144`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=6)`, `allocation_unit_cost`, `historical_rate`, `list`, `order_financials`, `orders.values`, `rows.append`, `str`.

### `preview_trip_price(*, actor, batch_id, line_id, revision, price_aed)`

Исходник: `orders/trip_prices.py:184`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_locked_context`, `_preview`, `_quantity`, `validated_aed`.

### `change_trip_price(*, actor, batch_id, line_id, revision, price_aed, reason='')`

Исходник: `orders/trip_prices.py:193`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_locked_context`, `_preview`, `_quantity`, `_record_trip_change`, `details.update`, `len`, `line.full_clean`, `line.save`, `str`, `str(reason or '').strip`, `timezone.now`, `validated_aed`.

## `orders/trip_views.py`

Страницы рейса, доступные заказы, таблицы поставщиков и Excel; учётные изменения делегируются сервисам.

Импорты: `arrival_models`, `arrival_views`, `catalog.product_ordering`, `catalog.supplier_exclusions`, `collections`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.urls`, `django.utils.http`, `django.utils.text`, `django.views.decorators.cache`, `django.views.decorators.http`, `forms`, `fulfillment`, `models`, `order_editing`, `partners.models`, `trip_excel`, `trip_invoices`, `trip_prices`, `trips`, `uuid`.

### `trip_empty_create(request)`

Исходник: `orders/trip_views.py:36`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `EmptyTripForm`, `create_empty_trip`, `form.add_error`, `form.is_valid`, `isinstance`, `messages.success`, `permission_required_all`, `redirect`, `render`, `require_http_methods`, `uuid4`.

### `trip_add_orders(request, pk)`

Исходник: `orders/trip_views.py:51`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `SupplierOrderBatch.objects.trips`, `TripAddOrdersForm`, `add_orders_to_trip`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `isinstance`, `messages.success`, `permission_required_all`, `redirect`, `render`, `require_http_methods`.

### `_trip_line_order_key(line)`

Исходник: `orders/trip_views.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalized_order_name`, `platform_order_key`.

### `trip_create(request)`

Исходник: `orders/trip_views.py:78`.

Декораторы: `require_POST`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `create_trip`, `isinstance`, `messages.error`, `messages.success`, `permission_required_all`, `redirect`, `request.POST.get`, `request.POST.getlist`.

### `order_trip_assign(request, pk)`

Исходник: `orders/trip_views.py:91`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `CustomerProcurementOrder.objects.select_related`, `TripAssignmentForm`, `assign_order_to_trip`, `available_trips`, `bool`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `isinstance`, `list`, `messages.success`, `order.trip.trip_orders.exclude`, `order.trip.trip_orders.exclude(status=order.Status.CREATED).exists`, `permission_required_all`, `redirect`, `render`, `require_http_methods`.

### `trip_detail(request, pk)`

Исходник: `orders/trip_views.py:118`.

Декораторы: `require_GET`; `permission_required_all(*VIEW_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Supplier.objects.all`, `TripArrival.objects.filter`, `TripArrival.objects.filter(trip=batch, arrived_at__isnull=False).exists`, `all`, `allocations.append`, `batch.invoice_flags.filter`, `batch.invoice_flags.filter(accepted=True).values_list`, `batch.lines.all`, `batch.trip_orders.all`, `bool`, `can_manage_trips`, `defaultdict`, `downstream_lock_reason`, `exclusion_keys`, `get_object_or_404`, `grouped.items`, `grouped.values`, `grouped[line.supplier].append`, `is_m_order_in_f`, `line.allocations.all`, `line.price_list_item.supplier_offers.all`, `line_price_lock_reason`, `list`, `operation_actions`, `panel_context`, `permission_required_all`, `render`, `request.user.has_perm`, `reverse`, `set`, `sorted`, `str`, `supplier.name.casefold`, `supplier_lines.sort`, `supplier_priority_state`, `trip_financials`, `trip_queryset`, `trip_queryset().trips`, `trip_supplier_chains`.

### `trip_line_update(request, pk, line_pk)`

Исходник: `orders/trip_views.py:193`.

Декораторы: `require_POST`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `change_trip_line`, `isinstance`, `json.loads`, `permission_required_all`, `request.POST.get`, `require_page_editable`, `return_line_to_m`, `transaction.atomic`.

### `trip_full_export(request, pk)`

Исходник: `orders/trip_views.py:216`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all(*VIEW_PERMISSIONS, 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `SupplierOrderBatch.objects.trips`, `batch.lines.select_related`, `batch.lines.select_related('supplier', 'cd__platform', 'cd__game_series', 'tech__brand', 'tech__product_type').order_by`, `content_disposition_header`, `get_object_or_404`, `list`, `permission_required_all`, `transaction.atomic`, `trip_order_xlsx`.

### `trip_export(request, pk, supplier_pk)`

Исходник: `orders/trip_views.py:232`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all(*VIEW_PERMISSIONS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `SupplierOrderBatch.objects.trips`, `batch.lines.filter`, `batch.lines.filter(supplier=supplier).select_related`, `batch.lines.filter(supplier=supplier).select_related('cd__platform', 'cd__game_series', 'tech__brand', 'tech__product_type').order_by`, `content_disposition_header`, `get_object_or_404`, `get_valid_filename`, `list`, `permission_required_all`, `request.user.has_perm`, `supplier_order_xlsx`.

## `orders/trips.py`

Создание рейсов, привязка прайса и распределение поставщиков/заказчиков.

Импорты: `arrival_models`, `catalog.supplier_exclusions`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`, `order_editing`, `partners.models`, `price.models`, `services`, `uuid`.

### `can_manage_trips(user)`

Исходник: `orders/trips.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `user.has_perms`.

### `_require_manage(actor)`

Исходник: `orders/trips.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `can_manage_trips`.

### `trip_queryset()`

Исходник: `orders/trips.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierOrderBatch.objects.select_related`, `SupplierOrderBatch.objects.select_related('price_list', 'created_by').prefetch_related`.

### `_batch_exclusions(batch)`

Исходник: `orders/trips.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `exclusion_keys`, `hasattr`.

### `_check_supplier_admission(batch, source, *supplier_ids)`

Исходник: `orders/trips.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_batch_exclusions`, `any`.

### `_line_for(batch, source, supplier_id, price_supplier_id, price, *, price_updated_at=None)`

Исходник: `orders/trips.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierOrderBatchLine.objects.get_or_create`, `ValidationError`, `_check_supplier_admission`, `line.save`.

### `create_trip(*, actor, order_ids, creation_key, name='', allow_empty=False)`

Исходник: `orders/trips.py:75`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().filter`, `CustomerProcurementOrder.objects.select_for_update().filter(pk__in=ids).order_by`, `CustomerProcurementOrderItem.objects.select_for_update`, `CustomerProcurementOrderItem.objects.select_for_update().select_related`, `CustomerProcurementOrderItem.objects.select_for_update().select_related('price_list_item__cd', 'price_list_item__tech', 'cd', 'tech').filter`, `CustomerProcurementOrderItem.objects.select_for_update().select_related('price_list_item__cd', 'price_list_item__tech', 'cd', 'tech').filter(order_id__in=ids).order_by`, `SupplierOrderBatch.objects.create`, `SupplierOrderBatch.objects.filter`, `SupplierOrderBatch.objects.filter(creation_key=key).first`, `SupplierTripAllocation.objects.create`, `SupplierTripChange.objects.create`, `UUID`, `ValidationError`, `_line_for`, `_require_manage`, `any`, `apply_m_to_f_rule`, `batch.refresh_from_db`, `batch.source_orders.set`, `existing.changes.filter`, `existing.changes.filter(revision=0, details__empty=True).exists`, `existing.source_orders.values_list`, `int`, `len`, `line.save`, `list`, `order.save`, `require_untransferred_order`, `set`, `sorted`, `str`, `str(name or '').strip`.

### `create_empty_trip(*, actor, creation_key, name='')`

Исходник: `orders/trips.py:141`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `create_trip`.

### `_assert_balances(batch)`

Исходник: `orders/trips.py:145`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrderItem.objects.filter`, `ValidationError`, `batch.lines.prefetch_related`, `batch.lines.prefetch_related('allocations').all`, `line.allocations.all`, `quantities.get`, `quantities.pop`, `sum`.

### `available_trips(*, price_list_id, exclude_id=None)`

Исходник: `orders/trips.py:161`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Q`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().filter`, `SupplierOrderBatch.objects.trips().filter(Q(price_list_id=price_list_id) | Q(price_list__isnull=True)).exclude`, `SupplierOrderBatch.objects.trips().filter(Q(price_list_id=price_list_id) | Q(price_list__isnull=True)).exclude(pk=exclude_id).exclude`, `SupplierOrderBatch.objects.trips().filter(Q(price_list_id=price_list_id) | Q(price_list__isnull=True)).exclude(pk=exclude_id).exclude(pk__in=TripArrival.objects.filter(arrived_at__isnull=False).values('trip_id')).exclude`, `SupplierOrderBatch.objects.trips().filter(Q(price_list_id=price_list_id) | Q(price_list__isnull=True)).exclude(pk=exclude_id).exclude(pk__in=TripArrival.objects.filter(arrived_at__isnull=False).values('trip_id')).exclude(trip_orders__status__in=(CustomerProcurementOrder.Status.CONFIRMED, CustomerProcurementOrder.Status.RECEIVING, CustomerProcurementOrder.Status.COMPLETED)).order_by`, `TripArrival.objects.filter`, `TripArrival.objects.filter(arrived_at__isnull=False).values`.

### `_require_editable_trip(batch)`

Исходник: `orders/trips.py:174`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TripArrival.objects.filter`, `TripArrival.objects.filter(trip=batch, arrived_at__isnull=False).exists`, `ValidationError`, `_assert_balances`, `any`, `batch.source_orders.values_list`, `batch.trip_orders.select_for_update`, `batch.trip_orders.select_for_update().order_by`, `list`, `require_untransferred_order`, `set`.

### `_record_trip_change(batch, actor, description, details)`

Исходник: `orders/trips.py:188`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierTripChange.objects.create`, `batch.save`.

### `assign_order_to_trip(*, actor, order_id, target_batch_id, target_revision, source_batch_id=None, source_revision=None)`

Исходник: `orders/trips.py:196`.

Декораторы: `transaction.atomic`.

Перенести весь заказ или добавить свободный, сохранив снимки и распределение.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().get`, `ProcurementSupplierOffer.objects.filter`, `ProcurementSupplierOffer.objects.filter(price_list_item=item.price_list_item, supplier_id=supplier_id, price_aed=item.supplier_price_aed_snapshot).exists`, `Supplier.objects.filter`, `Supplier.objects.filter(letter='F').first`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().filter`, `SupplierOrderBatch.objects.trips().select_for_update().filter(pk__in=ids).order_by`, `SupplierTripAllocation.objects.create`, `SupplierTripAllocation.objects.select_for_update`, `SupplierTripAllocation.objects.select_for_update().select_related`, `SupplierTripAllocation.objects.select_for_update().select_related('line__price_list_item__cd', 'line__price_list_item__tech').filter`, `SupplierTripAllocation.objects.select_for_update().select_related('line__price_list_item__cd', 'line__price_list_item__tech').filter(line__batch=source, order_item__order=order).order_by`, `ValidationError`, `_assert_balances`, `_batch_exclusions`, `_line_for`, `_quantity`, `_record_trip_change`, `_require_editable_trip`, `_require_manage`, `allocation.save`, `any`, `batches.get`, `int`, `line.allocations.exists`, `line.delete`, `line.save`, `list`, `new_line.save`, `order.items.select_for_update`, `order.items.select_for_update().select_related`, `order.items.select_for_update().select_related('price_list_item__cd', 'price_list_item__tech', 'selected_supplier', 'cd', 'tech').order_by`, `order.save`, `set`, `source.source_orders.remove`, `source_lines.setdefault`, `source_lines.values`, `str`, `target.save`, `target.source_orders.add`, `transfers.append`.

### `create_stock_order_for_trip(*, actor, batch_id, revision, price_list_id, recipient, comment, lines)`

Исходник: `orders/trips.py:315`.

Декораторы: `transaction.atomic`.

Заказ и распределения рейса сохраняются вместе; при отказе свободного заказа не остаётся.

Статические вызовы: `PermissionDenied`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `ValidationError`, `_quantity`, `_require_editable_trip`, `_require_manage`, `actor.has_perm`, `assign_order_to_trip`, `create_customer_procurement_order`.

### `add_orders_to_trip(*, actor, batch_id, order_ids, revision)`

Исходник: `orders/trips.py:337`.

Декораторы: `transaction.atomic`.

Добавить выбранные свободные заказы одной атомарной операцией.

Статические вызовы: `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `ValidationError`, `_quantity`, `_require_manage`, `assign_order_to_trip`, `int`, `sorted`.

### `delete_empty_trip(*, actor, batch_id, revision, archive_batch_id)`

Исходник: `orders/trips.py:359`.

Декораторы: `transaction.atomic`.

Удалить пустой рейс, сохранив его историю в рейсе назначения.

Статические вызовы: `SupplierOrderBatch.objects.select_for_update`, `SupplierOrderBatch.objects.select_for_update().filter`, `SupplierOrderBatch.objects.select_for_update().filter(pk__in=(batch_id, archive_batch_id), price_list__isnull=False).order_by`, `SupplierTripAllocation.objects.filter`, `SupplierTripAllocation.objects.filter(line__batch=batch).exists`, `ValidationError`, `_quantity`, `_record_trip_change`, `_require_manage`, `batch.changes.all`, `batch.changes.all().delete`, `batch.created_at.isoformat`, `batch.delete`, `batch.lines.all`, `batch.lines.all().delete`, `batch.lines.filter`, `batch.lines.filter(quantity__gt=0).exists`, `batch.source_orders.exists`, `batch.trip_orders.exists`, `change.created_at.isoformat`, `len`, `str`.

### `_record_customer_changes(actor, changes, batch)`

Исходник: `orders/trips.py:390`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.get`, `OrderAdjustment.objects.create`, `OrderAdjustmentChange.objects.create`, `_save_totals`, `changes.items`, `list`, `order.items.all`.

### `trip_supplier_chains(lines, *, excluded=None)`

Исходник: `orders/trips.py:404`.

Предложения, фактические получатели и допустимый получатель M по чужой цене.

Статические вызовы: `Supplier.objects.filter`, `Supplier.objects.filter(letter='M').values_list`, `chains.setdefault`, `exclusion_keys`, `line.price_list_item.supplier_offers.all`, `list`, `set`, `suppliers.add`, `suppliers.update`.

### `supplier_priority_state(supplier_id, priorities)`

Исходник: `orders/trips.py:422`.

При равном максимуме не выбирает последнего по букве, имени или ID.

Статические вызовы: `len`, `max`, `priorities.items`, `priorities.values`.

### `_automatic_reduction(allocations, quantity)`

Исходник: `orders/trips.py:432`.

Сохраняет доли других поставщиков; нуль и одного получателя распределяет без выбора.

Статические вызовы: `len`.

### `change_trip_line(*, actor, batch_id, line_id, revision, quantity, action, target_supplier_id=None, price_supplier_id=None, distribution=None, _allow_priority_transfer=False, _exclusions=None)`

Исходник: `orders/trips.py:444`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_for_update`, `CustomerProcurementOrder.objects.select_for_update().filter`, `CustomerProcurementOrder.objects.select_for_update().filter(trip=batch).order_by`, `ProcurementSupplierOffer.objects.get`, `Supplier.objects.get`, `Supplier.objects.select_for_update`, `Supplier.objects.select_for_update().filter`, `Supplier.objects.select_for_update().filter(pk__in=chain).values_list`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `SupplierOrderBatchLine.objects.select_for_update`, `SupplierOrderBatchLine.objects.select_for_update().select_related`, `SupplierOrderBatchLine.objects.select_for_update().select_related('price_list_item__cd', 'price_list_item__tech').get`, `SupplierTripAllocation.objects.get_or_create`, `SupplierTripChange.objects.create`, `ValidationError`, `_assert_balances`, `_automatic_reduction`, `_batch_exclusions`, `_check_supplier_admission`, `_line_for`, `_quantity`, `_record_customer_changes`, `_require_manage`, `allocation.save`, `batch.lines.filter`, `batch.lines.filter(price_list_item_id=line.price_list_item_id).select_related`, `batch.lines.filter(price_list_item_id=line.price_list_item_id).select_related('price_list_item').prefetch_related`, `batch.save`, `changes.setdefault`, `changes.setdefault(item.order_id, []).append`, `customer_details.append`, `destination.save`, `detail.update`, `dict`, `getattr`, `int`, `isinstance`, `item.full_clean`, `item.save`, `line.allocations.select_for_update`, `line.allocations.select_for_update().select_related`, `line.allocations.select_for_update().select_related('order_item__order').order_by`, `line.save`, `list`, `max`, `min`, `require_untransferred_order`, `reversed`, `set`, `setattr`, `str`, `supplier_priority_state`, `target.save`, `trip_supplier_chains`.

### `is_m_order_in_f(line)`

Исходник: `orders/trips.py:585`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `apply_m_to_f_rule(*, actor, batch_id)`

Исходник: `orders/trips.py:591`.

Декораторы: `transaction.atomic`.

Однократно применить правило к созданному рейсу; повтор без строк M ничего не меняет.

Статические вызовы: `Supplier.objects.filter`, `SupplierOrderBatch.objects.trips`, `SupplierOrderBatch.objects.trips().select_for_update`, `SupplierOrderBatch.objects.trips().select_for_update().get`, `SupplierTripChange.objects.create`, `ValidationError`, `_batch_exclusions`, `_require_manage`, `batch.lines.filter`, `batch.lines.filter(supplier=suppliers['M'], quantity__gt=0).order_by`, `change_trip_line`, `len`, `list`, `sum`.

### `return_line_to_m(*, actor, batch_id, line_id, revision)`

Исходник: `orders/trips.py:628`.

Декораторы: `transaction.atomic`.

Вернуть всю положительную строку F с ценой M, сохранив распределение заказчиков.

Статические вызовы: `SupplierOrderBatchLine.objects.select_related`, `SupplierOrderBatchLine.objects.select_related('supplier', 'price_supplier').get`, `ValidationError`, `_require_manage`, `change_trip_line`, `is_m_order_in_f`.

## `orders/urls.py`

Именованные HTTP-маршруты приложения импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `django.urls`.

## `orders/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю импортных заказов и рейсов.

План закупки, фактическое поступление и проведённые Sale/Supply учитываются раздельно.

Импорты: `collections`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.http`, `django.shortcuts`, `django.urls`, `django.utils.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `forms`, `fulfillment`, `models`, `order_editing`, `order_excel`, `order_supplier_excel`, `partners.customers`, `price.excel`, `price.models`, `services`, `trip_prices`, `trip_views`, `trips`, `uuid`.

### `_require_stock_prices(user, purpose)`

Исходник: `orders/views.py:39`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `user.has_perm`.

### `_parse_item_lines(post, *, id_field)`

Исходник: `orders/views.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `len`, `post.getlist`, `range`.

### `_order_queryset()`

Исходник: `orders/views.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.select_related`, `CustomerProcurementOrder.objects.select_related('price_list', 'payment_warehouse', 'created_by', 'trip', 'supply__warehouse').prefetch_related`.

### `order_list(request)`

Исходник: `orders/views.py:73`.

Декораторы: `require_GET`; `permission_required_any('orders.view_orders')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CustomerProcurementOrder.objects.only`, `Prefetch`, `SupplierOrderBatch.objects.select_related`, `SupplierOrderBatch.objects.select_related('created_by').prefetch_related`, `_order_queryset`, `can_manage_trips`, `list`, `operation_actions`, `orders.filter`, `permission_required_any`, `render`, `request.user.has_perm`, `str`, `uuid4`.

### `order_upload(request)`

Исходник: `orders/views.py:106`.

Декораторы: `permission_required_any('orders.create_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementOrderUploadForm`, `_require_stock_prices`, `form.add_error`, `form.is_valid`, `import_procurement_order_files`, `permission_required_any`, `redirect`, `render`, `request.user.has_perm`.

### `order_export(request, pk)`

Исходник: `orders/views.py:133`.

Декораторы: `never_cache`; `require_GET`; `permission_required_any('orders.view_order_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `_require_stock_prices`, `content_disposition_header`, `customer_filename`, `get_object_or_404`, `list`, `order.items.select_related`, `order.items.select_related('cd__platform', 'cd__game_series', 'tech__brand', 'tech__product_type').order_by`, `order_xlsx`, `permission_required_any`, `transaction.atomic`.

### `order_suppliers_export(request, pk)`

Исходник: `orders/views.py:150`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all('orders.view_order_detail', 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `HttpResponse`, `Prefetch`, `SupplierTripAllocation.objects.filter`, `SupplierTripAllocation.objects.filter(line__batch_id=order.trip_id).select_related`, `SupplierTripAllocation.objects.filter(line__batch_id=order.trip_id).select_related('line__supplier').order_by`, `build_order_supplier_rows`, `content_disposition_header`, `customer_filename`, `get_object_or_404`, `items.prefetch_related`, `list`, `messages.error`, `order.items.select_related`, `order.items.select_related('selected_supplier', 'cd__platform', 'cd__game_series', 'tech__brand', 'tech__product_type').order_by`, `order_suppliers_xlsx`, `permission_required_all`, `redirect`, `request.user.has_perm`, `transaction.atomic`.

### `order_preview(request)`

Исходник: `orders/views.py:178`.

Декораторы: `permission_required_any('orders.create_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ProcurementPriceListItem.objects.select_related`, `ProcurementPriceListItem.objects.select_related('cd', 'tech').filter`, `SupplierOrderBatch.objects.trips`, `_require_stock_prices`, `can_manage_trips`, `create_customer_procurement_order`, `create_stock_order_for_trip`, `draft.get`, `draft.items`, `get_object_or_404`, `items.get`, `messages.error`, `messages.success`, `permission_required_any`, `preview_rows.append`, `redirect`, `render`, `request.session.get`, `request.session.pop`, `reverse`.

### `order_detail(request, pk)`

Исходник: `orders/views.py:233`.

Декораторы: `require_GET`; `permission_required_any('orders.view_order_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_order_queryset`, `_require_stock_prices`, `available`, `can_manage_trips`, `downstream_lock_reason`, `get_object_or_404`, `order.operations.select_related`, `order.trip.trip_orders.exclude`, `order.trip.trip_orders.exclude(status=order.Status.CREATED).exists`, `order_financials`, `permission_required_any`, `render`, `request.user.has_perm`, `require_permissions`.

### `order_edit(request, pk)`

Исходник: `orders/views.py:295`.

Декораторы: `permission_required_any('orders.edit_created_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementOrderHeaderForm`, `_order_queryset`, `_parse_item_lines`, `_require_stock_prices`, `edit_created_order`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `list`, `messages.error`, `messages.success`, `order.items.all`, `order.price_list.items.all`, `permission_required_any`, `redirect`, `render`, `str`.

### `order_confirm(request, pk)`

Исходник: `orders/views.py:331`.

Декораторы: `require_POST`; `permission_required_any('orders.confirm_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `_require_stock_prices`, `advance_order_status`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `request.user.has_perm`.

### `order_start_receiving(request, pk)`

Исходник: `orders/views.py:353`.

Декораторы: `require_POST`; `permission_required_any('orders.start_receiving')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_require_stock_prices`, `advance_order_status`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `order_adjust(request, pk)`

Исходник: `orders/views.py:368`.

Декораторы: `permission_required_any('orders.edit_receiving_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReceivingAdjustmentForm`, `_order_queryset`, `_parse_item_lines`, `_require_stock_prices`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `reduce_receiving_order`, `render`, `request.user.has_perm`.

### `order_complete(request, pk)`

Исходник: `orders/views.py:393`.

Декораторы: `require_POST`; `permission_required_any('orders.complete_order')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `_require_stock_prices`, `advance_order_status`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `request.user.has_perm`.

### `supplier_batch_create(request)`

Исходник: `orders/views.py:419`.

Декораторы: `require_POST`; `permission_required_all('orders.generate_supplier_orders', 'partners.view_supplier_details', 'orders.edit_created_order', 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `permission_required_all`, `trip_create`.

### `supplier_batch_detail(request, pk)`

Исходник: `orders/views.py:426`.

Декораторы: `require_GET`; `permission_required_all('orders.generate_supplier_orders', 'partners.view_supplier_details')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierOrderBatch.objects.select_related`, `SupplierOrderBatch.objects.select_related('created_by').prefetch_related`, `batch.lines.all`, `defaultdict`, `get_object_or_404`, `grouped.items`, `grouped[line.supplier].append`, `permission_required_all`, `render`, `request.user.has_perm`.

## `partners/admin.py`

Регистрация моделей и разрешённых действий в Django Admin контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `django.contrib`, `forms`, `models`.

### `SupplierDetailAdminMixin._can_see_details(self, request)`

Исходник: `partners/admin.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`.

### `SupplierDetailAdminMixin.has_module_permission(self, request)`

Исходник: `partners/admin.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._can_see_details`, `super`, `super().has_module_permission`.

### `SupplierDetailAdminMixin.has_view_permission(self, request, obj=None)`

Исходник: `partners/admin.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._can_see_details`, `super`, `super().has_view_permission`.

### `SupplierDetailAdminMixin.has_add_permission(self, request)`

Исходник: `partners/admin.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._can_see_details`, `super`, `super().has_add_permission`.

### `SupplierDetailAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `partners/admin.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._can_see_details`, `super`, `super().has_change_permission`.

### `SupplierDetailAdminMixin.has_delete_permission(self, request, obj=None)`

Исходник: `partners/admin.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._can_see_details`, `super`, `super().has_delete_permission`.

### `SupplierAdmin.save_model(self, request, obj, form, change)`

Исходник: `partners/admin.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `Supplier.objects.filter`, `Supplier.objects.filter(pk=obj.pk).values_list`, `Supplier.objects.filter(pk=obj.pk).values_list('priority', flat=True).first`, `logger.info`, `super`, `super().save_model`.

## `partners/apps.py`

Конфигурация приложения и его регистрация в Django контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `django.apps`.

## `partners/customers.py`

Общий явный выбор заказчика без поиска контрагента по имени или телефону.

Импорты: `django`, `django.core.exceptions`, `models`.

### `resolve_customer(*, partner_id=None, partner_name='', required=False, allow_archived=False)`

Исходник: `partners/customers.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.get`, `ValidationError`, `len`, `str`, `str(partner_name or '').strip`.

### `customer_filename(name)`

Исходник: `partners/customers.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `re.sub`, `re.sub('[<>:"/\\\\|?*\\x00-\\x1f]', '_', str(name or '')).strip`, `str`.

### `CustomerSelectionForm.__init__(self, *args, allow_archived_initial=False, **kwargs)`

Исходник: `partners/customers.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(is_archived=False).only`, `Partner.objects.filter(pk=initial, is_archived=True).first`, `self.initial.get`, `str`, `str(initial).isdecimal`, `super`, `super().__init__`.

### `CustomerSelectionForm.clean(self)`

Исходник: `partners/customers.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `data.get('custom_partner_name', '').strip`, `int`, `self.add_error`, `super`, `super().clean`.

### `PartnerChoiceField.label_from_instance(self, partner)`

Исходник: `partners/customers.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `PartnerMultipleChoiceField.label_from_instance(self, partner)`

Исходник: `partners/customers.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `partners/excel.py`

Подписанные сведения о заказчике внутри прежнего технического листа прайса.

Импорты: `customers`, `django.core`, `django.core.exceptions`.

### `customer_metadata(*, warehouse_id, partner_id=None, partner_name='')`

Исходник: `partners/excel.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `resolve_customer`, `signing.dumps`.

### `read_customer_metadata(values)`

Исходник: `partners/excel.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `ValueError`, `isinstance`, `payload.get`, `resolve_customer`, `signing.loads`, `str`, `values.get`.

## `partners/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `django`, `models`, `telegram`.

### `PartnerForm.clean_telegram(self)`

Исходник: `partners/forms.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize_telegram`, `self.cleaned_data.get`.

### `PartnerForm.__init__(self, *args, can_create_platform=False, **kwargs)`

Исходник: `partners/forms.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.fields.pop`, `self.order_fields`, `super`, `super().__init__`.

### `PartnerForm.clean(self)`

Исходник: `partners/forms.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `self.add_error`, `super`, `super().clean`.

## `partners/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `creditors.models`, `django.core.exceptions`, `django.core.validators`, `django.db`, `telegram`, `validators`.

### `Supplier.__str__(self)`

Исходник: `partners/models.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Supplier.safe_label(self)`

Исходник: `partners/models.py:37`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SalesPlatform.__str__(self)`

Исходник: `partners/models.py:58`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Partner.__str__(self)`

Исходник: `partners/models.py:86`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Partner.display_name(self)`

Исходник: `partners/models.py:90`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `str(self.contact_person or '').strip`.

### `Partner.telegram_chat_url(self)`

Исходник: `partners/models.py:95`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `telegram_chat_url`.

### `Partner.clean(self)`

Исходник: `partners/models.py:99`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._normalize_telegram`, `super`, `super().clean`.

### `Partner._normalize_telegram(self)`

Исходник: `partners/models.py:103`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `normalize_telegram`.

### `Partner.save(self, *args, **kwargs)`

Исходник: `partners/models.py:111`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Creditor.objects.create`, `ValidationError`, `self._normalize_telegram`, `str`, `str(self.name or '').strip`, `super`, `super().save`, `type`, `type(self).objects.filter`, `type(self).objects.filter(pk=self.pk).values_list`, `type(self).objects.filter(pk=self.pk).values_list('creditor_id', flat=True).first`, `uuid.uuid4`.

### `Partner.delete(self, *args, **kwargs)`

Исходник: `partners/models.py:125`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

## `partners/partner_views.py`

Справочник партнёров: контакты и финансовые сведения проверяются отдельно.

Импорты: `django`, `django.contrib`, `django.contrib.auth.decorators`, `django.core.exceptions`, `django.db`, `django.shortcuts`, `forms`, `models`.

### `partner_list(request)`

Исходник: `partners/partner_views.py:16`.

Декораторы: `permission_required('partners.view_partner', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.select_related`, `permission_required`, `render`, `request.user.has_perm`.

### `partner_detail(request, pk)`

Исходник: `partners/partner_views.py:22`.

Декораторы: `permission_required('partners.view_partner', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.select_related`, `get_object_or_404`, `permission_required`, `render`, `request.user.has_perm`.

### `partner_create(request)`

Исходник: `partners/partner_views.py:30`.

Декораторы: `permission_required('partners.add_partner', raise_exception=True)`; `permission_required('partners.view_partner_contacts', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_edit`, `permission_required`.

### `partner_edit(request, pk)`

Исходник: `partners/partner_views.py:36`.

Декораторы: `permission_required('partners.change_partner', raise_exception=True)`; `permission_required('partners.view_partner_contacts', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_edit`, `permission_required`.

### `_edit(request, pk=None)`

Исходник: `partners/partner_views.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(creation_key=key).first`, `PartnerForm`, `PermissionDenied`, `SalesPlatformForm`, `all`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `form.save`, `forms.BooleanField`, `forms.BooleanField(required=False).clean`, `get_object_or_404`, `getattr`, `logger.info`, `messages.success`, `platform_form.is_valid`, `platform_form.save`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `transaction.atomic`.

## `partners/platform_views.py`

Создание площадки из раздела реализации без складских и денежных операций.

Импорты: `django.contrib`, `django.contrib.auth.decorators`, `django.db`, `django.shortcuts`, `forms`.

### `platform_create(request)`

Исходник: `partners/platform_views.py:13`.

Декораторы: `permission_required('partners.add_salesplatform', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SalesPlatformForm`, `any`, `form.is_valid`, `form.save`, `logger.info`, `messages.success`, `permission_required`, `redirect`, `render`, `request.user.has_perm`, `transaction.atomic`.

## `partners/telegram.py`

Нормализация контакта и ссылка на чат в браузерном клиенте Telegram.

Импорты: `django.core.exceptions`.

### `normalize_telegram(value)`

Исходник: `partners/telegram.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `link.group`, `re.fullmatch`, `str`, `str(value or '').strip`, `value.removeprefix`.

### `telegram_chat_url(value)`

Исходник: `partners/telegram.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `normalize_telegram`.

## `partners/urls.py`

Именованные HTTP-маршруты приложения контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `django.urls`.

## `partners/validators.py`

Валидаторы реквизитов контрагентов; клиентская маска не заменяет эти проверки.

Импорты: `django.core.validators`.

## `partners/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю контрагентов.

Partner, Supplier и SalesPlatform имеют разные роли; имя не заменяет финансовую FK-связь.

Импорты: `django.contrib`, `django.contrib.auth.decorators`, `django.shortcuts`, `forms`, `models`.

### `supplier_list(request)`

Исходник: `partners/views.py:16`.

Декораторы: `permission_required('partners.view_supplier', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Supplier.objects.values`, `list`, `permission_required`, `render`, `request.user.has_perm`.

### `supplier_create(request)`

Исходник: `partners/views.py:29`.

Декораторы: `permission_required('partners.add_supplier', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplierForm`, `form.is_valid`, `form.save`, `logger.info`, `messages.success`, `permission_required`, `redirect`, `render`.

### `supplier_update(request, pk)`

Исходник: `partners/views.py:44`.

Декораторы: `permission_required('partners.change_supplier', raise_exception=True)`; `permission_required('partners.view_supplier_details', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `SupplierForm`, `form.is_valid`, `form.save`, `get_object_or_404`, `logger.info`, `messages.success`, `permission_required`, `redirect`, `render`.

## `price/admin.py`

Регистрация моделей и разрешённых действий в Django Admin прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `django.contrib`, `models`.

### `_can_view_supplier_snapshots(request)`

Исходник: `price/admin.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`.

### `SupplierSnapshotAdminMixin.has_module_permission(self, request)`

Исходник: `price/admin.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_module_permission`.

### `SupplierSnapshotAdminMixin.has_view_permission(self, request, obj=None)`

Исходник: `price/admin.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_view_permission`.

### `SupplierSnapshotAdminMixin.has_change_permission(self, request, obj=None)`

Исходник: `price/admin.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().has_change_permission`.

### `PriceDocumentSettingsAdmin.has_add_permission(self, request)`

Исходник: `price/admin.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PriceDocumentSettings.objects.exists`, `super`, `super().has_add_permission`.

### `PriceDocumentSettingsAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `price/admin.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItemInline.has_add_permission(self, request, obj=None)`

Исходник: `price/admin.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListAdmin.get_inline_instances(self, request, obj=None)`

Исходник: `price/admin.py:61`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_can_view_supplier_snapshots`, `super`, `super().get_inline_instances`.

### `ProcurementPriceListAdmin.has_add_permission(self, request)`

Исходник: `price/admin.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `price/admin.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItemAdmin.has_add_permission(self, request)`

Исходник: `price/admin.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItemAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `price/admin.py:86`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `price/apps.py`

Конфигурация приложения и его регистрация в Django прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `django.apps`.

## `price/excel.py`

Генерация и проверяемый импорт XLSX. Служебная разметка/подписи, ведущие нули и разные правила нулевых строк обязательны.

Импорты: `catalog.models`, `catalog.newness`, `catalog.nomenclature_grouping`, `catalog.product_ordering`, `copy`, `core.excel_layout`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `io`, `models`, `openpyxl`, `openpyxl.cell.cell`, `openpyxl.drawing.image`, `openpyxl.styles`, `openpyxl.utils`, `openpyxl.worksheet.datavalidation`, `partners.excel`, `partners.models`, `pathlib`, `pricing.models`, `textwrap`, `warehouse.models`.

### `safe_text(value)`

Исходник: `price/excel.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ILLEGAL_CHARACTERS_RE.sub`, `result.startswith`, `str`.

### `_base_workbook(*, title, subtitle, columns, settings=None)`

Исходник: `price/excel.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' · '.join`, `Alignment`, `ExcelImage`, `Font`, `PatternFill`, `PriceDocumentSettings.get_solo`, `Workbook`, `filter`, `get_column_letter`, `int`, `max`, `min`, `safe_text`, `sheet.add_image`, `sheet.merge_cells`, `timezone.localtime`, `timezone.localtime().strftime`.

### `_style_table(sheet, headers, *, editable_columns=(), editable_end_row=None, header_row=HEADER_ROW)`

Исходник: `price/excel.py:99`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `Border`, `Font`, `PatternFill`, `Protection`, `Side`, `enumerate`, `get_column_letter`, `len`, `range`, `sheet.cell`, `sheet.iter_rows`.

### `_meta_sheet(workbook, *, document_type, values, rows=())`

Исходник: `price/excel.py:128`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enumerate`, `len`, `meta.cell`, `pairs.items`, `str`, `workbook.create_sheet`.

### `_bytes(workbook)`

Исходник: `price/excel.py:146`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BytesIO`, `output.getvalue`, `workbook.close`, `workbook.save`.

### `_norm(value)`

Исходник: `price/excel.py:153`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `str`, `str(value or '').casefold`, `str(value or '').casefold().replace`, `str(value or '').casefold().replace('ё', 'е').split`.

### `_tech_rows(warehouse, *, price_field)`

Исходник: `price/excel.py:157`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TechWarehouseStock.objects.filter`, `TechWarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0, tech__is_archived=False).select_related`, `getattr`, `groups.append`, `groups[-1][1].append`, `rows.append`, `rows.sort`, `tech_price_order`.

### `_cd_rows(warehouse, *, price_field)`

Исходник: `price/excel.py:178`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CDWarehouseStock.objects.filter`, `CDWarehouseStock.objects.filter(warehouse=warehouse, quantity__gt=0, cd__is_archived=False).select_related`, `_norm`, `entries.append`, `entries.sort`, `getattr`, `groups.append`, `groups[-1][1].append`, `platform_order_key`.

### `_warehouse_price_groups(warehouse, *, price_field)`

Исходник: `price/excel.py:200`.

Единая структура для розничного и оптового прайса: Tech перед CD.

Статические вызовы: `_cd_rows`, `_tech_rows`.

### `_group_fill(title)`

Исходник: `price/excel.py:221`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SECTION_FILLS.items`, `title.startswith`.

### `_style_group_rows(sheet, rows, *, columns)`

Исходник: `price/excel.py:228`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Border`, `Font`, `PatternFill`, `Protection`, `Side`, `_group_fill`, `range`, `sheet.cell`, `str`.

### `generate_retail_price_xlsx(*, warehouse_id, actor)`

Исходник: `price/excel.py:242`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Font`, `ValidationError`, `Warehouse.objects.get`, `_base_workbook`, `_bytes`, `_style_group_rows`, `_style_table`, `_warehouse_price_groups`, `group_rows.append`, `logger.info`, `safe_text`, `sheet.cell`.

### `generate_wholesale_price_xlsx(*, warehouse_id, actor, partner_id=None, partner_name='')`

Исходник: `price/excel.py:275`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `DataValidation`, `PatternFill`, `ValidationError`, `Warehouse.objects.get`, `_base_workbook`, `_bytes`, `_meta_sheet`, `_style_group_rows`, `_style_table`, `_warehouse_price_groups`, `customer_metadata`, `customer_product_name`, `group_rows.append`, `len`, `logger.info`, `max`, `metadata.append`, `new_product_rows.append`, `product_rows.append`, `range`, `safe_text`, `sheet.add_data_validation`, `sheet.cell`, `timezone.now`, `timezone.now().isoformat`, `validation.add`.

### `_supplier_text_height(value, *, width, minimum=28, line_height=16)`

Исходник: `price/excel.py:340`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `max`, `str`, `str(value or '').split`, `sum`, `wrap`.

### `_style_supplier_template(sheet, *, group_rows, product_kind=None)`

Исходник: `price/excel.py:348`.

Показываем название, CUSA/PPSA и цену, сохраняя служебные колонки.

Статические вызовы: `Alignment`, `Border`, `Font`, `PatternFill`, `Protection`, `Side`, `_group_fill`, `_supplier_text_height`, `max`, `next`, `range`, `sheet.cell`, `sheet.merge_cells`.

### `generate_supplier_template(*, actor, product_kind=None, supplier_id=None)`

Исходник: `price/excel.py:408`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().filter`, `CD.objects.active().filter(exclude_from_supplier_template=False).select_related`, `Tech.objects.active`, `Tech.objects.active().filter`, `Tech.objects.active().filter(exclude_from_supplier_template=False).select_related`, `ValidationError`, `Workbook`, `_bytes`, `_meta_sheet`, `_style_supplier_template`, `_style_table`, `dict`, `enumerate`, `kind.upper`, `len`, `logger.info`, `metadata.append`, `model.objects.filter`, `model.objects.filter(supplier_id=supplier_id, price__gt=0).values_list`, `nomenclature_product_groups`, `prices[kind].get`, `safe_text`, `sheet.cell`, `timezone.now`, `timezone.now().isoformat`.

### `generate_procurement_customer_xlsx(*, price_list_id, actor, product_kind=None)`

Исходник: `price/excel.py:465`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `DataValidation`, `PatternFill`, `ProcurementPriceList.objects.prefetch_related`, `ProcurementPriceList.objects.prefetch_related('items').get`, `ValidationError`, `_base_workbook`, `_bytes`, `_meta_sheet`, `_style_group_rows`, `_style_table`, `copy`, `customer_product_name`, `enumerate`, `group_rows.append`, `len`, `logger.info`, `max`, `metadata.append`, `new_product_rows.append`, `nomenclature_product_groups`, `price_list.items.select_related`, `product_rows.append`, `range`, `safe_text`, `sheet.add_data_validation`, `sheet.cell`, `sheet.merge_cells`, `timezone.now`, `timezone.now().isoformat`, `validation.add`, `wrapped_text_height`, `{'cd': ' · Диски', 'tech': ' · Техника'}.get`.

### `generate_procurement_stock_xlsx(*, price_list_id, actor)`

Исходник: `price/excel.py:588`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `DataValidation`, `ProcurementPriceList.objects.get`, `Sum`, `ValidationError`, `_base_workbook`, `_bytes`, `_meta_sheet`, `_style_group_rows`, `_style_table`, `dict`, `enumerate`, `group_rows.append`, `items.values`, `len`, `logger.info`, `max`, `metadata.append`, `model.objects.filter`, `model.objects.filter(**{f'{field}__in': product_ids}).values`, `model.objects.filter(**{f'{field}__in': product_ids}).values(field).annotate`, `model.objects.filter(**{f'{field}__in': product_ids}).values(field).annotate(total=Sum('quantity')).values_list`, `nomenclature_product_groups`, `price_list.items.select_related`, `product_rows.append`, `safe_text`, `sheet.add_data_validation`, `sheet.cell`, `sheet.merge_cells`, `stock_quantities[kind].get`, `str`, `timezone.now`, `timezone.now().isoformat`, `validation.add`, `wrap`, `wrapped_text_height`.

### `import_stock_procurement_order_xlsx(upload)`

Исходник: `price/excel.py:677`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementPriceList.objects.prefetch_related`, `ProcurementPriceList.objects.prefetch_related('items').get`, `ValidationError`, `_load_uploaded_workbook`, `_quantity`, `_require_headers`, `int`, `items.get`, `lines.append`, `price_list.items.all`, `range`, `safe_text`, `seen.add`, `seen_rows.add`, `set`, `sheet.cell`, `str`, `tuple`, `values.get`, `workbook.close`.

### `_load_uploaded_workbook(upload, expected_type)`

Исходник: `price/excel.py:728`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `Path(filename).suffix.lower`, `ValidationError`, `getattr`, `load_workbook`, `meta.cell`, `str`, `technical_rows.append`, `values.get`, `workbook.close`.

### `_require_headers(sheet, expected, *, header_row=HEADER_ROW)`

Исходник: `price/excel.py:765`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `len`, `range`, `sheet.cell`, `tuple`.

### `_quantity(value, *, excel_row)`

Исходник: `price/excel.py:771`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `int`, `isinstance`, `number.to_integral_value`, `str`.

### `import_wholesale_price_to_sale(upload, *, with_customer=False)`

Исходник: `price/excel.py:785`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().filter`, `CD.objects.active().filter(pk=product_id).first`, `CDWarehouseStock.objects.filter`, `CDWarehouseStock.objects.filter(warehouse=warehouse, cd_id=product_id).first`, `Tech.objects.active`, `Tech.objects.active().filter`, `Tech.objects.active().filter(pk=product_id).first`, `TechWarehouseStock.objects.filter`, `TechWarehouseStock.objects.filter(warehouse=warehouse, tech_id=product_id).first`, `ValidationError`, `Warehouse.objects.get`, `_load_uploaded_workbook`, `_quantity`, `_require_headers`, `int`, `kind.upper`, `lines.append`, `read_customer_metadata`, `seen.add`, `set`, `sheet.cell`, `str`, `values.get`, `workbook.close`.

### `import_supplier_price(*, supplier_id, upload, actor, product_kind=None)`

Исходник: `price/excel.py:838`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(raw_price)).quantize`, `Supplier.objects.select_for_update`, `Supplier.objects.select_for_update().get`, `ValidationError`, `_load_uploaded_workbook`, `_require_headers`, `any`, `included[kind].append`, `int`, `isinstance`, `kind.upper`, `len`, `logger.info`, `model`, `model.objects.bulk_create`, `model.objects.filter`, `model.objects.filter(supplier=supplier, **{f'{field}__in': included[kind]}).delete`, `model.objects.values_list`, `prepared[kind].append`, `range`, `seen.add`, `seen_rows.add`, `set`, `sheet.cell`, `str`, `values.get`, `workbook.close`.

### `import_supplier_price_files(*, supplier_id, uploads, actor)`

Исходник: `price/excel.py:947`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `import_supplier_price`, `set`, `set(uploads).issubset`, `uploads.items`.

### `import_procurement_order_xlsx(upload, *, product_kind=None, allow_empty=False)`

Исходник: `price/excel.py:956`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementPriceList.objects.prefetch_related`, `ProcurementPriceList.objects.prefetch_related('items').get`, `ValidationError`, `_load_uploaded_workbook`, `_quantity`, `_require_headers`, `int`, `items.get`, `lines.append`, `price_list.items.all`, `safe_text`, `seen.add`, `seen_rows.add`, `set`, `sheet.cell`, `str`, `values.get`, `workbook.close`.

### `import_procurement_order_files(uploads, *, with_purpose=False)`

Исходник: `price/excel.py:1016`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `import_procurement_order_xlsx`, `import_stock_procurement_order_xlsx`, `len`, `result_lines.append`, `seen_items.add`, `set`, `set(uploads).issubset`, `uploads.items`.

## `price/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `decimal`, `django`, `models`, `partners.customers`, `partners.models`, `warehouse.form_defaults`, `warehouse.models`.

### `SafeSupplierChoiceField.label_from_instance(self, obj)`

Исходник: `price/forms.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierPriceUploadForm.clean(self)`

Исходник: `price/forms.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `forms.ValidationError`, `super`, `super().clean`.

### `ProcurementWeightsForm.__init__(self, *args, products, user, **kwargs)`

Исходник: `price/forms.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `forms.IntegerField`, `forms.NumberInput`, `product.product_type.get_procurement_delivery_group_display`, `super`, `super().__init__`, `user.has_perm`.

### `ProcurementWeightsForm.weights(self)`

Исходник: `price/forms.py:95`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `name.removeprefix`, `self.cleaned_data.items`.

### `ProcurementSurchargesForm.__init__(self, *args, products, user, **kwargs)`

Исходник: `price/forms.py:100`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `forms.DecimalField`, `forms.NumberInput`, `super`, `super().__init__`, `user.has_perm`.

### `ProcurementSurchargesForm.surcharges(self)`

Исходник: `price/forms.py:112`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `name.removeprefix`, `self.cleaned_data.items`.

## `price/management/commands/backfill_procurement_tech_surcharges.py`

Контролируемое заполнение исторических доплат; сначала dry-run и согласованная копия БД.

Импорты: `django.contrib.auth`, `django.core.exceptions`, `django.core.management.base`, `price.services`.

### `Command.add_arguments(self, parser)`

Исходник: `price/management/commands/backfill_procurement_tech_surcharges.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `price/management/commands/backfill_procurement_tech_surcharges.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `CommandError`, `backfill_procurement_tech_surcharges`, `get_user_model`, `get_user_model().objects.get`, `len`, `self.stdout.write`, `sum`.

## `price/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `catalog.models`, `django.conf`, `django.core.validators`, `django.db`, `partners.models`.

### `PriceDocumentSettings.get_solo(cls)`

Исходник: `price/models.py:45`.

Декораторы: `classmethod`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cls.objects.get_or_create`.

### `PriceDocumentSettings.save(self, *args, **kwargs)`

Исходник: `price/models.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().save`.

### `PriceDocumentSettings.delete(self, *args, **kwargs)`

Исходник: `price/models.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `PriceDocumentSettings.__str__(self)`

Исходник: `price/models.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceList.__str__(self)`

Исходник: `price/models.py:106`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.product(self)`

Исходник: `price/models.py:213`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.product_id(self)`

Исходник: `price/models.py:217`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.__str__(self)`

Исходник: `price/models.py:220`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.effective_postpayment_surcharge_rub(self)`

Исходник: `price/models.py:224`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.configured_markup_rub(self)`

Исходник: `price/models.py:230`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.effective_postpayment_markup_rub(self)`

Исходник: `price/models.py:234`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `ProcurementPriceListItem.stock_unit_cost(self)`

Исходник: `price/models.py:238`.

Декораторы: `property`.

Себестоимость закупки на наличие из этой версии прайса.

### `ProcurementPriceListItem.postpayment_surcharge_mode(self)`

Исходник: `price/models.py:243`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `price/postpayment_rules.py`

Доплаты за постоплату по виду/типу товара; эти правила отличаются от фиксированной памяти наценки.

Импорты: `decimal`.

### `_normalized(value)`

Исходник: `price/postpayment_rules.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `re.sub`, `re.sub('\\s+', ' ', unicodedata.normalize('NFKC', value).casefold()).strip`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', value).casefold`.

### `tech_postpayment_surcharge(product)`

Исходник: `price/postpayment_rules.py:11`.

Первоначальные доплаты по согласованной модели; неизвестным товарам нужна ставка сотрудника.

Статические вызовы: `Decimal`, `_normalized`, `any`, `re.search`.

## `price/procurement_ordering.py`

Порядок строк редактора как в ценообразовании, без разделения игр по сериям.

Импорты: `catalog.product_ordering`.

### `ordered_procurement_items(items)`

Исходник: `price/procurement_ordering.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cd_order_key`, `list`, `sorted`, `tech_brand_groups`.

## `price/procurement_suppliers.py`

Выбор поставщика из сохранённых предложений конкретной версии прайса.

Импорты: `catalog.supplier_exclusions`, `decimal`, `django.core.exceptions`, `django.core.validators`, `types`.

### `can_change_supplier(user)`

Исходник: `price/procurement_suppliers.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `user.has_perm`.

### `supplier_base_price(item, price_list, price_aed)`

Исходник: `price/procurement_suppliers.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=2)`, `ValidationError`, `amount.is_finite`, `amount.quantize`.

### `prepare_supplier_choices(items, price_list)`

Исходник: `price/procurement_suppliers.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `SimpleNamespace`, `exclusion_keys`, `format`, `format(offer.price_aed, '.6f').rstrip`, `format(offer.price_aed, '.6f').rstrip('0').rstrip`, `item.supplier_choices.append`, `item.supplier_offers.all`, `list`, `offer.supplier.letter.casefold`, `offers.values`, `sorted`, `supplier_base_price`.

### `_supplier_id(value)`

Исходник: `price/procurement_suppliers.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`, `len`, `str`, `text.isascii`, `text.isdecimal`.

### `apply_supplier_choice(item, price_list, values, actor, excluded)`

Исходник: `price/procurement_suppliers.py:63`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_supplier_id`, `can_change_supplier`, `item.supplier_offers.all`, `next`, `supplier_base_price`.

## `price/services.py`

Закупочные версии, тарифы, предложения, память наценок и Decimal-расчёты; сохранение версии атомарно.

Импорты: `catalog.audit`, `catalog.models`, `catalog.product_identifiers`, `catalog.supplier_exclusions`, `collections`, `decimal`, `django.core.exceptions`, `django.core.validators`, `django.db`, `django.db.models`, `models`, `postpayment_rules`, `pricing.models`, `procurement_suppliers`.

### `decimal_value(value, *, precision=CENT, positive=False, nonnegative=False, label='Значение')`

Исходник: `price/services.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `result.is_finite`, `str`.

### `validated_postpayment_surcharge(value)`

Исходник: `price/services.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=2)`, `decimal_value`, `str`.

### `calculate_postpayment(prepayment, *, surcharge=None)`

Исходник: `price/services.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(price + surcharge).quantize`, `Decimal`, `decimal_value`, `validated_postpayment_surcharge`.

### `round_customer_price(value)`

Исходник: `price/services.py:59`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `((price / Decimal('10')).to_integral_value(rounding=ROUND_CEILING) * Decimal('10')).quantize`, `(price / Decimal('10')).to_integral_value`, `Decimal`, `ValidationError`, `price.is_finite`, `str`.

### `rounded_customer_prices(prepayment, *, surcharge=None)`

Исходник: `price/services.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `calculate_postpayment`, `decimal_value`, `round_customer_price`.

### `calculate_prepayment(postpayment, *, surcharge=None, rounded=False)`

Исходник: `price/services.py:76`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `calculate_postpayment`, `decimal_value`, `round_customer_price`, `validated_postpayment_surcharge`.

### `_supplier_offers(*, lock=False)`

Исходник: `price/services.py:101`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `defaultdict`, `getattr`, `getattr(model.objects, queryset_method)`, `getattr(model.objects, queryset_method)().select_related`, `getattr(model.objects, queryset_method)().select_related(*relations).filter`, `queryset.order_by`, `result[kind, product.pk].append`.

### `resolve_best_suppliers(offers=None)`

Исходник: `price/services.py:118`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Counter`, `_supplier_offers`, `exclusion_keys`, `len`, `min`, `minimum_candidates.items`, `offers.items`, `row[0].name.casefold`, `sorted`.

### `MissingProcurementWeights.__init__(self, products)`

Исходник: `price/services.py:143`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `sorted`, `super`, `super().__init__`.

### `get_missing_procurement_weights()`

Исходник: `price/services.py:148`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `resolve_best_suppliers`, `sorted`, `winners.items`.

### `_price_preferences(product_keys, *, lock=False)`

Исходник: `price/services.py:156`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProcurementPricePreference.objects.all`, `Q`, `list`, `queryset.filter`, `queryset.select_for_update`.

### `MissingProcurementSurcharges.__init__(self, products)`

Исходник: `price/services.py:169`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `sorted`, `super`, `super().__init__`.

### `get_missing_procurement_surcharges()`

Исходник: `price/services.py:174`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_price_preferences`, `preferences.get`, `resolve_best_suppliers`, `sorted`, `tech_postpayment_surcharge`, `winners.items`.

### `_prepare_procurement_weights(*, winners, weights, actor)`

Исходник: `price/services.py:184`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `MissingProcurementWeights`, `Tech.objects.active`, `Tech.objects.active().select_for_update`, `Tech.objects.active().select_for_update().select_related`, `Tech.objects.active().select_for_update().select_related('product_type').filter`, `ValidationError`, `actor.has_perm`, `any`, `int`, `len`, `logger.info`, `products.values`, `set`, `set(weights).issubset`, `set_product_weight`, `str`, `weight.is_finite`, `weight.to_integral_value`.

### `weighted_procurement_delivery(*, weight_grams, tariff, dollar_rate, label='Доставка')`

Исходник: `price/services.py:216`.

Действующая весовая формула для прайса и сохранённых расчётов операций рейса.

Статические вызовы: `Decimal`, `decimal_value`.

### `procurement_delivery(*, product, kind, price_list)`

Исходник: `price/services.py:222`.

Единый расчёт доставки единицы по зафиксированным тарифам прайса.

Статические вызовы: `ValidationError`, `decimal_value`, `rates.get`, `weighted_procurement_delivery`.

### `create_procurement_price_list(*, actor, exchange_rate_usdt_aed, exchange_rate_usdt_rub, delivery_general_usdt_per_kg, delivery_devices_usdt_per_kg, delivery_storage_usdt_per_kg, delivery_cd_rub, weights=None, postpayment_surcharges=None)`

Исходник: `price/services.py:243`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=2)`, `MissingProcurementSurcharges`, `ProcurementPriceList.objects.create`, `ProcurementPriceListItem`, `ProcurementPriceListItem.objects.bulk_create`, `ProcurementPricePreference`, `ProcurementSupplierOffer`, `ProcurementSupplierOffer.objects.bulk_create`, `ValidationError`, `_prepare_procurement_weights`, `_price_preferences`, `_supplier_offers`, `actor.has_perm`, `custom_surcharge_ids.add`, `decimal_value`, `items.append`, `len`, `logger.info`, `missing_surcharges.append`, `offers.items`, `preference.save`, `preferences.get`, `procurement_delivery`, `resolve_best_suppliers`, `rounded_customer_prices`, `set`, `set(postpayment_surcharges).issubset`, `tech_postpayment_surcharge`, `validate_rate`, `validated_postpayment_surcharge`, `winners.items`.

### `NegativeProcurementMarkup.__init__(self, items)`

Исходник: `price/services.py:382`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `backfill_procurement_tech_surcharges(*, actor, price_list_id, apply=False)`

Исходник: `price/services.py:388`.

Декораторы: `transaction.atomic`.

Перенос старых строк Tech на согласованные ставки без изменения остальных ценовых составляющих.

Статические вызовы: `MissingProcurementSurcharges`, `ProcurementPriceList.objects.select_for_update`, `ProcurementPriceList.objects.select_for_update().get`, `ValidationError`, `actor.has_perm`, `calculate_postpayment`, `changes.append`, `item.full_clean`, `item.save`, `list`, `logger.info`, `missing.append`, `price_list.customer_orders.exists`, `price_list.items.select_for_update`, `price_list.items.select_for_update().filter`, `price_list.items.select_for_update().filter(product_kind='tech', postpayment_surcharge_rub__isnull=True).select_related`, `tech_postpayment_surcharge`, `zip`.

### `update_procurement_pricing(*, actor, price_list_id, rows, can_change_markup, can_change_delivery, negative_markup_confirmed=False)`

Исходник: `price/services.py:430`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(item.base_price_rub + markup + delivery).quantize`, `NegativeProcurementMarkup`, `ProcurementPriceList.objects.select_for_update`, `ProcurementPriceList.objects.select_for_update().get`, `ProcurementPriceListItem.objects.select_for_update`, `ProcurementPriceListItem.objects.select_for_update().filter`, `ProcurementPriceListItem.objects.select_for_update().filter(price_list=price_list).select_related`, `ProcurementPriceListItem.objects.select_for_update().filter(price_list=price_list).select_related('selected_supplier', 'cd', 'tech').prefetch_related`, `ProcurementPricePreference`, `ValidationError`, `_price_preferences`, `apply_supplier_choice`, `calculate_prepayment`, `decimal_value`, `exclusion_keys`, `field_change`, `item.full_clean`, `item.save`, `items.values`, `len`, `logger.info`, `preference.save`, `preferences.get`, `price_list.customer_orders.exists`, `record_product_changes`, `rounded_customer_prices`, `rows.items`, `set`, `validated_postpayment_surcharge`, `values.get`.

## `price/sony_gamepad_sorting.py`

Классификация моделей Sony-геймпадов по нормализованному названию; не изменяет товарные карточки.

Импорты: `dataclasses`.

### `normalize_product_name(value)`

Исходник: `price/sony_gamepad_sorting.py:61`.

Нормализовать регистр, пробелы, дефисы и пунктуацию только для matching.

Статические вызовы: `re.sub`, `re.sub('[^\\w]+', ' ', value, flags=re.UNICODE).strip`, `str`, `unicodedata.normalize`, `unicodedata.normalize('NFKC', str(value or '')).casefold`, `unicodedata.normalize('NFKC', str(value or '')).casefold().replace`.

### `_matches_any(value, patterns)`

Исходник: `price/sony_gamepad_sorting.py:67`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`.

### `is_sony_gamepad(product)`

Исходник: `price/sony_gamepad_sorting.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `normalize_product_name`.

### `classify_sony_gamepad(product)`

Исходник: `price/sony_gamepad_sorting.py:80`.

Вернуть ровно одну категорию; более поздние специальные группы приоритетнее.

Статические вызовы: `_matches_any`, `normalize_product_name`.

### `sony_gamepad_sort_key(product)`

Исходник: `price/sony_gamepad_sorting.py:104`.

Общий стабильный ключ Sony/Геймпад для розничного и оптового прайса.

Статические вызовы: `classify_sony_gamepad`, `normalize_product_name`.

## `price/urls.py`

Именованные HTTP-маршруты приложения прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `django.urls`.

## `price/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю прайсов и Excel.

Сохранённые предложения и расчёты закупочной версии не подменяются текущим прайсом.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db.models`, `django.http`, `django.shortcuts`, `django.utils`, `django.utils.http`, `django.views.decorators.cache`, `django.views.decorators.http`, `excel`, `forms`, `models`, `partners.customers`, `partners.models`, `pricing.models`, `procurement_ordering`, `procurement_suppliers`, `resource_storefront.models`, `resource_storefront.retail_security`, `resource_storefront.security`, `services`.

### `_price_filename(kind)`

Исходник: `price/views.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `timezone.localdate`.

### `_xlsx_response(content, filename)`

Исходник: `price/views.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `content_disposition_header`.

### `price_page(request)`

Исходник: `price/views.py:68`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Складские прайсы и данные документов — раздел по умолчанию.

Статические вызовы: `PriceDocumentSettings.get_solo`, `PriceDocumentSettingsForm`, `WarehousePriceForm`, `WholesaleWarehousePriceForm`, `permission_required_any`, `render`, `request.user.has_perm`.

### `import_prices(request)`

Исходник: `price/views.py:83`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Прайсы поставщиков и закупочные версии.

Статические вызовы: `ProcurementPriceCreateForm`, `ProcurementPriceList.objects.filter`, `ProcurementPriceList.objects.filter(is_trip_addition=False).select_related`, `ProcurementPriceList.objects.filter(is_trip_addition=False).select_related('created_by').prefetch_related`, `Supplier.objects.order_by`, `SupplierCDPrice.objects.filter`, `SupplierCDPrice.objects.filter(supplier=supplier, price__gt=0).count`, `SupplierPriceUploadForm`, `SupplierTechPrice.objects.filter`, `SupplierTechPrice.objects.filter(supplier=supplier, price__gt=0).count`, `permission_required_any`, `render`, `request.user.has_perm`, `suppliers.append`.

### `site_links(request)`

Исходник: `price/views.py:112`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Допуски на розничный и оптовый сайты по существующим правам.

Статические вызовы: `WholesaleContact.objects.filter`, `WholesaleContact.objects.filter(is_archived=False).prefetch_related`, `contact.access_links.filter`, `contact.access_links.filter(is_active=True).first`, `permission_required_any`, `recover_token`, `render`, `request.user.has_perm`, `retail_link`, `wholesale_contacts.append`.

### `document_settings_update(request)`

Исходник: `price/views.py:133`.

Декораторы: `require_POST`; `permission_required_any('price.change_document_settings')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PriceDocumentSettings.get_solo`, `PriceDocumentSettingsForm`, `form.is_valid`, `form.save`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `retail_export(request)`

Исходник: `price/views.py:146`.

Декораторы: `require_POST`; `permission_required_any('price.generate_retail_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehousePriceForm`, `_price_filename`, `_xlsx_response`, `form.is_valid`, `generate_retail_price_xlsx`, `messages.error`, `permission_required_any`, `redirect`, `str`.

### `wholesale_export(request)`

Исходник: `price/views.py:161`.

Декораторы: `require_POST`; `permission_required_any('price.generate_wholesale_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WholesaleWarehousePriceForm`, `_price_filename`, `_xlsx_response`, `customer_filename`, `form.is_valid`, `generate_wholesale_price_xlsx`, `messages.error`, `permission_required_any`, `redirect`, `resolve_customer`.

### `supplier_template_export(request, product_kind=None)`

Исходник: `price/views.py:178`.

Декораторы: `require_GET`; `permission_required_any('price.download_supplier_template')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_xlsx_response`, `generate_supplier_template`, `permission_required_any`, `redirect`.

### `supplier_template_prefilled_export(request, supplier_id, product_kind)`

Исходник: `price/views.py:192`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all('price.download_supplier_template', 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_xlsx_response`, `generate_supplier_template`, `get_object_or_404`, `permission_required_all`.

### `supplier_price_upload(request)`

Исходник: `price/views.py:206`.

Декораторы: `require_POST`; `permission_required_any('price.upload_supplier_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `'; '.join`, `SupplierPriceUploadForm`, `counts.items`, `form.is_valid`, `import_supplier_price_files`, `logger.warning`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`.

### `procurement_create(request)`

Исходник: `price/views.py:231`.

Декораторы: `require_POST`; `permission_required_any('price.create_procurement_price_list')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `ProcurementPriceCreateForm`, `ProcurementSurchargesForm`, `ProcurementWeightsForm`, `any`, `create_procurement_price_list`, `extra.is_valid`, `form.add_error`, `form.is_valid`, `get_missing_procurement_surcharges`, `get_missing_procurement_weights`, `getattr`, `len`, `messages.success`, `messages.warning`, `permission_required_any`, `price_list.items.filter`, `price_list.items.filter(markup_rub__lt=0).count`, `redirect`, `render`, `request.POST.get`.

### `procurement_detail(request, pk)`

Исходник: `price/views.py:285`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Prefetch`, `ProcurementPriceList.objects.select_related`, `ProcurementPriceList.objects.select_related('created_by').prefetch_related`, `ProcurementPriceListItem.objects.select_related`, `ProcurementPriceListItem.objects.select_related('selected_supplier', 'cd__platform', 'tech__brand', 'tech__product_type').prefetch_related`, `can_change_supplier`, `get_object_or_404`, `ordered_procurement_items`, `permission_required_any`, `prepare_supplier_choices`, `price_list.customer_orders.exists`, `price_list.items.all`, `render`, `request.user.has_perm`.

### `procurement_update(request, pk)`

Исходник: `price/views.py:317`.

Декораторы: `require_POST`; `permission_required_any('price.change_procurement_markup', 'price.change_procurement_delivery')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ValidationError`, `any`, `get_object_or_404`, `int`, `isinstance`, `json.dumps`, `json.loads`, `list`, `messages.error`, `messages.success`, `payload.items`, `payload.values`, `permission_required_any`, `price_list.items.values_list`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `set`, `str`, `update_procurement_pricing`.

### `procurement_export(request, pk, product_kind=None)`

Исходник: `price/views.py:369`.

Декораторы: `require_GET`; `permission_required_any('price.export_procurement_price_list')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_xlsx_response`, `generate_procurement_customer_xlsx`, `permission_required_any`, `redirect`.

### `procurement_stock_export(request, pk)`

Исходник: `price/views.py:380`.

Декораторы: `require_GET`; `permission_required_all('price.export_procurement_price_list', 'price.view_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_xlsx_response`, `generate_procurement_stock_xlsx`, `get_object_or_404`, `permission_required_all`.

## `pricing/admin.py`

Регистрация моделей и разрешённых действий в Django Admin ценообразования.

Себестоимость, опт, цена Avito, FBS и найденный минимум — разные величины.

Импорты: `django.contrib`, `models`, `partners.admin`.

### `SupplierPricePermissionMixin.has_module_permission(self, request)`

Исходник: `pricing/admin.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `super`, `super().has_module_permission`.

### `SupplierPricePermissionMixin.has_view_permission(self, request, obj=None)`

Исходник: `pricing/admin.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `super`, `super().has_view_permission`.

### `SupplierPricePermissionMixin.has_add_permission(self, request)`

Исходник: `pricing/admin.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `super`, `super().has_add_permission`.

### `SupplierPricePermissionMixin.has_change_permission(self, request, obj=None)`

Исходник: `pricing/admin.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `super`, `super().has_change_permission`.

### `SupplierPricePermissionMixin.has_delete_permission(self, request, obj=None)`

Исходник: `pricing/admin.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.user.has_perm`, `super`, `super().has_delete_permission`.

## `pricing/apps.py`

Конфигурация приложения и его регистрация в Django ценообразования.

Себестоимость, опт, цена Avito, FBS и найденный минимум — разные величины.

Импорты: `django.apps`.

## `pricing/avito_check_catalog.py`

Единая выборка таблицы и ручной очереди Avito Check.

Импорты: `catalog.models`, `catalog.product_search`, `django.db.models`, `integrations.avito_check`.

### `listed_products(*, query='', sort='name', product_id=None)`

Исходник: `pricing/avito_check_catalog.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.filter`, `CD.objects.filter(avito_profile__connection__isnull=False).select_related`, `CD.objects.filter(avito_profile__connection__isnull=False).select_related('avito_profile__manual_price', 'platform', 'game_series').annotate`, `CD.objects.filter(avito_profile__connection__isnull=False).select_related('avito_profile__manual_price', 'platform', 'game_series').annotate(physical_stock=Sum('warehouse_stocks__quantity')).filter`, `Sum`, `dated.sort`, `filter_products_by_text`, `getattr`, `p.name.casefold`, `products.filter`, `sorted`.

### `manual_product_data(product)`

Исходник: `pricing/avito_check_catalog.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `found.recorded_at.isoformat`, `getattr`, `manual_search_url`, `str`.

## `pricing/avito_check_views.py`

Последовательная ручная проверка цен связанных с Avito товаров.

Импорты: `avito_check_catalog`, `catalog.audit`, `catalog.models`, `core.decorators`, `decimal`, `django.conf`, `django.contrib`, `django.core.cache`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.http`, `django.middleware.csrf`, `django.shortcuts`, `django.template.loader`, `django.urls`, `django.utils`, `django.views.decorators.cache`, `django.views.decorators.http`, `integrations.avito_check`, `integrations.models`, `integrations.reef_api`, `services`, `warnings`.

### `_item(kind, pk, items=None)`

Исходник: `pricing/avito_check_views.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enumerate`, `next`, `queue`.

### `_page_context(request, items, index, *, posted=None)`

Исходник: `pricing/avito_check_views.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReefApiCredential.objects.filter`, `ReefApiCredential.objects.filter(pk=1).exclude`, `ReefApiCredential.objects.filter(pk=1).exclude(encrypted_api_key='').exists`, `display_result`, `len`, `manual_search_url`, `posted.get`, `product_price_warnings`, `request.user.has_perm`, `wholesale_margin`.

### `page(request)`

Исходник: `pricing/avito_check_views.py:54`.

Декораторы: `require_GET`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `len`, `listed_products`, `manual_search_url`, `permission_required_any`, `product_price_warnings`, `render`, `request.GET.get`, `request.GET.get('q', '').strip`, `request.user.has_perm`, `rows.append`, `wholesale_margin`.

### `manual_context(request)`

Исходник: `pricing/avito_check_views.py:80`.

Декораторы: `require_GET`; `never_cache`; `permission_required_all('pricing.view_pricing', 'pricing.change_retail_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `get_token`, `int`, `len`, `listed_products`, `manual_product_data`, `permission_required_all`, `product_id.isascii`, `product_id.isdecimal`, `request.GET.get`, `request.GET.get('q', '').strip`.

### `save_found_price(request)`

Исходник: `pricing/avito_check_views.py:99`.

Декораторы: `require_POST`; `permission_required_all('pricing.view_pricing', 'pricing.change_retail_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `AvitoManualPrice.objects.select_for_update`, `AvitoManualPrice.objects.select_for_update().filter`, `AvitoManualPrice.objects.select_for_update().filter(profile=product.avito_profile).first`, `AvitoManualPrice.objects.update_or_create`, `JsonResponse`, `Sum`, `ValidationError`, `_parse_price`, `int`, `isinstance`, `model.objects.select_related`, `model.objects.select_related('avito_profile').filter`, `permission_required_all`, `previous.recorded_at.isoformat`, `products.annotate`, `products.annotate(physical_stock=Sum('warehouse_stocks__quantity')).filter`, `products.get`, `record_product_changes`, `recorded_at.isoformat`, `request.POST.get`, `request.POST.get('price', '').strip`, `request.POST.get('price', '').strip().replace`, `str`, `timezone.localtime`, `timezone.localtime(found.recorded_at).strftime`, `timezone.now`, `transaction.atomic`, `{'cd': CD, 'tech': Tech}.get`.

### `automatic_page(request)`

Исходник: `pricing/avito_check_views.py:142`.

Декораторы: `require_GET`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_page_context`, `int`, `len`, `permission_required_any`, `queue`, `render`, `request.GET.get`.

### `_parse_price(value)`

Исходник: `pricing/avito_check_views.py:155`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `number.as_tuple`, `number.is_finite`, `str`.

### `next_product(request)`

Исходник: `pricing/avito_check_views.py:169`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `_item`, `_page_context`, `_parse_price`, `getattr`, `int`, `messages.error`, `messages.success`, `permission_required_any`, `queue`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `reverse`, `str`, `update_product_prices`.

### `check_product(request)`

Исходник: `pricing/avito_check_views.py:200`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoPriceCheckResult.objects.get`, `JsonResponse`, `_item`, `cache.add`, `cache.delete`, `display_result`, `int`, `permission_required_any`, `render_to_string`, `request.POST.get`, `run_check`, `str`.

## `pricing/fbs_views.py`

Предпросмотр, сохранение расчёта и явное применение к отправляемой цене.

Импорты: `catalog.models`, `catalog.nomenclature_forms`, `core.decorators`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `services`, `yandex_market.fbs_pricing`, `yandex_market.pricing_forms`.

### `product_for(kind, pk)`

Исходник: `pricing/fbs_views.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `model.objects.active`, `model.objects.active().select_related`, `{'cd': CD, 'tech': Tech}.get`.

### `detail(request, kind, pk)`

Исходник: `pricing/fbs_views.py:25`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FBSProductForm`, `permission_required_any`, `product_calculation`, `product_for`, `render`, `request.GET.get`, `request.user.has_perm`.

### `preview(request, kind, pk)`

Исходник: `pricing/fbs_views.py:36`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `FBSProductForm`, `JsonResponse`, `data.get`, `form.errors.values`, `form.is_valid`, `permission_required_any`, `product._meta.get_field`, `product._meta.get_field('yandex_desired_profit').clean`, `product_calculation`, `product_for`, `request.POST.get`, `set`, `str`.

### `save(request, kind, pk)`

Исходник: `pricing/fbs_views.py:56`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `FBSProductForm`, `JsonResponse`, `ValidationError`, `all`, `form.errors.values`, `form.is_valid`, `getattr`, `permission_required_any`, `product_for`, `product_version`, `request.POST.get`, `request.user.has_perm`, `save_product_inputs`, `str`, `transaction.atomic`, `update_product_prices`.

## `pricing/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния ценообразования.

Себестоимость, опт, цена Avito, FBS и найденный минимум — разные величины.

Импорты: `catalog.models`, `django.core.validators`, `django.db`, `partners.models`.

### `SupplierCDPrice.__str__(self)`

Исходник: `pricing/models.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplierTechPrice.__str__(self)`

Исходник: `pricing/models.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `pricing/services.py`

Изменение текущих продажных и поставщицких цен.

Импорты: `catalog.audit`, `catalog.models`, `catalog.product_fields`, `decimal`, `django.core.exceptions`, `django.db`, `models`, `partners.models`.

### `_price(value, *, nullable, precision)`

Исходник: `pricing/services.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `result.is_finite`, `str`.

### `product_configuration(product_type)`

Исходник: `pricing/services.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `update_product_prices(*, actor, product_type, product_id, changes, record_audit=True)`

Исходник: `pricing/services.py:41`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `Decimal`, `ValidationError`, `_price`, `changed_snapshots`, `changes.items`, `logger.exception`, `logger.info`, `product.full_clean`, `product.save`, `product_configuration`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().get`, `product_snapshot`, `record_product_changes`, `set`, `setattr`, `tuple`, `updates.items`.

### `update_supplier_price(*, actor, product_type, product_id, supplier_id, value)`

Исходник: `pricing/services.py:91`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Supplier.objects.get`, `ValidationError`, `_price`, `logger.info`, `price_model.objects.update_or_create`, `product_configuration`, `product_model.objects.active`, `product_model.objects.active().get`.

## `pricing/urls.py`

Именованные HTTP-маршруты приложения ценообразования.

Себестоимость, опт, цена Avito, FBS и найденный минимум — разные величины.

Импорты: `django.urls`.

## `pricing/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю ценообразования.

Себестоимость, опт, цена Avito, FBS и найденный минимум — разные величины.

Импорты: `catalog.models`, `catalog.product_filters`, `catalog.product_ordering`, `collections`, `core.decorators`, `decimal`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.db.models.functions`, `django.http`, `django.shortcuts`, `django.urls`, `django.views.decorators.http`, `fbs_views`, `services`, `warehouse.models`, `warnings`, `yandex_market.fbs_pricing`.

### `_pricing_storage_locations(products, assignment_model, product_field)`

Исходник: `pricing/views.py:38`.

Собирает места видимых товаров одним запросом, отдельно от суммы остатков.

Статические вызовы: `', '.join`, `'; '.join`, `assignment_model.objects.filter`, `assignment_model.objects.filter(stock__quantity__gt=0, **{f'{product_key}__in': [product.pk for product in products]}).order_by`, `assignment_model.objects.filter(stock__quantity__gt=0, **{f'{product_key}__in': [product.pk for product in products]}).order_by('stock__warehouse__name', 'position', 'id').values`, `defaultdict`, `dict.fromkeys`, `locations.items`, `locations[assignment[product_key]][assignment['stock__warehouse__name']].append`, `warehouses.items`, `warehouses.values`.

### `_pricing_filter_params(params, product_kind)`

Исходник: `pricing/views.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `params.copy`, `params.pop`.

### `_pricing_destination(request)`

Исходник: `pricing/views.py:76`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_pricing_filter_params`, `product_filter_query_string`, `redirect`, `request.POST.get`, `request.user.has_perm`, `reverse`.

### `pricing_list(request, product_kind=None)`

Исходник: `pricing/views.py:90`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').annotate`, `CD.objects.active().select_related('platform').annotate(global_stock=stock_total).order_by`, `Coalesce`, `Http404`, `IntegerField`, `Sum`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.active().select_related('brand', 'product_type').annotate`, `Tech.objects.active().select_related('brand', 'product_type').annotate(global_stock=stock_total).order_by`, `Value`, `_pricing_filter_params`, `_pricing_storage_locations`, `cd_groups.items`, `cd_groups[product.platform].append`, `cd_locations.get`, `cds.filter`, `cds.none`, `context.update`, `defaultdict`, `filter_product_querysets`, `list`, `permission_required_any`, `product.cost.to_integral_value`, `product_filter_context`, `product_filter_query_string`, `product_price_warnings`, `render`, `request.GET.get`, `request.user.has_perm`, `sorted`, `tech_brand_groups`, `tech_groups.items`, `tech_groups.values`, `tech_groups[product.product_type].append`, `tech_items.filter`, `tech_items.none`, `tech_locations.get`, `wholesale_margin`.

### `product_prices_update(request)`

Исходник: `pricing/views.py:167`.

Декораторы: `require_POST`; `permission_required_any('pricing.change_retail_price', 'pricing.change_wholesale_price', 'pricing.change_yandex_market_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `PermissionDenied`, `ValidationError`, `_pricing_destination`, `field_permissions.items`, `getattr`, `messages.error`, `messages.success`, `permission_required_any`, `product_calculation`, `product_for`, `request.POST.get`, `request.headers.get`, `request.user.has_perm`, `save_product_inputs`, `transaction.atomic`, `update_product_prices`.

### `supplier_price_update(request)`

Исходник: `pricing/views.py:243`.

Декораторы: `require_POST`; `permission_required_any('pricing.change_supplier_prices')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_pricing_destination`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `request.POST.get`, `update_supplier_price`.

## `pricing/warnings.py`

Рекомендательные предупреждения о цене; не блокируют её сохранение.

Импорты: `catalog.product_fields`.

### `wholesale_margin(wholesale, cost)`

Исходник: `pricing/warnings.py:10`.

Фактическая разница между оптовой ценой и себестоимостью.

### `price_warning(*, price, wholesale, cost, markup=None)`

Исходник: `pricing/warnings.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'\n'.join`, `reasons.append`.

### `product_price_warnings(product)`

Исходник: `pricing/warnings.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `price_warning`.

## `resource_storefront/admin.py`

Регистрация моделей и разрешённых действий в Django Admin оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `django.contrib`, `django.urls`, `django.utils.html`, `models`.

### `WholesaleContactAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `resource_storefront/admin.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `WholesaleAccessLinkAdmin.has_add_permission(self, request)`

Исходник: `resource_storefront/admin.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `WholesaleAccessLinkAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `resource_storefront/admin.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `StorefrontSettingsAdmin.has_add_permission(self, request)`

Исходник: `resource_storefront/admin.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StorefrontSettings.objects.exists`.

### `StorefrontSettingsAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `resource_storefront/admin.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `StorefrontSubmissionAdmin.has_add_permission(self, request)`

Исходник: `resource_storefront/admin.py:81`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `StorefrontSubmissionAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `resource_storefront/admin.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CatalogImageCropAdmin.preview(self, obj)`

Исходник: `resource_storefront/admin.py:99`.

Декораторы: `admin.display(description='Оригинал и кадр каталога')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `admin.display`, `format_html`, `reverse`.

### `RetailSettingsAdmin.has_add_permission(self, request)`

Исходник: `resource_storefront/admin.py:110`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RetailSettings.objects.exists`, `super`, `super().has_add_permission`.

### `RetailSettingsAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `resource_storefront/admin.py:113`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `resource_storefront/apps.py`

Конфигурация приложения и его регистрация в Django оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `django.apps`.

## `resource_storefront/asset_pipeline.py`

Пересборка декоративных WebP из сохранённых оригиналов: python -m resource_storefront.asset_pipeline.

Импорты: `PIL`, `pathlib`.

### `build()`

Исходник: `resource_storefront/asset_pipeline.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Image.open`, `Path`, `Path(__file__).resolve`, `image.crop`, `image.save`, `image.thumbnail`, `original.convert`, `print`, `round`, `tuple`, `zip`.

## `resource_storefront/catalogue.py`

Разрешённая покупателю выборка витрины, фильтры, цены и доступное физическое наличие.

Импорты: `catalog.models`, `catalog.product_search`, `django.urls`, `filters`, `models`, `warehouse.models`.

### `storefront_warehouse(mode='wholesale')`

Исходник: `resource_storefront/catalogue.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `model.objects.select_related`, `model.objects.select_related('warehouse').filter`, `model.objects.select_related('warehouse').filter(pk=1).first`.

### `visible_product_rows(*, kind='', category='', query='', platform='', brand='', product_type='', price_min=None, price_max=None, ordering='name', ids=None, mode='wholesale')`

Исходник: `resource_storefront/catalogue.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StorefrontProduct.objects.filter`, `category_type_ids`, `dates.get`, `filter_products_by_text`, `getattr`, `ids.get`, `model.objects.active`, `model.objects.active().filter`, `qs.filter`, `qs.select_related`, `result.append`, `result.sort`, `row['product'].name.casefold`, `slot.created_at.timestamp`, `stock_model.objects.filter`, `stocks.filter`, `storefront_warehouse`.

### `product_by_id(kind, pk, mode='wholesale')`

Исходник: `resource_storefront/catalogue.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `visible_product_rows`.

### `buyer_filters(rows=None)`

Исходник: `resource_storefront/catalogue.py:82`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Brand.objects.filter`, `Brand.objects.filter(pk__in={p.brand_id for p in techs}).order_by`, `Platform.objects.filter`, `Platform.objects.filter(pk__in={p.platform_id for p in cds}).order_by`, `ProductType.objects.filter`, `ProductType.objects.filter(pk__in={p.product_type_id for p in techs}).order_by`, `visible_product_rows`.

### `product_images(row)`

Исходник: `resource_storefront/catalogue.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductImage.objects.filter`, `gallery.filter`, `reverse`, `row.get`, `urls.append`, `urls.extend`.

### `row_key(kind, product_id)`

Исходник: `resource_storefront/catalogue.py:106`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`.

### `parse_cart(session, mode='wholesale')`

Исходник: `resource_storefront/catalogue.py:110`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cart.items`, `int`, `isinstance`, `key.split`, `row_key`, `session.get`.

### `set_cart(session, cart, mode='wholesale')`

Исходник: `resource_storefront/catalogue.py:126`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `resource_storefront/context_processors.py`

Публичный контекст оформления витрины без служебных закупочных/финансовых реквизитов.

Импорты: `modes`.

### `storefront_context(request)`

Исходник: `resource_storefront/context_processors.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `mode_for`, `request.session.get`.

## `resource_storefront/filters.py`

Состояние каталога и явное сопоставление редакционных разделов справочнику CRM.

Импорты: `catalog.models`, `django`, `django.conf`, `django.http`.

### `category_type_ids(category)`

Исходник: `resource_storefront/filters.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductType.objects.filter`, `ProductType.objects.filter(name__in=mapping.get(category, ())).values_list`, `getattr`, `list`, `mapping.get`.

### `normalized_query(params)`

Исходник: `resource_storefront/filters.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `QueryDict`, `params.get`, `params.get(name, '').strip`.

### `PriceFilterField.to_python(self, value)`

Исходник: `resource_storefront/filters.py:51`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`, `super`, `super().to_python`, `value.replace`, `value.replace('\xa0', '').replace`, `value.replace('\xa0', '').replace(' ', '').replace`.

### `CatalogueFilterForm.__init__(self, data, *, filters, **kwargs)`

Исходник: `resource_storefront/filters.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `forms.TextInput`, `self.fields.values`, `str`, `super`, `super().__init__`.

### `CatalogueFilterForm.clean(self)`

Исходник: `resource_storefront/filters.py:83`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `self.add_error`, `super`, `super().clean`.

## `resource_storefront/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `django`.

### `RetailCheckoutForm.clean(self)`

Исходник: `resource_storefront/forms.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `data.get('telegram', '').strip`, `len`, `re.fullmatch`, `re.sub`, `self.add_error`, `super`, `super().clean`.

## `resource_storefront/image_crops.py`

Кадр каталога вычисляется из оригинала; файл товара никогда не перезаписывается.

Импорты: `models`.

### `crop_catalog_image(image, product, kind)`

Исходник: `resource_storefront/image_crops.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CatalogImageCrop.objects.filter`, `CatalogImageCrop.objects.filter(**{kind: product}, source_image=product.title_image.name).first`, `float`, `image.crop`, `min`, `round`.

## `resource_storefront/log_filters.py`

Редактирование чувствительных ссылок/токенов в логах витрины до их вывода.

### `RetailTokenFilter.filter(self, record)`

Исходник: `resource_storefront/log_filters.py:8`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `re.sub`, `record.getMessage`.

## `resource_storefront/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `catalog.models`, `django.conf`, `django.core.exceptions`, `django.core.validators`, `django.db`, `sales.models`, `warehouse.models`.

### `WholesaleContact.__str__(self)`

Исходник: `resource_storefront/models.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `StorefrontSettings.get_solo(cls)`

Исходник: `resource_storefront/models.py:70`.

Декораторы: `classmethod`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cls.objects.get_or_create`.

### `StorefrontProduct.product(self)`

Исходник: `resource_storefront/models.py:94`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `StorefrontProduct.product_kind(self)`

Исходник: `resource_storefront/models.py:98`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CollectionProduct.product(self)`

Исходник: `resource_storefront/models.py:126`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CollectionProduct.product_kind(self)`

Исходник: `resource_storefront/models.py:130`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CatalogImageCrop.product(self)`

Исходник: `resource_storefront/models.py:196`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CatalogImageCrop.clean(self)`

Исходник: `resource_storefront/models.py:199`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `bool`.

### `CatalogImageCrop.save(self, *args, **kwargs)`

Исходник: `resource_storefront/models.py:206`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().save`.

### `CatalogImageCrop.__str__(self)`

Исходник: `resource_storefront/models.py:210`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`.

## `resource_storefront/modes.py`

Режим выбирает серверный URL namespace; параметры браузера его не меняют.

Импорты: `django.urls`, `models`.

### `mode_for(request)`

Исходник: `resource_storefront/modes.py:2`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`.

### `session_key(request, key)`

Исходник: `resource_storefront/modes.py:6`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `key.replace`, `mode_for`.

### `storefront_url(request, name, **kwargs)`

Исходник: `resource_storefront/modes.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `mode_for`, `reverse`.

### `config_for(request)`

Исходник: `resource_storefront/modes.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `mode_for`, `model.objects.filter`, `model.objects.filter(pk=1).first`.

## `resource_storefront/retail_concurrency_checks.py`

Запускать с browser_test_settings: два подключения к отдельной файловой SQLite.

Импорты: `cash.models`, `catalog.models`, `concurrent.futures`, `cryptography.fernet`, `django.db`, `django.test`, `django.urls`, `models`, `retail_security`, `sales.models`, `security`, `threading`, `warehouse.models`.

### `RetailConcurrencyTests.test_last_unit_between_retail_and_wholesale(self)`

Исходник: `resource_storefront/retail_concurrency_checks.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Barrier`, `CD.objects.create`, `CDWarehouseStock.objects.create`, `CashTransaction.objects.exists`, `Client`, `Platform.objects.create`, `RetailSettings.objects.update_or_create`, `Sale.objects.count`, `StorefrontSettings.objects.update_or_create`, `ThreadPoolExecutor`, `Warehouse.objects.create`, `WholesaleContact.objects.create`, `barrier.wait`, `client.get`, `client.post`, `clients.append`, `close_old_connections`, `issue_link`, `list`, `pool.map`, `recover_token`, `retail_link`, `reverse`, `self.assertEqual`, `self.assertFalse`, `sorted`, `stock.refresh_from_db`.

## `resource_storefront/retail_security.py`

Розничный контекст доступа и токены; отделён от оптового контакта и CRM-сессии.

Импорты: `django.db`, `django.views.decorators.debug`, `models`, `security`.

### `retail_link(*, actor=None, regenerate=False)`

Исходник: `resource_storefront/retail_security.py:17`.

Декораторы: `sensitive_variables('token')`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RetailSettings.objects.get_or_create`, `RetailSettings.objects.select_for_update`, `RetailSettings.objects.select_for_update().get`, `_cipher`, `_cipher().encrypt`, `_cipher().encrypt(token.encode()).decode`, `config.save`, `getattr`, `hashlib.sha256`, `hashlib.sha256(token.encode()).hexdigest`, `logger.info`, `secrets.token_urlsafe`, `sensitive_variables`, `token.encode`, `uuid.uuid4`.

### `validate_retail(request)`

Исходник: `resource_storefront/retail_security.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RetailSettings.objects.filter`, `RetailSettings.objects.filter(pk=1, generation=generation).exclude`, `RetailSettings.objects.filter(pk=1, generation=generation).exclude(token_digest='').exists`, `request.session.get`, `request.session.pop`.

### `enter_retail(request, config)`

Исходник: `resource_storefront/retail_security.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.session.cycle_key`, `request.session.get`, `request.session.set_expiry`, `str`, `uuid.uuid4`.

## `resource_storefront/retail_urls.py`

Маршруты розничной витрины с общими каталогом/корзиной и отдельным контекстом доступа.

Импорты: `django.urls`.

## `resource_storefront/retail_views.py`

Выдача/обновление розничного доступа; не создаёт отдельный склад или независимую продажу.

Импорты: `catalogue`, `core.decorators`, `django.contrib`, `django.core.cache`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.views.decorators.debug`, `django.views.decorators.http`, `forms`, `models`, `modes`, `retail_security`, `sales.models`, `sales.services`, `views`, `warehouse.models`.

### `access(request, token)`

Исходник: `resource_storefront/retail_views.py:23`.

Декораторы: `require_GET`; `sensitive_variables('token')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `RetailSettings.objects.filter`, `RetailSettings.objects.filter(pk=1, token_digest=digest).first`, `_private`, `cache.add`, `cache.incr`, `enter_retail`, `hashlib.sha256`, `hashlib.sha256(request.META.get('REMOTE_ADDR', 'unknown').encode()).hexdigest`, `hashlib.sha256(token.encode()).hexdigest`, `redirect`, `render`, `request.META.get`, `request.META.get('REMOTE_ADDR', 'unknown').encode`, `sensitive_variables`, `token.encode`.

### `regenerate(request)`

Исходник: `resource_storefront/retail_views.py:42`.

Декораторы: `require_POST`; `permission_required_any('resource_storefront.manage_retail_storefront')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `messages.success`, `permission_required_any`, `redirect`, `retail_link`.

### `retail_checkout_status(request)`

Исходник: `resource_storefront/retail_views.py:48`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `_clear_cart`, `_submission`, `storefront_url`.

### `_submission(request)`

Исходник: `resource_storefront/retail_views.py:55`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RetailSubmission.objects.filter`, `RetailSubmission.objects.filter(visitor_id=visitor, idempotency_key=key, sale__isnull=False).first`, `request.session.get`.

### `_clear_cart(request)`

Исходник: `resource_storefront/retail_views.py:63`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.session.pop`.

### `retail_success(request, sale_id)`

Исходник: `resource_storefront/retail_views.py:68`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RetailSubmission.objects.select_related`, `RetailSubmission.objects.select_related('sale').filter`, `RetailSubmission.objects.select_related('sale').filter(visitor_id=request.session.get('retailer_visitor'), sale_id=sale_id).first`, `render`, `request.session.get`.

### `retail_checkout(request)`

Исходник: `resource_storefront/retail_views.py:75`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `RetailCheckoutForm`, `RetailSettings.objects.select_for_update`, `RetailSettings.objects.select_for_update().filter`, `RetailSettings.objects.select_for_update().filter(pk=1, generation=request.session.get('retailer_generation')).first`, `RetailSubmission.objects.create`, `RetailSubmission.objects.filter`, `RetailSubmission.objects.filter(visitor_id=visitor, idempotency_key=key).first`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_ajax`, `_cart_context`, `_clear_cart`, `_locked_inventory`, `_submission`, `cart.items`, `create_sale`, `error`, `form.is_valid`, `int`, `k.split`, `messages.error`, `parse_cart`, `redirect`, `render`, `request.POST.get`, `request.POST.getlist`, `request.session.get`, `sale.save`, `storefront_url`, `submission.save`, `success`, `transaction.atomic`.

## `resource_storefront/security.py`

Доступ оптового покупателя по разрешённому контакту/ссылке и защищённая выдача публичного контента.

Импорты: `cryptography.fernet`, `django.conf`, `django.core.exceptions`, `django.db`, `django.utils`, `models`.

### `_cipher()`

Исходник: `resource_storefront/security.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Fernet`, `ImproperlyConfigured`, `getattr`, `key.encode`.

### `issue_link(contact, actor)`

Исходник: `resource_storefront/security.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WholesaleAccessLink.objects.create`, `WholesaleAccessLink.objects.filter`, `WholesaleAccessLink.objects.filter(contact=contact, is_active=True).update`, `_cipher`, `cipher.encrypt`, `cipher.encrypt(token.encode()).decode`, `hashlib.sha256`, `hashlib.sha256(token.encode('utf-8')).hexdigest`, `secrets.token_urlsafe`, `timezone.now`, `token.encode`, `transaction.atomic`.

### `recover_token(link)`

Исходник: `resource_storefront/security.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_cipher`, `_cipher().decrypt`, `_cipher().decrypt(link.encrypted_token.encode('ascii')).decode`, `link.encrypted_token.encode`.

### `contact_for_request(request)`

Исходник: `resource_storefront/security.py:45`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WholesaleAccessLink.objects.filter`, `WholesaleAccessLink.objects.filter(pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False).select_related`, `WholesaleAccessLink.objects.filter(pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False).select_related('contact').values_list`, `WholesaleAccessLink.objects.filter(pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False).select_related('contact').values_list('contact', flat=True).first`, `WholesaleAccessLink.objects.get`, `__import__`, `__import__('resource_storefront.models', fromlist=['WholesaleContact']).WholesaleContact.objects.filter`, `__import__('resource_storefront.models', fromlist=['WholesaleContact']).WholesaleContact.objects.filter(pk=contact_id, is_archived=False).first`, `request.session.get`.

### `enter_buyer_session(request, link)`

Исходник: `resource_storefront/security.py:58`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.session.cycle_key`, `request.session.get`, `request.session.pop`, `request.session.set_expiry`.

### `validate_buyer(request)`

Исходник: `resource_storefront/security.py:70`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WholesaleAccessLink.objects.select_related`, `WholesaleAccessLink.objects.select_related('contact').filter`, `WholesaleAccessLink.objects.select_related('contact').filter(pk=link_id, contact_id=contact_id, is_active=True, contact__is_archived=False).first`, `request.session.get`, `request.session.pop`.

## `resource_storefront/templatetags/resource_format.py`

Шаблонное форматирование витрины; не пересчитывает сохранённые финансовые значения.

Импорты: `decimal`, `django`, `django.utils.html`.

### `hero_heading(value)`

Исходник: `resource_storefront/templatetags/resource_format.py:10`.

Декораторы: `register.filter`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `format_html`, `len`, `title.endswith`, `title[:-len(phrase)].strip`.

### `rubles(value)`

Исходник: `resource_storefront/templatetags/resource_format.py:19`.

Декораторы: `register.filter`.

Разряды разделены неразрывным пробелом; значимые копейки сохраняются.

Статические вызовы: `Decimal`, `amount.is_finite`, `amount.to_integral_value`, `format`, `format(amount, f',.{places}f').replace`, `format(amount, f',.{places}f').replace(',', '\xa0').replace`, `str`.

## `resource_storefront/templatetags/storefront.py`

URL и общие шаблонные компоненты оптового/розничного контекста.

Импорты: `django`, `django.urls`, `resource_storefront.modes`.

### `storefront_url(context, name, *args)`

Исходник: `resource_storefront/templatetags/storefront.py:10`.

Декораторы: `register.simple_tag(takes_context=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `mode_for`, `register.simple_tag`, `reverse`.

## `resource_storefront/urls.py`

Именованные HTTP-маршруты приложения оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `django.urls`.

## `resource_storefront/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю оптовой и розничной витрин.

Публичная витрина не раскрывает закупочные данные и повторно проверяет наличие при оформлении.

Импорты: `PIL`, `catalog.audit`, `catalog.models`, `catalog.product_media`, `catalogue`, `core.decorators`, `decimal`, `django.contrib`, `django.core.cache`, `django.core.exceptions`, `django.core.paginator`, `django.db`, `django.db.models`, `django.http`, `django.shortcuts`, `django.template.loader`, `django.urls`, `django.utils`, `django.utils.http`, `django.utils.text`, `django.views.decorators.cache`, `django.views.decorators.http`, `filters`, `forms`, `image_crops`, `io`, `models`, `modes`, `partners.models`, `retail_security`, `retail_views`, `sales.models`, `sales.services`, `security`, `uuid`, `warehouse.models`.

### `_ajax(request)`

Исходник: `resource_storefront/views.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `request.headers.get`.

### `_private(response)`

Исходник: `resource_storefront/views.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `buyer_required(view)`

Исходник: `resource_storefront/views.py:58`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `_ajax`, `_private`, `mode_for`, `redirect`, `render`, `request.session.get`, `request.user.has_perm`, `validate_buyer`, `validate_retail`, `view`.

### `denied(request)`

Исходник: `resource_storefront/views.py:90`.

Декораторы: `require_GET`; `never_cache`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_private`, `render`.

### `access(request, token)`

Исходник: `resource_storefront/views.py:96`.

Декораторы: `require_GET`; `never_cache`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `WholesaleAccessLink.objects.select_related`, `WholesaleAccessLink.objects.select_related('contact').filter`, `WholesaleAccessLink.objects.select_related('contact').filter(token_digest=digest, is_active=True, contact__is_archived=False).first`, `_private`, `cache.add`, `cache.incr`, `cache.set`, `enter_buyer_session`, `hashlib.sha256`, `hashlib.sha256(ip.encode('utf-8')).hexdigest`, `hashlib.sha256(token.encode('utf-8')).hexdigest`, `ip.encode`, `redirect`, `render`, `request.META.get`, `token.encode`.

### `_row_for_slot(slot)`

Исходник: `resource_storefront/views.py:118`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `product_by_id`.

### `home(request)`

Исходник: `resource_storefront/views.py:125`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductCollection.objects.filter`, `Q`, `StorefrontNews.objects.filter`, `StorefrontProduct.objects.filter`, `StorefrontSettings.objects.filter`, `StorefrontSettings.objects.filter(pk=1).first`, `_row_for_slot`, `collection.items.select_related`, `collections.append`, `getattr`, `parse_cart`, `parse_cart(request.session).values`, `render`, `request.GET.get`, `request.user.has_perm`, `reverse`, `sum`, `timezone.now`.

### `catalogue(request, kind=None)`

Исходник: `resource_storefront/views.py:154`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CatalogueFilterForm`, `Paginator`, `Paginator(rows, 12).get_page`, `StorefrontProduct.objects.filter`, `StorefrontProduct.objects.filter(placement='new', cd__isnull=False).values_list`, `StorefrontProduct.objects.filter(placement='new', tech__isnull=False).values_list`, `any`, `buyer_filters`, `data.copy`, `data.items`, `data.urlencode`, `dict`, `dict(form.fields[key].choices).get`, `form.is_valid`, `hasattr`, `list`, `mode_for`, `normalized_query`, `page.has_next`, `page.has_previous`, `page.next_page_number`, `page.paginator.get_elided_page_range`, `page.previous_page_number`, `page_url`, `pagination.append`, `params.urlencode`, `parse_cart`, `parse_cart(request.session, mode_for(request)).values`, `redirect`, `render`, `request.GET.get`, `sum`, `visible_product_rows`.

### `product_detail(request, kind, pk)`

Исходник: `resource_storefront/views.py:195`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `back_url.startswith`, `mode_for`, `parse_cart`, `parse_cart(request.session, mode_for(request)).values`, `product_by_id`, `product_images`, `render`, `request.GET.get`, `request.get_host`, `storefront_url`, `sum`, `url_has_allowed_host_and_scheme`.

### `news_list(request)`

Исходник: `resource_storefront/views.py:210`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Paginator`, `Paginator(StorefrontNews.objects.filter(status='published', published_at__lte=timezone.now()), 12).get_page`, `StorefrontNews.objects.filter`, `mode_for`, `parse_cart`, `parse_cart(request.session, mode_for(request)).values`, `render`, `request.GET.get`, `sum`, `timezone.now`.

### `news_detail(request, slug)`

Исходник: `resource_storefront/views.py:217`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `item.newscdproduct_set.select_related`, `item.newstechproduct_set.select_related`, `mode_for`, `parse_cart`, `parse_cart(request.session, mode_for(request)).values`, `product_by_id`, `render`, `row.get`, `sum`, `timezone.now`.

### `_cart_context(request, changes=False)`

Исходник: `resource_storefront/views.py:227`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `RetailCheckoutForm if mode_for(request) == 'retail' else CheckoutForm`, `any`, `bool`, `cart.items`, `cart.values`, `config_for`, `hashlib.sha256`, `hashlib.sha256(json.dumps(version_data, sort_keys=True).encode()).hexdigest`, `int`, `json.dumps`, `json.dumps(version_data, sort_keys=True).encode`, `key.split`, `mode_for`, `parse_cart`, `product_by_id`, `request.session.get`, `request.session.get(session_key(request, 'resource_cart_seen'), {}).get`, `row.get`, `rows.append`, `session_key`, `str`, `sum`.

### `cart_view(request)`

Исходник: `resource_storefront/views.py:265`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_cart_context`, `render`, `request.session.get`, `session_key`, `uuid4`.

### `_remember_quantity(request, key)`

Исходник: `resource_storefront/views.py:272`.

Изменение количества не означает согласия с новой ценой и остатком.

Статические вызовы: `_cart_context`, `request.session.get`, `request.session.get(session_key(request, 'resource_cart_seen'), {}).copy`, `seen.get`, `seen.pop`, `session_key`.

### `_cart_reply(request, error='')`

Исходник: `resource_storefront/views.py:283`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `_ajax`, `_cart_context`, `messages.error`, `redirect`, `render_to_string`, `storefront_url`.

### `cart_add(request)`

Исходник: `resource_storefront/views.py:296`.

Декораторы: `buyer_required`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `JsonResponse`, `_ajax`, `_remember_quantity`, `cart.get`, `cart.values`, `int`, `messages.error`, `messages.success`, `min`, `mode_for`, `parse_cart`, `parse_cart(request.session, mode_for(request)).values`, `product_by_id`, `redirect`, `request.POST.get`, `request.get_host`, `request.is_secure`, `request.session.get`, `row_key`, `session_key`, `set_cart`, `storefront_url`, `sum`, `url_has_allowed_host_and_scheme`, `uuid4`.

### `cart_update(request, key)`

Исходник: `resource_storefront/views.py:334`.

Декораторы: `buyer_required`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_cart_reply`, `_remember_quantity`, `int`, `key.split`, `mode_for`, `parse_cart`, `product_by_id`, `request.POST.get`, `set_cart`.

### `cart_remove(request, key)`

Исходник: `resource_storefront/views.py:353`.

Декораторы: `buyer_required`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_cart_reply`, `_remember_quantity`, `cart.pop`, `mode_for`, `parse_cart`, `set_cart`.

### `cart_refresh(request)`

Исходник: `resource_storefront/views.py:363`.

Декораторы: `buyer_required`; `require_POST`.

Покупатель явно принимает текущие цены и наличие; позиции с нулём убираются.

Статические вызовы: `_cart_context`, `cart.items`, `int`, `key.split`, `messages.info`, `min`, `mode_for`, `parse_cart`, `product_by_id`, `redirect`, `session_key`, `set_cart`, `storefront_url`, `updated.items`.

### `checkout(request)`

Исходник: `resource_storefront/views.py:380`.

Декораторы: `buyer_required`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CheckoutForm`, `HttpResponse`, `JsonResponse`, `StorefrontSubmission.objects.filter`, `StorefrontSubmission.objects.filter(contact=contact, idempotency_key=key).select_related`, `StorefrontSubmission.objects.filter(contact=contact, idempotency_key=key).select_related('sale').first`, `StorefrontSubmission.objects.get_or_create`, `ValidationError`, `WholesaleAccessLink.objects.select_for_update`, `WholesaleAccessLink.objects.select_for_update().filter`, `WholesaleAccessLink.objects.select_for_update().filter(pk=getattr(request, 'wholesale_access_link_id', None), contact=contact, is_active=True).exists`, `_ajax`, `_cart_context`, `any`, `checkout_form.is_valid`, `config_for`, `create_sale`, `getattr`, `messages.error`, `messages.warning`, `mode_for`, `redirect`, `render`, `request.POST.get`, `request.session.get`, `request.session.pop`, `retail_checkout`, `row.get`, `sale.save`, `session_key`, `storefront_url`, `str`, `submission.save`, `transaction.atomic`, `uuid4`.

### `checkout_status(request)`

Исходник: `resource_storefront/views.py:480`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `StorefrontSubmission.objects.filter`, `StorefrontSubmission.objects.filter(contact=request.wholesale_contact, idempotency_key=request.session.get(session_key(request, 'resource_checkout_key'), ''), sale__isnull=False).first`, `mode_for`, `request.session.get`, `request.session.pop`, `retail_checkout_status`, `session_key`, `storefront_url`.

### `order_success(request, sale_id)`

Исходник: `resource_storefront/views.py:495`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.objects.filter`, `Sale.objects.filter(pk=sale_id, wholesale_contact=request.wholesale_contact, storefront_source='resource_storefront').first`, `mode_for`, `render`, `retail_success`.

### `_file_response(image)`

Исходник: `resource_storefront/views.py:505`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `image.open`, `mimetypes.guess_type`, `source.read`.

### `product_photo(request, kind, pk, image_id)`

Исходник: `resource_storefront/views.py:515`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BytesIO`, `HttpResponse`, `Image.open`, `ImageOps.exif_transpose`, `ProductImage.objects.filter`, `_file_response`, `_private`, `crop_catalog_image`, `gallery.filter`, `gallery.first`, `image.open`, `int`, `mode_for`, `output.getvalue`, `product_by_id`, `request.GET.get`, `round`, `thumbnail.convert`, `thumbnail.convert('RGB').save`, `thumbnail.thumbnail`.

### `content_asset(request, kind, pk)`

Исходник: `resource_storefront/views.py:551`.

Декораторы: `buyer_required`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_file_response`, `_private`, `config_for`, `get_object_or_404`, `getattr`, `request.GET.get`, `timezone.now`.

### `contacts(request)`

Исходник: `resource_storefront/views.py:567`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(is_archived=False).only`, `Q`, `WholesaleContact.objects.filter`, `WholesaleContact.objects.filter(is_archived=False).prefetch_related`, `permission_required_any`, `recover_token`, `render`, `request.GET.get`, `request.GET.get('q', '').strip`, `row.access_links.filter`, `row.access_links.filter(is_active=True).first`, `rows.filter`.

### `contact_save(request, pk=None)`

Исходник: `resource_storefront/views.py:582`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `Partner.objects.filter`, `Partner.objects.filter(pk=value, is_archived=False).exists`, `ValidationError`, `WholesaleContact`, `contact.full_clean`, `contact.save`, `get_object_or_404`, `issue_link`, `len`, `messages.error`, `messages.success`, `permission_required_any`, `re.fullmatch`, `redirect`, `request.POST.get`, `request.POST.get('address', '').strip`, `request.POST.get('name', '').strip`, `request.POST.get('phone', '').strip`, `transaction.atomic`, `value.isdecimal`.

### `link_issue(request, pk)`

Исходник: `resource_storefront/views.py:614`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `issue_link`, `messages.error`, `permission_required_any`, `redirect`, `request.POST.get`, `request.build_absolute_uri`, `request.user.has_perm`, `reverse`.

### `link_revoke(request, pk)`

Исходник: `resource_storefront/views.py:632`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `link.save`, `messages.success`, `permission_required_any`, `redirect`, `timezone.now`.

### `manage(request)`

Исходник: `resource_storefront/views.py:643`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductCollection.objects.prefetch_related`, `StorefrontNews.objects.all`, `StorefrontProduct.objects.filter`, `StorefrontSettings.get_solo`, `Warehouse.objects.order_by`, `availability.get`, `getattr`, `model.objects.active`, `model.objects.active().filter`, `model.objects.active().filter(name__icontains=product_q).order_by`, `permission_required_any`, `product_results.extend`, `render`, `request.GET.get`, `request.GET.get('product_q', '').strip`, `stock_model.objects.filter`.

### `preview_start(request)`

Исходник: `resource_storefront/views.py:667`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_GET`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `permission_required_any`, `redirect`, `reverse`.

### `settings_save(request)`

Исходник: `resource_storefront/views.py:674`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `Decimal`, `StorefrontSettings.get_solo`, `Warehouse.objects.filter`, `Warehouse.objects.filter(pk=warehouse_id).exists`, `config.hero_button_url.startswith`, `config.save`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.FILES.get`, `request.POST.get`, `request.POST.get('minimum_order_amount', '').strip`, `request.POST.get(field, '').strip`, `setattr`, `validate_product_image`.

### `slot_add(request)`

Исходник: `resource_storefront/views.py:710`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StorefrontProduct.objects.filter`, `StorefrontProduct.objects.filter(placement=placement).count`, `StorefrontProduct.objects.get_or_create`, `int`, `messages.error`, `messages.success`, `model.objects.active`, `model.objects.active().get`, `permission_required_any`, `redirect`, `request.POST.get`.

### `product_publication(request, kind, pk)`

Исходник: `resource_storefront/views.py:731`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `field_change`, `get_object_or_404`, `messages.success`, `model.objects.active`, `permission_required_any`, `product._meta.get_field`, `product.save`, `record_product_changes`, `redirect`, `request.POST.get`, `str`, `transaction.atomic`.

### `slot_remove(request, pk)`

Исходник: `resource_storefront/views.py:762`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `get_object_or_404(StorefrontProduct, pk=pk).delete`, `permission_required_any`, `redirect`.

### `news_save(request, pk=None)`

Исходник: `resource_storefront/views.py:769`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `StorefrontNews`, `get_object_or_404`, `item.full_clean`, `item.save`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.FILES.get`, `request.POST.get`, `request.POST.get('body', '').strip`, `request.POST.get('excerpt', '').strip`, `request.POST.get('slug', '').strip`, `request.POST.get('title', '').strip`, `slugify`, `timezone.now`, `validate_product_image`.

### `news_unpublish(request, pk)`

Исходник: `resource_storefront/views.py:799`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `item.save`, `permission_required_any`, `redirect`.

### `collection_save(request, pk=None)`

Исходник: `resource_storefront/views.py:809`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `ProductCollection`, `collection.full_clean`, `collection.save`, `get_object_or_404`, `int`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `request.POST.get('slug', '').strip`, `request.POST.get('title', '').strip`, `slugify`.

### `collection_product_add(request, pk)`

Исходник: `resource_storefront/views.py:828`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CollectionProduct.objects.get_or_create`, `collection.items.count`, `get_object_or_404`, `int`, `messages.error`, `model.objects.active`, `model.objects.active().get`, `permission_required_any`, `redirect`, `request.POST.get`.

### `collection_product_remove(request, pk)`

Исходник: `resource_storefront/views.py:845`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `get_object_or_404(CollectionProduct, pk=pk).delete`, `permission_required_any`, `redirect`.

### `news_product_add(request, pk)`

Исходник: `resource_storefront/views.py:852`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `int`, `messages.error`, `model.objects.active`, `model.objects.active().get`, `permission_required_any`, `redirect`, `request.POST.get`, `through.objects.filter`, `through.objects.filter(news=item).count`, `through.objects.get_or_create`.

### `news_product_remove(request, kind, pk)`

Исходник: `resource_storefront/views.py:870`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `get_object_or_404`, `get_object_or_404(model, pk=pk).delete`, `permission_required_any`, `redirect`.

## `sales/admin.py`

Регистрация моделей и разрешённых действий в Django Admin продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `django.contrib`, `models`.

### `SaleHistoryAdmin.has_add_permission(self, request)`

Исходник: `sales/admin.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SaleHistoryAdmin.has_change_permission(self, request, obj=None)`

Исходник: `sales/admin.py:13`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SaleHistoryAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `sales/admin.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `sales/apps.py`

Конфигурация приложения и его регистрация в Django продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `django.apps`.

## `sales/avito_order_models.py`

Ссылка на заказ Avito и очередь печати, независимые от браузерной вкладки.

Импорты: `django.conf`, `django.db`.

## `sales/avito_order_views.py`

Session/CSRF расширения и штатная форма создания продажи.

Импорты: `avito_shipping`, `core.decorators`, `core.external_policy`, `django.core.exceptions`, `django.db`, `django.http`, `django.middleware.csrf`, `django.shortcuts`, `django.urls`, `django.views.decorators.cache`, `django.views.decorators.http`, `forms`, `models`, `services`, `views`.

### `bridge(request)`

Исходник: `sales/avito_order_views.py:22`.

Декораторы: `never_cache`; `permission_required_any('sales.create_sale')`; `require_http_methods(['GET', 'POST'])`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `AvitoBrowserOrder.objects.select_related`, `AvitoBrowserOrder.objects.select_related('sale').filter`, `JsonResponse`, `ValidationError`, `controls.cancel`, `controls.change_status`, `controls.status_styles`, `controls.summary`, `data.get`, `get_object_or_404`, `get_token`, `getattr`, `isinstance`, `json.loads`, `len`, `permission_required_any`, `render`, `request_label`, `require_http_methods`, `require_live_operation`, `reverse`, `service.order_id`, `service.prepare_order`, `str`, `uuid.UUID`, `{'test_environment_blocked': 403, 'stale_sale': 409}.get`.

### `create(request, pk)`

Исходник: `sales/avito_order_views.py:70`.

Декораторы: `permission_required_any('sales.create_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'\n'.join`, `AvitoBrowserOrder.objects.select_for_update`, `AvitoBrowserOrder.objects.select_for_update().select_related`, `AvitoBrowserOrder.objects.select_for_update().select_related('sale').get`, `AvitoBrowserOrder.objects.select_related`, `SaleCreateForm`, `_consignment_options`, `_parse_lines`, `_posted_initial_items`, `_sale_destination`, `create_sale`, `dict`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `order.save`, `permission_required_any`, `render`, `request.user.has_perm`, `require_live_operation`, `service.initial_lines`, `str`, `transaction.atomic`.

## `sales/avito_orders.py`

Подготовка заказа из расширения не проводит продажу и не меняет наличие.

Импорты: `decimal`, `django.core.exceptions`, `django.db`, `integrations.models`, `models`.

### `order_id(value)`

Исходник: `sales/avito_orders.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `isinstance`, `re.fullmatch`.

### `prepare_order(data, actor)`

Исходник: `sales/avito_orders.py:18`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoBrowserOrder.objects.get_or_create`, `Decimal`, `ValidationError`, `amount.as_tuple`, `amount.is_finite`, `any`, `data.get`, `isinstance`, `len`, `order_id`, `str`, `str(data.get('carrier', '')).strip`, `str(data.get('status', '')).lower`, `t.strip`.

### `initial_lines(order)`

Исходник: `sales/avito_orders.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoListingConnection.objects.select_related`, `AvitoListingConnection.objects.select_related('profile__cd', 'profile__tech').filter`, `dict`, `len`, `list`, `profile.product_kind.upper`, `rows.append`, `str`.

## `sales/avito_sale_controls.py`

Статусы связанной продажи CRM; сами заказы на Avito эти действия не меняют.

Импорты: `avito_orders`, `django.conf`, `django.core.exceptions`, `django.db`, `django.urls`, `functools`, `models`, `pathlib`, `services`.

### `status_styles()`

Исходник: `sales/avito_sale_controls.py:16`.

Декораторы: `lru_cache(maxsize=1)`.

Те же классы и цвета, что в CRM; отдельной копии палитры в расширении нет.

Статические вызовы: `(Path(settings.BASE_DIR) / 'static/css/sales-list.css').read_text`, `Path`, `lru_cache`.

### `can_view(sale, actor)`

Исходник: `sales/avito_sale_controls.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `actor.has_perm`.

### `summary(order, actor)`

Исходник: `sales/avito_sale_controls.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.OrderStatus`, `actor.has_perm`, `bool`, `can_mark_paid`, `can_view`, `dict`, `next_order_status`, `reverse`, `sale.get_order_status_display`, `sale.get_payment_method_display`, `sale.get_payment_status_display`, `sale.updated_at.isoformat`, `str`.

### `change_status(data, actor)`

Исходник: `sales/avito_sale_controls.py:45`.

Декораторы: `transaction.atomic`.

Права, текущая версия и штатные сервисы проверяются до проведения операции.

Статические вызовы: `AvitoBrowserOrder.objects.select_related`, `AvitoBrowserOrder.objects.select_related('sale').get`, `PermissionDenied`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `actor.has_perm`, `advance_order_status`, `can_view`, `data.get`, `mark_sale_paid`, `order_id`, `sale.updated_at.isoformat`, `summary`, `{'order': 'sales.advance_order_status', 'payment': 'sales.mark_sale_paid'}.get`.

### `cancel(data, actor)`

Исходник: `sales/avito_sale_controls.py:75`.

Декораторы: `transaction.atomic`.

«Удалить» в расширении означает штатную отмену с сохранением истории и связи.

Статические вызовы: `AvitoBrowserOrder.objects.select_related`, `AvitoBrowserOrder.objects.select_related('sale').get`, `PermissionDenied`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `actor.has_perm`, `can_view`, `cancel_sale`, `comment.strip`, `data.get`, `isinstance`, `len`, `order_id`, `sale.updated_at.isoformat`, `summary`.

## `sales/avito_shipping.py`

Оригинальный символ Avito на этикетке 58×40; печать не меняет статусы продажи.

Импорты: `PIL`, `avito_orders`, `barcode`, `barcode.writer`, `core.external_policy`, `datetime`, `django.conf`, `django.core.exceptions`, `django.core.files.base`, `django.db`, `django.utils`, `io`, `label_printing`, `market_fulfillment`, `models`, `pathlib`, `print_agents`.

### `label_pdf(encoded, carrier)`

Исходник: `sales/avito_shipping.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BytesIO`, `Image.open`, `Path`, `ValidationError`, `base64.b64decode`, `carrier.strip`, `clean.getvalue`, `doc.new_page`, `doc.tobytes`, `image.convert`, `image.convert('RGB').save`, `isinstance`, `len`, `max`, `min`, `page.insert_font`, `page.insert_image`, `page.insert_textbox`, `pymupdf.Font`, `pymupdf.Font(fontfile=str(font)).text_length`, `pymupdf.Rect`, `pymupdf.open`, `str`.

### `check_actor(actor)`

Исходник: `sales/avito_shipping.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `actor.has_perm`.

### `request_label(*, actor, data)`

Исходник: `sales/avito_shipping.py:62`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoShippingPrintJob`, `AvitoShippingPrintJob.objects.filter`, `AvitoShippingPrintJob.objects.filter(request_id=key).first`, `BytesIO`, `Code128`, `Code128(content, writer=ImageWriter()).write`, `ContentFile`, `ImageWriter`, `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(request_id=key).exists`, `ValidationError`, `_printer_target`, `base64.b64encode`, `base64.b64encode(output.getvalue()).decode`, `check_actor`, `content.encode`, `data.get`, `data['order'].get`, `hashlib.sha256`, `hashlib.sha256(pdf).hexdigest`, `isinstance`, `job.file.save`, `job.save`, `label_pdf`, `len`, `order.print_jobs.exclude`, `order.print_jobs.exclude(state__in=['done', 'error']).first`, `output.getvalue`, `prepare_order`, `qr.add_data`, `qr.make`, `qr.make_image`, `qr.make_image(fill_color='black', back_color='white').save`, `qrcode.QRCode`, `re.fullmatch`, `require_live_operation`, `str`, `str(data['order'].get('carrier', '')).strip`, `symbol.get`, `uuid.UUID`.

### `process_jobs(stop=None)`

Исходник: `sales/avito_shipping.py:116`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoShippingPrintJob.objects.filter`, `AvitoShippingPrintJob.objects.filter(print_backend='native', state__in=['pending', 'spooled']).values_list`, `AvitoShippingPrintJob.objects.select_for_update`, `AvitoShippingPrintJob.objects.select_for_update().get`, `check_actor`, `file.read`, `getattr`, `job.file.open`, `job.save`, `list`, `logging.getLogger`, `logging.getLogger('gamebat.business').warning`, `print_job_completed`, `print_pdf`, `release_print_job`, `require_live_operation`, `stop.is_set`, `str`, `timedelta`, `timezone.now`, `transaction.atomic`.

### `agent_claim(agent, instance)`

Исходник: `sales/avito_shipping.py:166`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoShippingPrintJob.objects.select_for_update`, `AvitoShippingPrintJob.objects.select_for_update().filter`, `_session`, `check_actor`, `job.save`, `jobs.filter`, `jobs.filter(state='agent_waiting').order_by`, `jobs.filter(state='agent_waiting').order_by('pk').first`, `jobs.filter(state__in=AGENT_ACTIVE).order_by`, `jobs.filter(state__in=AGENT_ACTIVE).order_by('pk').first`, `old.save`, `str`, `timedelta`, `timezone.now`, `uuid.uuid4`.

### `agent_owned(agent_id, instance, request_id, lock=False)`

Исходник: `sales/avito_shipping.py:185`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `AvitoShippingPrintJob.objects.select_for_update`, `PrintAgent.objects.get`, `_session`, `check_actor`, `qs.filter`, `qs.filter(request_id=request_id, agent=agent, print_backend='agent').first`.

### `agent_result(agent_id, instance, request_id, data)`

Исходник: `sales/avito_shipping.py:199`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `PrintAgent.objects.select_for_update`, `PrintAgent.objects.select_for_update().get`, `agent_owned`, `data.get`, `job.save`, `str`, `timedelta`, `timezone.now`, `type`.

## `sales/commissions.py`

Decimal-расчёт комиссии Avito по строке; комиссия не уменьшает фактически полученную наличную оплату.

Импорты: `decimal`.

### `calculate_avito_commission(line_total, *, enabled)`

Исходник: `sales/commissions.py:11`.

Рассчитать денежный снимок комиссии по итоговой сумме строки.

Статические вызовы: `Decimal`, `amount.quantize`, `max`.

## `sales/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `django`, `models`, `partners.customers`, `warehouse.form_defaults`, `warehouse.models`.

### `SaleCreateForm.__init__(self, *args, imported_wholesale=False, imported_report=False, **kwargs)`

Исходник: `sales/forms.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.initial.get`, `self.order_fields`, `super`, `super().__init__`.

### `SaleCreateForm.clean(self)`

Исходник: `sales/forms.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `cleaned.get`, `self.add_error`, `super`, `super().clean`.

## `sales/invoice_excel.py`

Накладная XLSX по структуре и цветам прежнего sales/invoice.html.

Импорты: `core.excel_layout`, `django.utils`, `io`, `math`, `openpyxl`, `openpyxl.cell.cell`, `openpyxl.styles`, `openpyxl.worksheet.page`, `openpyxl.worksheet.pagebreak`.

### `_text(cell, value)`

Исходник: `sales/invoice_excel.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ILLEGAL_CHARACTERS_RE.sub`, `str`.

### `_height(value, width, *, size=12, bold=False, padding=12, minimum=28)`

Исходник: `sales/invoice_excel.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `wrapped_text_height`.

### `_page_breaks(sheet, last_item, total_row, widths)`

Исходник: `sales/invoice_excel.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Break`, `column_width_pixels`, `min`, `range`, `sheet.row_breaks.append`, `sum`.

### `render_sale_invoice_xlsx(*, sale, rows)`

Исходник: `sales/invoice_excel.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Alignment`, `Border`, `BytesIO`, `Font`, `PageMargins`, `PatternFill`, `Side`, `Workbook`, `_height`, `_page_breaks`, `_text`, `book.close`, `book.save`, `ceil`, `enumerate`, `isinstance`, `max`, `output.getvalue`, `range`, `sheet.cell`, `sheet.merge_cells`, `sum`, `table_cell`, `text_width_pixels`, `timezone.localtime`, `timezone.localtime(sale.created_at).strftime`, `values.append`, `zip`.

## `sales/label_printing.py`

Печать официального PDF 58×40 мм на локальный принтер Windows без диалогов.

Импорты: `PIL`, `contextlib`, `core.external_policy`, `django.conf`, `django.core.exceptions`, `pathlib`.

### `printer_configuration()`

Исходник: `sales/label_printing.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `Path(settings.LABEL_PRINTER_CONFIG_PATH).read_text`, `ValidationError`, `isinstance`, `json.loads`, `len`, `name.strip`, `require_live_operation`.

### `render_label_pages(data, *, dpi)`

Исходник: `sales/label_printing.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Image.frombytes`, `ValidationError`, `abs`, `data.startswith`, `len`, `page.get_pixmap`, `pages.append`, `pymupdf.open`.

### `_windows_printer(name)`

Исходник: `sales/label_printing.py:47`.

Декораторы: `contextmanager`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `abs`, `dc.DeleteDC`, `dc.GetDeviceCaps`, `require_live_operation`, `win32gui.CreateDC`, `win32print.ClosePrinter`, `win32print.DocumentProperties`, `win32print.GetPrinter`, `win32print.OpenPrinter`, `win32ui.CreateDCFromHandle`.

### `print_pdf(data, *, printer_name, title)`

Исходник: `sales/label_printing.py:81`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ImageWin.Dib`, `ImageWin.Dib(page).draw`, `ValidationError`, `_control_job`, `_start_document`, `_windows_printer`, `dc.AbortDoc`, `dc.EndDoc`, `dc.EndPage`, `dc.GetDeviceCaps`, `dc.GetHandleOutput`, `dc.StartPage`, `min`, `render_label_pages`, `require_live_operation`, `round`.

### `_start_document(dc, title)`

Исходник: `sales/label_printing.py:106`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `dc.GetHandleOutput`, `require_live_operation`, `win32print.StartDoc`.

### `_control_job(printer_name, job_id, command)`

Исходник: `sales/label_printing.py:113`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `require_live_operation`, `win32print.ClosePrinter`, `win32print.OpenPrinter`, `win32print.SetJob`.

### `_printer_job_info(printer_name, job_id)`

Исходник: `sales/label_printing.py:123`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `require_live_operation`, `win32print.ClosePrinter`, `win32print.GetJob`, `win32print.OpenPrinter`.

### `print_job_completed(printer_name, job_id, *, expected_title=None)`

Исходник: `sales/label_printing.py:133`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_printer_job_info`, `bool`, `info.get`, `require_live_operation`.

### `release_print_job(printer_name, job_id, *, expected_title=None)`

Исходник: `sales/label_printing.py:155`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_control_job`, `_printer_job_info`, `_printer_job_info(printer_name, job_id).get`.

## `sales/listing.py`

Общие выборки списков и данные интерфейса; переходы выполняет sales.services.

Импорты: `django.core.paginator`, `itertools`, `market_controls`, `models`, `services`.

### `sales_queryset()`

Исходник: `sales/listing.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.objects.select_related`, `Sale.objects.select_related('warehouse', 'created_by', 'cancelled_by', 'consignment_platform').prefetch_related`, `with_market_controls`.

### `_items_preview(sale)`

Исходник: `sales/listing.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `chain.from_iterable`, `islice`, `len`, `list`, `sale._related_items`, `sorted`.

### `status_context(sale, user, editable=True)`

Исходник: `sales/listing.py:33`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.OrderStatus`, `_items_preview`, `can_mark_paid`, `market_context`, `next_order_status`, `sale.updated_at.isoformat`, `user.has_perm`.

### `list_groups(request, state)`

Исходник: `sales/listing.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Paginator`, `Paginator(queryset.filter(sale_type__in=sale_types), 50).get_page`, `dict`, `groups.append`, `kinds.append`, `page.has_next`, `page.has_previous`, `page.next_page_number`, `page.previous_page_number`, `page_url`, `params.urlencode`, `queryset.exclude`, `queryset.filter`, `request.GET.copy`, `request.GET.get`, `sales_queryset`, `status_context`, `{'completed': 1, 'cancelled': 2}.get`.

## `sales/management/commands/register_print_agent.py`

Регистрация администратором: stdin содержит только публичный хеш, не токен.

Импорты: `core.external_policy`, `django.core.management.base`, `django.db`, `sales.models`.

### `Command.add_arguments(self, parser)`

Исходник: `sales/management/commands/register_print_agent.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `sales/management/commands/register_print_agent.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CommandError`, `MarketPrintJob.objects.filter`, `PrintAgent`, `PrintAgent.objects.select_for_update`, `PrintAgent.objects.select_for_update().filter`, `PrintAgent.objects.select_for_update().filter(pk=agent_id).first`, `PrintAgent.objects.select_for_update().get`, `agent.save`, `isinstance`, `job.save`, `json.loads`, `len`, `options.get`, `re.fullmatch`, `require_live_operation`, `self.stdout.write`, `str`, `sys.stdin.read`, `transaction.atomic`, `uuid.UUID`.

## `sales/management/commands/run_label_print_worker.py`

Windows-исполнитель печати ярлыков. Подтверждённая печать отделена от постановки задания/готовности FBS.

Импорты: `django.core.management.base`, `django.db`, `integrations.worker_heartbeat`, `integrations.worker_runtime`, `sales.avito_shipping`, `sales.market_fulfillment`.

### `Command.add_arguments(self, parser)`

Исходник: `sales/management/commands/run_label_print_worker.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `sales/management/commands/run_label_print_worker.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `close_old_connections`, `connections.close_all`, `graceful_shutdown`, `monitored_worker`, `process_jobs`, `process_print_jobs`, `self.stdout.write`, `stop.is_set`, `stop.wait`.

## `sales/market_controls.py`

Данные для управления связанным заказом Маркета из карточки и списка продаж.

Импорты: `django.db.models`, `models`, `notifications`, `yandex_market.models`, `yandex_market.orders`.

### `with_market_controls(queryset)`

Исходник: `sales/market_controls.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Exists`, `LabelDocument.objects.filter`, `LabelDocument.objects.filter(box_id__isnull=True, shipment_id__isnull=True).order_by`, `MarketPrintJob.objects.filter`, `OuterRef`, `Prefetch`, `SyncJob.objects.filter`, `SyncJob.objects.filter(kind__in=['order', 'order_action', 'boxes']).order_by`, `queryset.annotate`, `queryset.annotate(has_market_label_printed=Exists(MarketPrintJob.objects.filter(order_id=OuterRef('yandex_order__pk'), printed_at__isnull=False))).select_related`, `queryset.annotate(has_market_label_printed=Exists(MarketPrintJob.objects.filter(order_id=OuterRef('yandex_order__pk'), printed_at__isnull=False))).select_related('yandex_order__integration', 'yandex_order__staff_attention').prefetch_related`.

### `market_status_label(order)`

Исходник: `sales/market_controls.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `labels.get`.

### `market_context(sale, user, *, editable=True)`

Исходник: `sales/market_controls.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `actions.pop`, `available_actions`, `available_actions(order).copy`, `bool`, `can_acknowledge`, `getattr`, `job.payload.get`, `market_status_label`, `next`, `user.has_perm`.

## `sales/market_fulfillment.py`

Сборка сканером и последовательность PDF → Windows → готовность Маркета.

Импорты: `catalog.models`, `collections`, `core.external_policy`, `datetime`, `django.conf`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `label_printing`, `models`, `print_agents`, `yandex_market.documents`, `yandex_market.models`, `yandex_market.orders`, `yandex_market.services`.

### `_printer_target()`

Исходник: `sales/market_fulfillment.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `configured_agent`, `getattr`, `printer_configuration`, `require_live_operation`.

### `_uuid(value)`

Исходник: `sales/market_fulfillment.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `str`, `uuid.UUID`.

### `_check_actor(actor, *, scanning=False)`

Исходник: `sales/market_fulfillment.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `actor.has_perm`, `all`.

### `required_items(order)`

Исходник: `sales/market_fulfillment.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `defaultdict`, `dict`, `order.lines.select_related`, `order.sale.cd_items.all`, `order.sale.custom_items.exists`, `order.sale.tech_items.all`, `sale_items.update`.

### `record_scan(*, actor, barcode, request_id)`

Исходник: `sales/market_fulfillment.py:70`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BarcodeRegistry.objects.filter`, `BarcodeRegistry.objects.filter(value=barcode).first`, `F`, `F('created_remote_at').asc`, `MarketPicking.objects.get_or_create`, `MarketPrintJob.objects.create`, `MarketScanEvent.objects.create`, `MarketScanEvent.objects.filter`, `MarketScanEvent.objects.filter(request_id=request_id).first`, `OrderMetadata.objects.select_related`, `OrderMetadata.objects.select_related('sale', 'integration').filter`, `OrderMetadata.objects.select_related('sale', 'integration').filter(**lookup, status='PROCESSING', substatus='STARTED', fake=False, integration__enabled=True, sale__cancelled_at__isnull=True, sale__sale_type='yandex_market').exclude`, `OrderMetadata.objects.select_related('sale', 'integration').filter(**lookup, status='PROCESSING', substatus='STARTED', fake=False, integration__enabled=True, sale__cancelled_at__isnull=True, sale__sale_type='yandex_market').exclude(sale__order_status='delivered', sale__payment_status='paid').exclude`, `OrderMetadata.objects.select_related('sale', 'integration').filter(**lookup, status='PROCESSING', substatus='STARTED', fake=False, integration__enabled=True, sale__cancelled_at__isnull=True, sale__sale_type='yandex_market').exclude(sale__order_status='delivered', sale__payment_status='paid').exclude(print_jobs__ready_after_print=True).distinct`, `OrderMetadata.objects.select_related('sale', 'integration').filter(**lookup, status='PROCESSING', substatus='STARTED', fake=False, integration__enabled=True, sale__cancelled_at__isnull=True, sale__sale_type='yandex_market').exclude(sale__order_status='delivered', sale__payment_status='paid').exclude(print_jobs__ready_after_print=True).distinct().order_by`, `ValidationError`, `_check_actor`, `_printer_target`, `_uuid`, `all`, `audit`, `event.save`, `len`, `picking.save`, `picking.scanned.get`, `picking.scanned.values`, `required.get`, `required.items`, `required.values`, `required_items`, `str`, `str(barcode or '').strip`, `sum`, `timezone.now`, `transaction.atomic`.

### `request_print(*, order, actor, request_id)`

Исходник: `sales/market_fulfillment.py:124`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(order=order).exclude`, `MarketPrintJob.objects.filter(order=order).exclude(state__in=['done', 'error']).exists`, `MarketPrintJob.objects.filter(request_id=_uuid(request_id)).first`, `MarketPrintJob.objects.get_or_create`, `OrderMetadata.objects.select_for_update`, `OrderMetadata.objects.select_for_update().get`, `ValidationError`, `_check_actor`, `_printer_target`, `_uuid`, `transaction.atomic`.

### `_save(job, *fields)`

Исходник: `sales/market_fulfillment.py:145`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `job.save`.

### `_finished(sync_job)`

Исходник: `sales/market_fulfillment.py:149`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_step(job)`

Исходник: `sales/market_fulfillment.py:155`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(pk=job.pk, lease=job.lease, state='printing').exists`, `ValidationError`, `_check_actor`, `_finished`, `_save`, `any`, `audit`, `data.startswith`, `expire_job`, `hashlib.sha256`, `hashlib.sha256(data).hexdigest`, `job.document.file.open`, `len`, `logger.warning`, `picking.scanned.get`, `print_job_completed`, `print_pdf`, `release_print_job`, `request_labels`, `request_order_action`, `required.items`, `required_items`, `source.read`, `timedelta`, `timezone.now`, `transaction.atomic`, `type`.

### `process_print_jobs(*, limit=50, stop=None)`

Исходник: `sales/market_fulfillment.py:253`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(pk=pk, lease=lease).exclude`, `MarketPrintJob.objects.filter(pk=pk, lease=lease).exclude(state='printing').update`, `MarketPrintJob.objects.filter(pk=pk, lease__isnull=True).exclude`, `MarketPrintJob.objects.filter(pk=pk, lease__isnull=True).exclude(state__in=['done', 'error', 'uncertain']).update`, `MarketPrintJob.objects.filter(pk=pk, state='printing').exists`, `MarketPrintJob.objects.select_related`, `MarketPrintJob.objects.select_related('order__sale', 'order__integration', 'actor', 'document', 'refresh_job', 'boxes_job', 'ready_job').get`, `Q`, `_save`, `_step`, `active.values_list`, `getattr`, `isinstance`, `jobs.exclude`, `jobs.exclude(state__in=['done', 'error', 'uncertain', 'printing']).filter`, `jobs.exclude(state__in=['done', 'error', 'uncertain', 'printing']).filter(lease__isnull=True).order_by`, `jobs.filter`, `jobs.filter(state='printing', lease__isnull=True).update`, `list`, `stale.exclude`, `stale.exclude(state='printing').update`, `stale.filter`, `stale.filter(state='printing').update`, `stop.is_set`, `timedelta`, `timezone.now`, `uuid.uuid4`.

## `sales/market_views.py`

Разрешённые операции Маркета из продажи; отправку выполняет существующий worker.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.urls`, `django.views.decorators.cache`, `django.views.decorators.http`, `market_controls`, `market_fulfillment`, `models`, `print_agents`, `yandex_market.documents`, `yandex_market.models`, `yandex_market.orders`.

### `_back(request, sale_id)`

Исходник: `sales/market_views.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `redirect`, `request.POST.get`, `request.user.has_perm`.

### `_confirm(request)`

Исходник: `sales/market_views.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `request.POST.get`.

### `sale_market_action(request, pk)`

Исходник: `sales/market_views.py:36`.

Декораторы: `require_POST`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.manage_orders')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(order=order, printed_at__isnull=False).exists`, `OrderMetadata.objects.select_related`, `ValidationError`, `_back`, `_confirm`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `request.POST.get`, `request_order_action`.

### `sale_market_label(request, pk)`

Исходник: `sales/market_views.py:62`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `OrderMetadata.objects.select_related`, `ValidationError`, `_label_response`, `get_object_or_404`, `permission_required_any`, `request_labels`.

### `_label_response(document, sale_id)`

Исходник: `sales/market_views.py:76`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `data.update`, `reverse`.

### `sale_market_label_status(request, pk, document_id)`

Исходник: `sales/market_views.py:90`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_label_response`, `get_object_or_404`, `permission_required_any`.

### `_print_response(job)`

Исходник: `sales/market_views.py:95`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `available_actions`, `bool`, `list`, `market_status_label`, `messages_by_state.get`, `reverse`, `str`.

### `sale_market_scan(request)`

Исходник: `sales/market_views.py:119`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales')`; `permission_required_any('yandex_market.print_labels')`; `permission_required_any('yandex_market.manage_orders')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `permission_required_any`, `record_scan`, `request.POST.get`, `result.get`, `reverse`.

### `sale_market_print(request, pk)`

Исходник: `sales/market_views.py:135`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `OrderMetadata.objects.select_related`, `_print_response`, `get_object_or_404`, `permission_required_any`, `request.POST.get`, `request_print`.

### `sale_market_print_status(request, request_id)`

Исходник: `sales/market_views.py:150`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `MarketPrintJob.objects.select_related`, `_print_response`, `get_object_or_404`, `permission_required_any`.

### `print_resolve(request, request_id)`

Исходник: `sales/market_views.py:157`.

Декораторы: `require_POST`; `permission_required_any('yandex_market.print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ValidationError`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `resolve`.

## `sales/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `avito_order_models`, `catalog.models`, `decimal`, `django.conf`, `django.core.exceptions`, `django.core.validators`, `django.db`, `django.utils`, `orders.arrival`, `partners.models`, `print_agent_models`, `warehouse.models`.

### `temporary_sale_id()`

Исходник: `sales/models.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `uuid.uuid4`.

### `Sale.PaymentMethod.is_cash_payment(self)`

Исходник: `sales/models.py:59`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.PaymentMethod.is_bank_payment(self)`

Исходник: `sales/models.py:63`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.PaymentMethod.is_postpayment(self)`

Исходник: `sales/models.py:67`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.is_partner_debt(self)`

Исходник: `sales/models.py:235`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.debt_charge_amount(self)`

Исходник: `sales/models.py:239`.

Декораторы: `property`.

Новый долг из сохранённых сумм продажи, без пересчёта по текущему балансу партнёра.

Статические вызовы: `Decimal`, `max`.

### `Sale.get_payment_status_display(self)`

Исходник: `sales/models.py:247`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.PaymentStatus`.

### `Sale.is_cash_payment(self)`

Исходник: `sales/models.py:253`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.PaymentMethod`.

### `Sale.is_bank_payment(self)`

Исходник: `sales/models.py:257`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.PaymentMethod`.

### `Sale.is_postpayment(self)`

Исходник: `sales/models.py:261`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.PaymentMethod`.

### `Sale.can_select_payment_partner(self)`

Исходник: `sales/models.py:265`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.is_completed(self)`

Исходник: `sales/models.py:273`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.storefront_source_label(self)`

Исходник: `sales/models.py:281`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `{'resource_storefront': 'Оптовый сайт', 'resource_retail': 'Розничный сайт'}.get`.

### `Sale.buyer_contact_methods_label(self)`

Исходник: `sales/models.py:285`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `labels.get`.

### `Sale.is_cancelled(self)`

Исходник: `sales/models.py:290`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.is_postpay_editable(self)`

Исходник: `sales/models.py:294`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `hasattr`.

### `Sale.position_count(self)`

Исходник: `sales/models.py:304`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `self._related_items`, `sum`.

### `Sale.total_units(self)`

Исходник: `sales/models.py:312`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._related_items`, `sum`.

### `Sale._related_items(self, name)`

Исходник: `sales/models.py:319`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `getattr(self, '_prefetched_objects_cache', {}).get`, `getattr(self, name).all`.

### `Sale.__str__(self)`

Исходник: `sales/models.py:323`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Sale.save(self, *args, **kwargs)`

Исходник: `sales/models.py:326`.

Разрешает только одно служебное преобразование TMP-id в постоянный номер продажи.

Статические вызовы: `ValidationError`, `assert_document_finalized`, `stored_id.startswith`, `str`, `str(self.note or '').strip`, `super`, `super().save`, `type`, `type(self).objects.filter`, `type(self).objects.filter(pk=self.pk).values`, `type(self).objects.filter(pk=self.pk).values('visible_id', 'completed_at', 'direct_delivery', 'procurement_prepaid_amount').first`.

### `SaleItemBase.effective_unit_price(self)`

Исходник: `sales/models.py:374`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SaleItemBase.price_adjustment_display(self)`

Исходник: `sales/models.py:378`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `abs`.

### `SaleItemBase.revenue_after_avito_commission(self)`

Исходник: `sales/models.py:383`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SaleItemBase.save(self, *args, **kwargs)`

Исходник: `sales/models.py:386`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `getattr`, `super`, `super().save`, `type`, `type(self).objects.filter`, `type(self).objects.filter(pk=self.pk).values`, `type(self).objects.filter(pk=self.pk).values('unit_cost_snapshot', 'avito_commission_enabled', 'avito_commission_amount', 'sale__completed_at', 'is_direct_delivery', 'trip_cost_row_id', 'trip_cost_slot').first`.

### `SaleCustomItem.clean(self)`

Исходник: `sales/models.py:469`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `super`, `super().clean`.

### `SaleCustomItem.save(self, *args, **kwargs)`

Исходник: `sales/models.py:481`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `getattr`, `self.clean`, `super`, `super().save`, `type`, `type(self).objects.filter`, `type(self).objects.filter(pk=self.pk, sale__completed_at__isnull=False).values`, `type(self).objects.filter(pk=self.pk, sale__completed_at__isnull=False).values('unit_price', 'quantity', 'line_total', 'system_product_id').first`.

### `SaleConsignmentItem.product(self)`

Исходник: `sales/models.py:566`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `sales/notification_views.py`

Закрытые endpoints внутреннего подтверждения; API Маркета не вызывается.

Импорты: `core.decorators`, `django.db`, `django.http`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.http`, `models`, `notifications`.

### `pending_orders(request)`

Исходник: `sales/notification_views.py:20`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `can_acknowledge`, `pending_attention`, `permission_required_any`, `render`.

### `notification_status(request)`

Исходник: `sales/notification_views.py:29`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `attention_snapshot`, `logger.exception`, `permission_required_any`.

### `acknowledge(request, attention_id)`

Исходник: `sales/notification_views.py:40`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all('sales.view_sales', 'yandex_market.manage_orders')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Http404`, `JsonResponse`, `acknowledge_order`, `attention_snapshot`, `logger.exception`, `permission_required_all`, `record.acknowledged_at.isoformat`.

## `sales/notifications.py`

Внутреннее подтверждение внимания сотрудника без изменения статусов заказа.

Импорты: `django.core.exceptions`, `django.db`, `django.urls`, `django.utils`, `models`, `yandex_market.services`.

### `can_acknowledge(user)`

Исходник: `sales/notifications.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `user.has_perm`.

### `pending_attention()`

Исходник: `sales/notifications.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketOrderAttention.objects.filter`, `MarketOrderAttention.objects.filter(acknowledged_at__isnull=True).select_related`, `MarketOrderAttention.objects.filter(acknowledged_at__isnull=True).select_related('order__sale', 'order__integration').order_by`.

### `require_staff_acknowledgement(order)`

Исходник: `sales/notifications.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketOrderAttention.objects.get_or_create`, `ValidationError`, `audit`, `logger.info`.

### `attention_snapshot(user)`

Исходник: `sales/notifications.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `can_acknowledge`, `len`, `pending_attention`, `reverse`, `row.notification_started_at.isoformat`, `str`, `timezone.now`, `timezone.now().isoformat`, `user.has_perm`.

### `acknowledge_order(*, actor, attention_id)`

Исходник: `sales/notifications.py:50`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketOrderAttention.objects.filter`, `MarketOrderAttention.objects.filter(pk=attention_id, acknowledged_at__isnull=True).update`, `MarketOrderAttention.objects.select_related`, `MarketOrderAttention.objects.select_related('order__integration', 'acknowledged_by').get`, `audit`, `can_acknowledge`, `logger.info`, `record.acknowledged_at.isoformat`, `timezone.now`.

## `sales/partner_payments.py`

Расчёты партнёра через существующий кредиторский журнал, без повторной кассовой проводки.

Импорты: `creditors.models`, `decimal`, `django.core`, `django.core.exceptions`, `django.db`, `models`, `partners.models`.

### `resolve_payment_partner(sale, partner_id)`

Исходник: `sales/partner_payments.py:12`.

Явный выбор счёта при оплате; текстовое имя не связывает партнёров автоматически.

Статические вызовы: `Partner.objects.get`, `ValidationError`, `int`, `len`, `str`, `text.isascii`, `text.isdecimal`.

### `payment_partner_choices()`

Исходник: `sales/partner_payments.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Partner.objects.filter`, `Partner.objects.filter(is_archived=False).order_by`, `Partner.objects.filter(is_archived=False).order_by('name', 'pk').only`.

### `money(value)`

Исходник: `sales/partner_payments.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `ValueError`, `amount.is_finite`, `str`.

### `quote(*, total, received, debt, partner_id, sale_id=None, creation_key=None)`

Исходник: `sales/partner_payments.py:47`.

Чистый Decimal-предпросмотр: сначала погашение/взаимозачёт существующего знакового долга, затем новый долг/переплата. Сам денег и записей не создаёт.

Статические вызовы: `Decimal`, `Decimal(str(debt)).quantize`, `max`, `min`, `money`, `str`.

### `payment_values(*, actor, sale_type, partner, total, received, note, confirmation='', sale_id=None, creation_key=None)`

Исходник: `sales/partner_payments.py:63`.

Повторно рассчитывает платёж под блокировкой кредитора и сверяет подписанное подтверждение. Обычная частичная оплата требует Partner/опта/права/примечания.

Статические вызовы: `Creditor.objects.select_for_update`, `Creditor.objects.select_for_update().get`, `Decimal`, `PermissionDenied`, `ValidationError`, `actor.has_perm`, `max`, `money`, `quote`, `signing.loads`, `str`, `str(note or '').strip`.

### `record_settlement(*, sale, actor)`

Исходник: `sales/partner_payments.py:92`.

Декораторы: `transaction.atomic`.

Записывает единственную долговую дельту продажи без второй кассовой проводки. partner_debt — отдельная ветка полного начисления T.

Статические вызовы: `Creditor.objects.select_for_update`, `Creditor.objects.select_for_update().get`, `CreditorTransaction.objects.create`, `CreditorTransaction.objects.filter`, `CreditorTransaction.objects.filter(operation_key=key).exists`, `PermissionDenied`, `ValidationError`, `actor.has_perm`, `creditor.full_clean`, `creditor.save`.

### `reverse_settlement(*, sale, actor, comment)`

Исходник: `sales/partner_payments.py:121`.

Декораторы: `transaction.atomic`.

Сторнирует дельту своей продажи относительно текущего баланса, сохраняя последующие оплаты и коррекции других операций.

Статические вызовы: `Creditor.objects.select_for_update`, `Creditor.objects.select_for_update().get`, `CreditorTransaction.objects.create`, `CreditorTransaction.objects.filter`, `CreditorTransaction.objects.filter(reversal_of=original).exists`, `PermissionDenied`, `actor.has_perm`, `creditor.save`, `sale.creditor_movements.filter`, `sale.creditor_movements.filter(reversal_of__isnull=True).first`.

## `sales/partner_statistics.py`

Единая лента продаж и движений долга для HTML и Excel; выручка считается прежним сервисом.

Импорты: `cash.models`, `creditors.models`, `dataclasses`, `decimal`, `django.db.models`.

### `financial_operations(filters, sales)`

Исходник: `sales/partner_statistics.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CashTransaction.objects.filter`, `CashTransaction.objects.filter(customer_order__isnull=False).select_related`, `CreditorTransaction.objects.select_related`, `FinancialOperation`, `Q`, `all`, `any`, `cash_entries.filter`, `cash_entries.none`, `entry.get_kind_display`, `entry.get_operation_type_display`, `filters.get`, `getattr`, `min`, `operations.append`, `query.filter`, `query.none`, `query.order_by`, `sale.get_operation_kind_display`, `sorted`, `sources.append`.

## `sales/partner_views.py`

Предпросмотр подтверждения: суммы подписаны и заново сверяются при проведении.

Импорты: `core.decorators`, `decimal`, `django.core`, `django.core.exceptions`, `django.http`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.http`, `models`, `partner_payments`, `partners.models`.

### `settlement_preview(request)`

Исходник: `sales/partner_views.py:18`.

Декораторы: `never_cache`; `require_POST`; `permission_required_any('sales.create_sale', 'sales.mark_sale_paid')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Decimal`, `JsonResponse`, `any`, `get_object_or_404`, `int`, `partner_id.isdecimal`, `permission_required_any`, `quote`, `request.POST.get`, `request.user.has_perm`, `resolve_payment_partner`, `sale_id.isdecimal`, `signing.dumps`.

## `sales/print_agent_models.py`

Отдельная идентичность локального устройства печати, без прав пользователя CRM.

Импорты: `django.db`.

### `PrintAgent.__str__(self)`

Исходник: `sales/print_agent_models.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `sales/print_agent_urls.py`

Фиксированный протокол исходящих запросов магазинного агента.

Импорты: `django.urls`.

## `sales/print_agent_views.py`

Machine API: только отдельный Bearer, без cookie-аутентификации и CORS.

Импорты: `avito_shipping`, `core.external_policy`, `django.conf`, `django.core.exceptions`, `django.db`, `django.http`, `django.views.decorators.cache`, `django.views.decorators.csrf`, `django.views.decorators.http`, `functools`, `models`, `urllib.parse`.

### `agent_api(method)`

Исходник: `sales/print_agent_views.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `PrintAgent.objects.filter`, `PrintAgent.objects.filter(pk=agent_id, enabled=True).first`, `auth.startswith`, `function`, `getattr`, `hashlib.sha256`, `hashlib.sha256(token.encode()).hexdigest`, `hmac.compare_digest`, `isinstance`, `json.loads`, `len`, `request.get_host`, `request.headers.get`, `request.is_secure`, `require_http_methods`, `require_live_operation`, `service.AgentError`, `token.encode`, `urlsplit`, `uuid.UUID`, `wraps`.

### `heartbeat(request, agent_id, instance, data)`

Исходник: `sales/print_agent_views.py:75`.

Декораторы: `agent_api('POST')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `agent_api`, `service.heartbeat`.

### `claim(request, agent_id, instance, data)`

Исходник: `sales/print_agent_views.py:80`.

Декораторы: `agent_api('POST')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `agent_api`, `service.claim`.

### `result(request, agent_id, instance, data, request_id)`

Исходник: `sales/print_agent_views.py:85`.

Декораторы: `agent_api('POST')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoShippingPrintJob.objects.filter`, `AvitoShippingPrintJob.objects.filter(request_id=request_id).exists`, `JsonResponse`, `agent_api`, `agent_result`, `service.result`.

### `document(request, agent_id, instance, data, request_id)`

Исходник: `sales/print_agent_views.py:94`.

Декораторы: `agent_api('GET')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AvitoShippingPrintJob.objects.filter`, `AvitoShippingPrintJob.objects.filter(request_id=request_id).exists`, `FileResponse`, `agent_api`, `agent_owned`, `job.document.file.open`, `job.file.open`, `service.AgentError`, `service.owned_job`.

## `sales/print_agents.py`

Атомарные назначения агенту; HTTP/Windows никогда не вызываются внутри транзакции.

Импорты: `avito_shipping`, `core.external_policy`, `datetime`, `django.conf`, `django.core.exceptions`, `django.db`, `django.utils`, `market_fulfillment`, `models`, `yandex_market.services`.

### `AgentError.__init__(self, code, status=409)`

Исходник: `sales/print_agents.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `configured_agent()`

Исходник: `sales/print_agents.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PrintAgent.objects.filter`, `ValidationError`, `getattr`, `len`, `list`, `query.filter`, `require_live_operation`, `str`, `uuid.UUID`.

### `_session(agent, instance)`

Исходник: `sales/print_agents.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `timedelta`, `timezone.now`.

### `heartbeat(agent_id, instance, data)`

Исходник: `sales/print_agents.py:43`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `PrintAgent.objects.select_for_update`, `PrintAgent.objects.select_for_update().get`, `agent.save`, `data.get`, `isinstance`, `len`, `timedelta`, `timezone.now`, `type`, `uuid.uuid4`.

### `_audit(job, action, **details)`

Исходник: `sales/print_agents.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `audit`, `str`.

### `_expire(job, now)`

Исходник: `sales/print_agents.py:70`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_audit`, `job.save`, `timedelta`.

### `expire_job(pk)`

Исходник: `sales/print_agents.py:86`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.select_for_update`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related('agent', 'order', 'actor').get`, `_expire`, `timezone.now`.

### `claim(agent_id, instance)`

Исходник: `sales/print_agents.py:92`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.filter`, `MarketPrintJob.objects.filter(agent=agent, print_backend='agent', state__in=AGENT_ACTIVE).order_by`, `MarketPrintJob.objects.filter(agent=agent, print_backend='agent', state__in=AGENT_ACTIVE).order_by('pk').first`, `MarketPrintJob.objects.select_for_update`, `MarketPrintJob.objects.select_for_update().filter`, `MarketPrintJob.objects.select_for_update().filter(agent=agent, print_backend='agent', state='agent_waiting').order_by`, `MarketPrintJob.objects.select_for_update().filter(agent=agent, print_backend='agent', state='agent_waiting').order_by('pk').first`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related('agent', 'order', 'actor').filter`, `PrintAgent.objects.select_for_update`, `PrintAgent.objects.select_for_update().get`, `_audit`, `_expire`, `_session`, `agent_claim`, `job.save`, `str`, `timezone.now`, `uuid.uuid4`.

### `owned_job(agent_id, instance, request_id, *, lock=False)`

Исходник: `sales/print_agents.py:114`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `MarketPrintJob.objects.select_related`, `PrintAgent.objects.get`, `_session`, `query.filter`, `query.filter(request_id=request_id, agent=agent, print_backend='agent').first`, `query.select_for_update`.

### `result(agent_id, instance, request_id, data)`

Исходник: `sales/print_agents.py:127`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AgentError`, `PrintAgent.objects.select_for_update`, `PrintAgent.objects.select_for_update().get`, `_audit`, `_check_actor`, `data.get`, `job.save`, `owned_job`, `str`, `timedelta`, `timezone.now`, `type`.

### `snapshot()`

Исходник: `sales/print_agents.py:174`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PrintAgent.objects.all`, `agent.marketprintjob_set.exclude`, `agent.marketprintjob_set.exclude(state__in=['done', 'error']).count`, `agents.append`, `bool`, `str`, `timedelta`, `timezone.now`.

### `resolve(request_id, actor, decision)`

Исходник: `sales/print_agents.py:188`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketPrintJob.objects.select_for_update`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related`, `MarketPrintJob.objects.select_for_update(of=('self',)).select_related('order', 'actor', 'agent').get`, `ValidationError`, `_check_actor`, `_printer_target`, `audit`, `job.save`, `target.get`, `timezone.now`.

## `sales/services.py`

Атомарные продажи, статусы, оплаты и изменение неоплаченной постоплаты.

Импорты: `cash.services`, `catalog.audit`, `catalog.models`, `collections`, `commissions`, `consignment.services`, `core.db_retry`, `dataclasses`, `decimal`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `orders.arrival`, `orders.fulfillment`, `partner_payments`, `partners.customers`, `warehouse.models`, `warehouse.services`, `warehouse.storage_services`, `warehouse.valuation`, `yandex_market.models`.

### `next_order_status(sale)`

Исходник: `sales/services.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ORDER_TRANSITIONS.get`.

### `can_mark_paid(sale)`

Исходник: `sales/services.py:39`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `document_waits_finalization`.

### `_configuration(product_type)`

Исходник: `sales/services.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_validate_choice(value, choices, message)`

Исходник: `sales/services.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_locked_inventory(warehouse_id, lines, *, direct_delivery=False)`

Исходник: `sales/services.py:70`.

Блокирует товары и локальные остатки; product lock синхронизирует продажи с пересчётом cost.

Статические вызовы: `ValidationError`, `_configuration`, `getattr`, `len`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().filter`, `product_model.objects.active().select_for_update().filter(pk__in=ids).order_by`, `products.update`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse_id=warehouse_id, **{f'{product_field}_id__in': ids}).order_by`, `stocks.update`.

### `_selected_price(product, price_type)`

Исходник: `sales/services.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `getattr`, `price.quantize`.

### `_complete_if_ready(sale)`

Исходник: `sales/services.py:105`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `timezone.now`.

### `_cash_received(value, total)`

Исходник: `sales/services.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `Decimal(str(value)).quantize`, `ValidationError`, `amount.is_finite`, `str`.

### `_commission_enabled(*, sale_type)`

Исходник: `sales/services.py:126`.

Комиссия обязательна для Avito и не зависит от переданного флага.

### `_prepare_custom_line(line, *, sale_type)`

Исходник: `sales/services.py:131`.

Проверяет ручную строку на backend и возвращает Decimal-снимки.

Статические вызовы: `((values['unit_price'] - values['unit_discount']) * quantity).quantize`, `Decimal`, `Decimal(str(raw_value)).quantize`, `ValidationError`, `_commission_enabled`, `calculate_avito_commission`, `int`, `label.capitalize`, `line.get`, `str`, `str(line.get('name') or '').strip`, `value.is_finite`, `values.update`.

### `_sale_product_lines(lines)`

Исходник: `sales/services.py:170`.

Сохраняет строки продажи; складской normalizer вызывается отдельно для каждой.

Статические вызовы: `Decimal`, `Decimal(str(source.get('unit_discount') or 0)).quantize`, `ValidationError`, `discount.is_finite`, `line.update`, `normalise_product_lines`, `prepared.append`, `source.get`, `str`, `str(source.get('line_note') or '').strip`.

### `_product_quantities(lines)`

Исходник: `sales/services.py:187`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `defaultdict`.

### `_prepare_manual_lines(lines, *, sale_type, note)`

Исходник: `sales/services.py:197`.

Определяет режим по фактическому составу, проверяя каждый входной тип.

Статические вызовы: `Decimal`, `SystemProduct.objects.in_bulk`, `ValidationError`, `_prepare_custom_line`, `abs`, `any`, `dict`, `iter`, `len`, `line.get`, `line.setdefault`, `next`, `prepared.append`, `source.get`, `str`, `str(note or '').strip`.

### `_validate_partner_debt(*, partner, sale_type, operation, total, received)`

Исходник: `sales/services.py:240`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `money`.

### `_validate_expense_received(operation, amount)`

Исходник: `sales/services.py:249`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `str`, `value.is_finite`.

### `_line_commission_flags(lines, *, sale_type)`

Исходник: `sales/services.py:259`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_commission_enabled`, `int`, `line.get`, `str`, `str(line.get('product_type') or '').lower`.

### `_commission_audit_snapshot(sale)`

Исходник: `sales/services.py:270`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `','.join`, `getattr`, `getattr(sale, relation).all`, `int`, `rows.append`, `sale.custom_items.all`.

### `create_sale(*, actor, warehouse_id, price_type, sale_type, payment_method, lines, cash_received_amount=None, note='', external_prices=None, creation_key=None, partner_id=None, partner_name='', settlement_confirmation='')`

Исходник: `sales/services.py:289`.

Декораторы: `retry_database_lock`.

Обычный доверенный вход создания продажи с блокировкой запасов, снимками и денежным расчётом. Yandex-тип запрещён: ему нужен внутренний импорт.

Статические вызовы: `ValidationError`, `_create_sale`.

### `create_market_sale(*, order, lines, external_prices)`

Исходник: `sales/services.py:304`.

Декораторы: `transaction.atomic`.

Доверенный путь импорта: настройки берутся из существующего заказа, а не HTTP.

Статические вызовы: `OrderMetadata.objects.select_for_update`, `OrderMetadata.objects.select_for_update().select_related`, `OrderMetadata.objects.select_for_update().select_related('integration').get`, `ValidationError`, `_create_sale`, `isinstance`.

### `_create_sale(*, actor, warehouse_id, price_type, sale_type, payment_method, lines, cash_received_amount=None, note='', external_prices=None, creation_key=None, partner_id=None, partner_name='', settlement_confirmation='', _direct_rows=None, _prepaid=Decimal('0.00'))`

Исходник: `sales/services.py:322`.

Декораторы: `transaction.atomic`.

Списывает локальный stock и для наличной продажи в той же транзакции проводит кассу.

Статические вызовы: `((price - discount) * line['quantity']).quantize`, `(line_total / line['quantity']).quantize`, `Decimal`, `Decimal(str(external_prices[key])).quantize`, `Sale.PaymentMethod`, `Sale.objects.create`, `Sale.objects.filter`, `Sale.objects.filter(creation_key=creation_key).first`, `SaleCDItem`, `SaleCDItem.objects.bulk_create`, `SaleCustomItem`, `SaleCustomItem.objects.bulk_create`, `SaleTechItem`, `SaleTechItem.objects.bulk_create`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_commission_audit_snapshot`, `_commission_enabled`, `_complete_if_ready`, `_direct_rows[index].get`, `_locked_inventory`, `_prepare_manual_lines`, `_product_quantities`, `_product_quantities(warehouse_prepared).items`, `_sale_product_lines`, `_selected_price`, `_validate_choice`, `_validate_expense_received`, `_validate_partner_debt`, `any`, `bool`, `calculate_avito_commission`, `cd_items.append`, `clear_storage_locations_if_zero`, `consume_consignment_sale_lines`, `credit_sale_payment`, `dict`, `enumerate`, `getattr`, `hashlib.sha256`, `hashlib.sha256(json.dumps({'actor': actor.pk, 'warehouse': str(warehouse_id), 'price': price_type, 'type': sale_type, 'payment': payment_method, 'lines': lines, 'received': cash_received_amount, 'note': note, 'partner_id': str(partner_id or ''), 'partner_name': partner_name}, sort_keys=True, default=str).encode()).hexdigest`, `json.dumps`, `json.dumps({'actor': actor.pk, 'warehouse': str(warehouse_id), 'price': price_type, 'type': sale_type, 'payment': payment_method, 'lines': lines, 'received': cash_received_amount, 'note': note, 'partner_id': str(partner_id or ''), 'partner_name': partner_name}, sort_keys=True, default=str).encode`, `line.get`, `line_total.is_finite`, `logger.info`, `money`, `payment_values`, `priced_lines.append`, `quote_consignment_sale_lines`, `record_product_changes`, `record_settlement`, `resolve_customer`, `sale.save`, `stock.full_clean`, `stock.save`, `stock_change`, `stocks.get`, `str`, `str(note or '').strip`, `sum`, `tech_items.append`, `timezone.now`, `uuid.UUID`.

### `advance_order_status(*, actor, sale_id, next_status, _market=False)`

Исходник: `sales/services.py:553`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ORDER_TRANSITIONS.get`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `_complete_if_ready`, `hasattr`, `lock_document_trip`, `logger.info`, `sale.save`, `update_fields.append`.

### `set_sale_payment_method(*, actor, sale_id, payment_method)`

Исходник: `sales/services.py:574`.

Декораторы: `transaction.atomic`.

Выбор сотрудника не подтверждает оплату и не создаёт кассовую операцию.

Статические вызовы: `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `logger.info`, `sale.full_clean`, `sale.save`.

### `mark_sale_paid(*, actor, sale_id, cash_received_amount=None, settlement_confirmation='', note=None, settlement_partner_id=None)`

Исходник: `sales/services.py:595`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подтверждает постоплату один раз с актуальным расчётом партнёра. Рейсовая финализация проверяется до денег; наличные и долг проводятся согласованно.

Статические вызовы: `Decimal`, `PermissionDenied`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().select_related`, `Sale.objects.select_for_update().select_related('warehouse').get`, `ValidationError`, `_complete_if_ready`, `_validate_expense_received`, `_validate_partner_debt`, `actor.has_perm`, `assert_document_finalized`, `credit_sale_payment`, `lock_document_trip`, `logger.info`, `money`, `payment_values`, `record_settlement`, `resolve_payment_partner`, `sale.save`, `str`, `str(note or '').strip`, `timezone.now`, `update_fields.append`, `update_fields.extend`.

### `update_sale_note(*, actor, sale_id, note)`

Исходник: `sales/services.py:659`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `len`, `logger.info`, `sale.save`, `str`, `str(note or '').strip`.

### `edit_postpay_sale_items(*, actor, sale_id, lines, note=None, partner_id=None, partner_name=None)`

Исходник: `sales/services.py:674`.

Декораторы: `transaction.atomic`.

Меняет только разрешённую незавершённую постоплату. Проверяет общий остаток повторов, сохраняет исторические строки, разделяет рейсовые и складские источники.

Статические вызовы: `((item.unit_price - item.unit_discount) * item.quantity).quantize`, `Decimal`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `SaleCustomItem`, `SaleCustomItem.objects.bulk_create`, `SaleCustomItem.objects.filter`, `SaleCustomItem.objects.filter(sale=sale).delete`, `ValidationError`, `_commission_audit_snapshot`, `_commission_enabled`, `_configuration`, `_locked_inventory`, `_prepare_manual_lines`, `_product_quantities`, `_sale_product_lines`, `_selected_price`, `any`, `bool`, `by_product.items`, `by_product[kind, getattr(item, field + '_id')].append`, `calculate_avito_commission`, `clear_storage_locations_if_zero`, `consume_consignment_sale_lines`, `defaultdict`, `desired.get`, `desired.keys`, `edit_direct_sale`, `existing.get`, `existing.items`, `getattr`, `hasattr`, `int`, `item.delete`, `item.full_clean`, `item.save`, `len`, `line.get`, `lock_document_trip`, `logger.info`, `matched.add`, `max`, `model`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `model.objects.select_for_update().filter(sale=sale).order_by`, `old_totals.get`, `old_totals.keys`, `quote_consignment_sale_lines`, `record_product_changes`, `resolve_customer`, `restore_consignment_sale_lines`, `sale.cd_items.all`, `sale.consignment_items.all`, `sale.custom_items.all`, `sale.save`, `sale.tech_items.all`, `set`, `stock.full_clean`, `stock.save`, `stock_change`, `stocks.get`, `str`, `str(note or '').strip`, `sum`, `total.quantize`.

### `cancel_sale(*, actor, sale_id, comment, _market=False, restore_stock=True)`

Исходник: `sales/services.py:826`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Сторнирует собственные деньги/долг и восстанавливает реально списанные партии. Direct-delivery не возвращается на физический склад; повтор отмены не дублирует движения.

Статические вызовы: `Decimal`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().select_related`, `Sale.objects.select_for_update().select_related('warehouse').get`, `SaleCancellationResult`, `SaleCustomItem.objects.filter`, `SaleCustomItem.objects.filter(sale=sale).exists`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_configuration`, `_locked_inventory`, `changes.append`, `field_change`, `getattr`, `hasattr`, `item_model.objects.select_for_update`, `item_model.objects.select_for_update().select_related`, `item_model.objects.select_for_update().select_related(product_field).filter`, `item_model.objects.select_for_update().select_related(product_field).filter(sale=sale).order_by`, `lines.extend`, `list`, `lock_document_trip`, `locked_items.extend`, `logger.info`, `product.full_clean`, `product.save`, `record_product_changes`, `refund_sale_payment`, `restore_consignment_sale_lines`, `reverse_settlement`, `sale.consignment_items.exists`, `sale.full_clean`, `sale.save`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_model`, `stocks.get`, `str`, `str(comment or '').strip`, `timezone.now`, `warehouse_owned_quantity`, `weighted_warehouse_cost`.

## `sales/statistics_excel.py`

XLSX rendering from the exact same StatisticsReport used by the web page.

Импорты: `django.utils`, `io`, `models`, `openpyxl`, `openpyxl.styles`, `statistics_service`.

### `_append(sheet, values)`

Исходник: `sales/statistics_excel.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`, `sheet.append`, `value.startswith`.

### `_header(sheet, values)`

Исходник: `sales/statistics_excel.py:17`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Font`, `PatternFill`, `_append`.

### `render_statistics_workbook(report)`

Исходник: `sales/statistics_excel.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `BytesIO`, `CHANNEL_LABELS.get`, `Workbook`, `_append`, `_header`, `dict`, `dict((('day', 'По дням'), ('week', 'По неделям'), ('month', 'По месяцам'))).get`, `dict(Sale.OperationKind.choices).get`, `filters.get`, `len`, `line.kind.upper`, `map`, `max`, `min`, `output.getvalue`, `payment_labels.get`, `row.kind.upper`, `sale.get_operation_kind_display`, `sale.get_payment_method_display`, `sorted`, `str`, `timezone.localtime`, `timezone.localtime(row.date).replace`, `timezone.localtime(sale.completed_at).replace`, `workbook.create_sheet`, `workbook.save`.

## `sales/statistics_forms.py`

Валидация периода и фильтров отчёта продаж без изменения документов.

Импорты: `catalog.models`, `django`, `models`, `partners.customers`, `partners.models`, `warehouse.models`.

### `SaleStatisticsFilterForm.clean(self)`

Исходник: `sales/statistics_forms.py:61`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `data.get`, `forms.ValidationError`, `frozenset`, `hasattr`, `ids.add`, `int`, `self.data.getlist`, `set`, `str`, `str(data.get('sale_ids_text') or '').replace`, `str(data.get('sale_ids_text') or '').replace(';', ',').split`, `str(raw).strip`, `super`, `super().clean`, `value.isdecimal`.

## `sales/statistics_service.py`

Единый источник расчётов для страницы, графика и Excel-отчёта.

Импорты: `catalog.models`, `catalog.product_search`, `collections`, `dataclasses`, `datetime`, `decimal`, `django.db`, `django.db.models`, `django.utils`, `models`, `partner_statistics`.

### `channel_for_sale(sale)`

Исходник: `sales/statistics_service.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `percentage(part, total)`

Исходник: `sales/statistics_service.py:37`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(part * Decimal('100') / total).quantize`, `Decimal`.

### `LineRow.unit_profit(self)`

Исходник: `sales/statistics_service.py:64`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(self.profit / self.quantity).quantize`.

### `ProductAggregate.sales_count(self)`

Исходник: `sales/statistics_service.py:131`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`.

### `_matching_sale_ids(filters)`

Исходник: `sales/statistics_service.py:155`.

Return sale IDs containing a matching item; selected sales retain all lines.

Статические вызовы: `CD.objects.all`, `SaleCDItem.objects.filter`, `SaleCDItem.objects.filter(cd__in=cd_queryset).values_list`, `SaleConsignmentItem.objects.filter`, `SaleConsignmentItem.objects.filter(models.Q(cd__in=cd_queryset) | models.Q(tech__in=tech_queryset)).values_list`, `SaleCustomItem.objects.filter`, `SaleCustomItem.objects.filter(product_name_snapshot__icontains=query).values_list`, `SaleTechItem.objects.filter`, `SaleTechItem.objects.filter(tech__in=tech_queryset).values_list`, `Tech.objects.all`, `any`, `cd_queryset.filter`, `filter_products_by_text`, `filters.get`, `ids.update`, `models.Q`, `set`, `str`, `str(filters.get('product_query') or '').strip`, `tech_queryset.filter`.

### `_base_queryset(filters)`

Исходник: `sales/statistics_service.py:189`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Prefetch`, `Sale.objects.filter`, `SaleCDItem.objects.select_related`, `SaleConsignmentItem.objects.select_related`, `SaleCustomItem.objects.all`, `SaleTechItem.objects.select_related`, `_matching_sale_ids`, `filters.get`, `models.Q`, `queryset.filter`, `queryset.select_related`, `queryset.select_related('warehouse', 'consignment_platform').prefetch_related`, `queryset.select_related('warehouse', 'consignment_platform').prefetch_related(Prefetch('cd_items', queryset=SaleCDItem.objects.select_related('cd__platform', 'cd__game_series')), Prefetch('tech_items', queryset=SaleTechItem.objects.select_related('tech__brand', 'tech__product_type')), Prefetch('custom_items', queryset=SaleCustomItem.objects.all()), Prefetch('consignment_items', queryset=SaleConsignmentItem.objects.select_related('cd', 'tech', 'platform'))).order_by`, `sale_types.append`.

### `_line(item, kind)`

Исходник: `sales/statistics_service.py:234`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(revenue / item.quantity).quantize`, `(unit_cost * item.quantity).quantize`, `LineRow`, `getattr`, `item.avito_commission_amount.quantize`, `item.line_total.quantize`, `percentage`.

### `_sale_row(sale)`

Исходник: `sales/statistics_service.py:269`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CHANNEL_LABELS.get`, `SaleRow`, `_line`, `bool`, `channel_for_sale`, `dict.fromkeys`, `item.system_product_id.lower`, `len`, `lines.extend`, `list`, `percentage`, `sale.cd_items.all`, `sale.consignment_items.all`, `sale.custom_items.all`, `sale.get_sale_type_display`, `sale.tech_items.all`, `sum`.

### `_aggregate(rows)`

Исходник: `sales/statistics_service.py:309`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(result.actual_revenue / result.sales_count).quantize`, `Aggregate`, `list`, `percentage`, `sum`.

### `_product_rows(rows)`

Исходник: `sales/statistics_service.py:337`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(group.revenue / group.units).quantize`, `ProductAggregate`, `all`, `group.sales_ids.add`, `groups.values`, `list`, `percentage`, `sum`.

### `_time_key(sale, grouping)`

Исходник: `sales/statistics_service.py:371`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `day.replace`, `day.strftime`, `day.weekday`, `timedelta`, `timezone.localtime`, `timezone.localtime(sale.completed_at).date`.

### `_group_rows(rows, grouping)`

Исходник: `sales/statistics_service.py:382`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CHANNEL_LABELS.get`, `GroupRow`, `_aggregate`, `_time_key`, `channel_rows.sort`, `channels.items`, `channels[row.channel].append`, `defaultdict`, `len`, `list`, `list(CHANNEL_LABELS).index`, `sorted`, `str`, `times[key].append`.

### `_sort_with_missing(rows, key, descending)`

Исходник: `sales/statistics_service.py:399`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `key`, `sorted`.

### `_sort_sales(rows, choice)`

Исходник: `sales/statistics_service.py:405`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_sort_with_missing`, `choice.lstrip`, `choice.startswith`, `keys.get`.

### `_sort_products(rows, choice)`

Исходник: `sales/statistics_service.py:417`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_sort_with_missing`, `choice.lstrip`, `choice.startswith`, `keys.get`.

### `_chart_data(time_rows)`

Исходник: `sales/statistics_service.py:425`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Decimal`, `coordinates.split`, `current.append`, `enumerate`, `float`, `getattr`, `len`, `max`, `min`, `point`, `points.append`, `segments.append`, `series.append`.

### `build_sales_statistics_report(filters)`

Исходник: `sales/statistics_service.py:468`.

Builds all surfaces from one completed-sale selection and immutable item snapshots.

Статические вызовы: `Sale.objects.filter`, `Sale.objects.filter(order_status=Sale.OrderStatus.DELIVERED, payment_status=Sale.PaymentStatus.PAID, cancelled_at__isnull=True, completed_at__isnull=True).count`, `StatisticsReport`, `_aggregate`, `_base_queryset`, `_chart_data`, `_group_rows`, `_product_rows`, `_sale_row`, `_sort_products`, `_sort_sales`, `filters.get`, `financial_operations`, `sum`.

## `sales/statistics_urls.py`

Маршруты статистики и экспорта с отдельными правами просмотра.

Импорты: `django.urls`.

## `sales/statistics_views.py`

Построение отчёта/экспорта по выбранным продажам; финансовые снимки не подменяются текущими ценами.

Импорты: `core.decorators`, `django.core.paginator`, `django.http`, `django.shortcuts`, `django.utils`, `statistics_excel`, `statistics_forms`, `statistics_service`.

### `_filter_form(request)`

Исходник: `sales/statistics_views.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SaleStatisticsFilterForm`, `data.get`, `request.GET.copy`.

### `_report(request)`

Исходник: `sales/statistics_views.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_filter_form`, `build_sales_statistics_report`, `form.is_valid`.

### `statistics_index(request)`

Исходник: `sales/statistics_views.py:28`.

Декораторы: `permission_required_any('sales.view_sales_statistics')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Paginator`, `Paginator(report.operations, 50).get_page`, `Paginator(report.products, 25).get_page`, `Paginator(report.sales, 25).get_page`, `_report`, `any`, `bool`, `params.pop`, `params.urlencode`, `permission_required_any`, `render`, `report.filters.get`, `request.GET.copy`, `request.GET.get`, `request.user.has_perm`, `timezone.localdate`, `timezone.localdate().isoformat`.

### `statistics_export(request)`

Исходник: `sales/statistics_views.py:50`.

Декораторы: `permission_required_all('sales.view_sales_statistics', 'sales.export_sales_statistics')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `HttpResponse`, `_report`, `permission_required_all`, `render_statistics_workbook`.

## `sales/storage_locations.py`

Места хранения для сборки незавершённой продажи без изменения складских данных.

Импорты: `catalog.models`, `django.db.models`, `models`, `warehouse.models`, `warehouse.storage_services`.

### `sale_storage_locations(sale)`

Исходник: `sales/storage_locations.py:17`.

Возвращает адреса склада продажи; очищенные при продаже адреса помечает историческими.

Статические вызовы: `OuterRef`, `Prefetch`, `ProductFieldChange.objects.filter`, `ProductFieldChange.objects.filter(Q(event__cd_id__in=cleared_products['cd']) | Q(event__tech_id__in=cleared_products['tech']), field_name=f'warehouse_storage_locations_{sale.warehouse_id}').order_by`, `ProductFieldChange.objects.filter(Q(event__cd_id__in=cleared_products['cd']) | Q(event__tech_id__in=cleared_products['tech']), field_name=f'warehouse_storage_locations_{sale.warehouse_id}').order_by('-event__created_at', '-event_id', '-pk').values`, `ProductFieldChange.objects.filter(field_name=f'warehouse_stock_{sale.warehouse_id}', **{f'event__{kind}_id': OuterRef(f'{kind}_id')}).order_by`, `ProductFieldChange.objects.filter(field_name=f'warehouse_stock_{sale.warehouse_id}', **{f'event__{kind}_id': OuterRef(f'{kind}_id')}).order_by('-event__created_at', '-event_id', '-pk').values`, `Q`, `Subquery`, `any`, `assignment_model.objects.select_related`, `assignment_model.objects.select_related('location').order_by`, `changes.iterator`, `cleared_products.values`, `cleared_products[kind].add`, `getattr`, `last_stock_changes.get`, `len`, `sale.cd_items.all`, `sale.tech_items.all`, `seen.add`, `set`, `stock_model.objects.filter`, `stock_model.objects.filter(warehouse_id=sale.warehouse_id, **{f'{kind}_id__in': products[kind]}).annotate`, `stock_model.objects.filter(warehouse_id=sale.warehouse_id, **{f'{kind}_id__in': products[kind]}).annotate(last_stock_change_at=Subquery(last_stock_change)).prefetch_related`, `storage_locations_for_stock`, `sum`.

## `sales/urls.py`

Именованные HTTP-маршруты приложения продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `django.urls`.

## `sales/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю продаж.

Склад, деньги и долг проводят штатные сервисы; исторические строки сохраняют снимки.

Импорты: `catalog.models`, `consignment.models`, `consignment.report_views`, `consignment.reports`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db`, `django.http`, `django.shortcuts`, `django.template.loader`, `django.urls`, `django.utils.http`, `django.views.decorators.http`, `forms`, `invoice_excel`, `listing`, `market_controls`, `models`, `orders.fulfillment_views`, `partner_payments`, `partners.customers`, `price.excel`, `services`, `storage_locations`.

### `_detail_financials(item, *, commission_applicable=True)`

Исходник: `sales/views.py:35`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `getattr`.

### `_sale_destination(request, sale)`

Исходник: `sales/views.py:54`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `redirect`, `request.user.has_perm`.

### `_parse_lines(post)`

Исходник: `sales/views.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `len`, `lines.extend`, `post.getlist`, `range`.

### `_consignment_options()`

Исходник: `sales/views.py:125`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `model.objects.filter`, `model.objects.filter(quantity__gt=0).select_related`, `options.append`, `row['label'].casefold`, `sorted`.

### `_posted_initial_items(post)`

Исходник: `sales/views.py:138`.

Сохраняет введённые строки при ошибке backend, без запросов на каждую строку.

Статические вызовы: `_parse_lines`, `getattr`, `line.get`, `model.objects.filter`, `products.get`, `products.update`, `result.append`, `str`, `str(line['product_id']).isdecimal`.

### `sale_list(request)`

Исходник: `sales/views.py:166`.

Декораторы: `permission_required_any('sales.view_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_sale_list_page`, `permission_required_any`.

### `_sale_list_page(request, state, title)`

Исходник: `sales/views.py:170`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `list_groups`, `payment_partner_choices`, `render`, `request.user.has_perm`.

### `sale_completed_list(request)`

Исходник: `sales/views.py:178`.

Декораторы: `permission_required_all('sales.view_sales', 'sales.view_completed_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_sale_list_page`, `permission_required_all`.

### `sale_cancelled_list(request)`

Исходник: `sales/views.py:183`.

Декораторы: `permission_required_any('sales.view_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_sale_list_page`, `permission_required_any`.

### `_status_response(request, pk, success, message, status=200)`

Исходник: `sales/views.py:187`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `data.update`, `render_to_string`, `sale.updated_at.isoformat`, `sales_queryset`, `sales_queryset().filter`, `sales_queryset().filter(pk=pk).first`, `status_context`.

### `sale_inline_status(request, pk)`

Исходник: `sales/views.py:204`.

Декораторы: `require_POST`; `permission_required_any('sales.view_sales')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `Sale.objects.select_for_update`, `Sale.objects.select_for_update().get`, `ValidationError`, `_status_response`, `advance_order_status`, `mark_sale_paid`, `needs_report_partner`, `permission_required_any`, `request.POST.get`, `request.user.has_perm`, `reverse`, `sale.updated_at.isoformat`, `transaction.atomic`, `{'order': 'sales.advance_order_status', 'payment': 'sales.mark_sale_paid'}.get`.

### `sale_create(request)`

Исходник: `sales/views.py:243`.

Декораторы: `permission_required_any('sales.create_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.objects.filter`, `Sale.objects.filter(consignment_report_id=report_id, created_by=request.user).first`, `SaleCreateForm`, `_consignment_options`, `_parse_lines`, `_posted_initial_items`, `_sale_destination`, `bool`, `create_report_sale`, `creator`, `draft.get`, `form.add_error`, `form.is_valid`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `render`, `report.get`, `request.GET.get`, `request.POST.get`, `request.session.get`, `request.session.pop`, `request.user.has_perm`, `str`, `trip_sale_create`, `uuid.UUID`, `uuid.uuid4`.

### `sale_wholesale_import(request)`

Исходник: `sales/views.py:316`.

Декораторы: `permission_required_all('sales.create_sale', 'sales.import_wholesale_price')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `WholesalePriceImportForm`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `import_wholesale_price_to_sale`, `messages.success`, `permission_required_all`, `redirect`, `render`, `request.session.get`, `request.session.pop`.

### `sale_detail(request, pk)`

Исходник: `sales/views.py:348`.

Декораторы: `permission_required_any('sales.view_sale_detail')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sale.objects.select_related`, `Sale.objects.select_related('warehouse', 'created_by', 'paid_by', 'consignment_platform').prefetch_related`, `_detail_financials`, `bool`, `get_object_or_404`, `hasattr`, `market_context`, `next_order_status`, `payment_partner_choices`, `permission_required_any`, `render`, `request.user.has_perm`, `sale.cash_transactions.all`, `sale.cd_items.all`, `sale.consignment_items.all`, `sale.custom_items.all`, `sale.tech_items.all`, `sale_storage_locations`, `storage_locations.get`, `sum`, `with_market_controls`.

### `sale_invoice(request, pk)`

Исходник: `sales/views.py:428`.

Декораторы: `require_GET`; `permission_required_any('sales.view_sale_detail')`.

Скачать накладную Excel по снимкам строк продажи в любом статусе.

Статические вызовы: `''.join`, `HttpResponse`, `Sale.objects.select_related`, `Sale.objects.select_related('warehouse', 'created_by').prefetch_related`, `bool`, `char.isalnum`, `content_disposition_header`, `customer_filename`, `get_object_or_404`, `permission_required_any`, `render_sale_invoice_xlsx`, `sale.cd_items.all`, `sale.consignment_items.all`, `sale.custom_items.all`, `sale.tech_items.all`.

### `sale_edit(request, pk)`

Исходник: `sales/views.py:466`.

Декораторы: `permission_required_any('sales.edit_unpaid_postpay_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `CustomerSelectionForm`, `Sale.objects.prefetch_related`, `_consignment_options`, `_parse_lines`, `_sale_destination`, `customer_form.is_valid`, `edit_postpay_sale_items`, `get_object_or_404`, `messages.error`, `messages.success`, `permission_required_any`, `render`, `request.POST.get`, `sale.cd_items.all`, `sale.consignment_items.all`, `sale.custom_items.all`, `sale.tech_items.all`, `str`.

### `sale_advance(request, pk)`

Исходник: `sales/views.py:522`.

Декораторы: `require_POST`; `permission_required_any('sales.advance_order_status')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Sale.objects.filter`, `Sale.objects.filter(pk=pk).first`, `_sale_destination`, `advance_order_status`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`.

### `sale_payment_method(request, pk)`

Исходник: `sales/views.py:535`.

Декораторы: `require_POST`; `permission_required_any('sales.mark_sale_paid')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Sale.objects.filter`, `Sale.objects.filter(pk=pk).first`, `_sale_destination`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `set_sale_payment_method`.

### `sale_mark_paid(request, pk)`

Исходник: `sales/views.py:548`.

Декораторы: `require_POST`; `permission_required_any('sales.mark_sale_paid')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Sale.objects.filter`, `Sale.objects.filter(pk=pk).first`, `_sale_destination`, `get_object_or_404`, `isinstance`, `mark_sale_paid`, `messages.error`, `messages.success`, `needs_report_partner`, `permission_required_any`, `redirect`, `request.POST.get`.

### `sale_note_update(request, pk)`

Исходник: `sales/views.py:574`.

Декораторы: `require_POST`; `permission_required_any('sales.change_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Sale.objects.get`, `_sale_destination`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `update_sale_note`.

### `sale_cancel(request, pk)`

Исходник: `sales/views.py:589`.

Декораторы: `require_POST`; `permission_required_any('sales.cancel_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Sale.objects.filter`, `Sale.objects.filter(pk=pk).first`, `_sale_destination`, `cancel_sale`, `isinstance`, `messages.error`, `messages.info`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`.

## `supplies/admin.py`

Регистрация моделей и разрешённых действий в Django Admin приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует.

Импорты: `django.contrib`, `models`, `partners.admin`.

### `HistoricalAdmin.has_add_permission(self, request)`

Исходник: `supplies/admin.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `HistoricalAdmin.has_change_permission(self, request, obj=None)`

Исходник: `supplies/admin.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `HistoricalAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `supplies/admin.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `supplies/apps.py`

Конфигурация приложения и его регистрация в Django приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует.

Импорты: `django.apps`.

## `supplies/finalization.py`

Точный расчёт и применение финализации принятого прихода.

Импорты: `catalog.audit`, `catalog.models`, `dataclasses`, `decimal`, `django.core.exceptions`, `django.core.validators`, `django.db`, `functools`, `math`, `models`, `orders.models`, `warehouse.models`, `warehouse.valuation`.

### `FinalizationRow.key(self)`

Исходник: `supplies/finalization.py:35`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `FinalizationRow.row_penalty(self)`

Исходник: `supplies/finalization.py:39`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`.

### `FinalizationRow.difference_per_unit(self)`

Исходник: `supplies/finalization.py:43`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `FinalizationInput.key(self)`

Исходник: `supplies/finalization.py:57`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_money(value, label)`

Исходник: `supplies/finalization.py:61`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `DecimalValidator`, `DecimalValidator(max_digits=20, decimal_places=2)`, `ValidationError`, `amount.is_finite`, `amount.quantize`, `str`, `str(value).strip`, `str(value).strip().replace`, `str(value).strip().replace(' ', '').replace`.

### `parse_finalization_inputs(raw_rows)`

Исходник: `supplies/finalization.py:78`.

Нормализует присланные baseline и corrected cost без доверия к UI.

Статические вызовы: `FinalizationInput`, `ValidationError`, `_money`, `int`, `parsed.append`, `raw.get`, `seen.add`, `set`, `str`, `str(raw.get('change_source', 'manual')).lower`, `str(raw.get('product_type', '')).lower`.

### `_supply_product_keys(supply)`

Исходник: `supplies/finalization.py:115`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `sorted`, `supply.cd_items.values_list`, `supply.tech_items.values_list`.

### `supply_has_complete_cost_calculations(supply)`

Исходник: `supplies/finalization.py:122`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_supply_product_keys`, `bool`, `set`, `supply.cost_calculations.all`.

### `_lock_global_quantity_records(keys)`

Исходник: `supplies/finalization.py:134`.

Блокирует складские строки, участвующие в расчёте себестоимости.

Статические вызовы: `CDWarehouseStock.objects.select_for_update`, `CDWarehouseStock.objects.select_for_update().filter`, `CDWarehouseStock.objects.select_for_update().filter(cd_id__in=cd_ids).order_by`, `TechWarehouseStock.objects.select_for_update`, `TechWarehouseStock.objects.select_for_update().filter`, `TechWarehouseStock.objects.select_for_update().filter(tech_id__in=tech_ids).order_by`, `list`.

### `get_supply_finalization_context(*, supply, lock=False)`

Исходник: `supplies/finalization.py:142`.

Возвращает товары актуальной редакции со складским количеством и cost.

Статические вызовы: `CD.objects.active`, `CD.objects.active().filter`, `CD.objects.active().filter(pk__in=cd_ids).order_by`, `FinalizationRow`, `Tech.objects.active`, `Tech.objects.active().filter`, `Tech.objects.active().filter(pk__in=tech_ids).order_by`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(supply=supply, calculation__has_key='arrival_id').exists`, `ValidationError`, `_lock_global_quantity_records`, `_supply_product_keys`, `calculations[key].resulting_unit_cost.quantize`, `cd_query.select_for_update`, `product.cost.quantize`, `rows.append`, `set`, `supply.cost_calculations.all`, `supply_has_complete_cost_calculations`, `tech_query.select_for_update`, `warehouse_owned_quantity`.

### `calculate_finalization_penalty(rows)`

Исходник: `supplies/finalization.py:192`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `sum`, `sum((row.row_penalty for row in rows), Decimal('0.00')).quantize`.

### `_extended_gcd(a, b)`

Исходник: `supplies/finalization.py:196`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_extended_gcd`.

### `_residual_coefficients(quantities, target)`

Исходник: `supplies/finalization.py:203`.

Находит детерминированные целые поправки в копейках для residual.

Статические вызовы: `ValidationError`, `_extended_gcd`, `enumerate`, `len`, `list`, `reduce`, `states.items`, `sum`.

### `auto_distribute_penalty(*, rows, selected_keys)`

Исходник: `supplies/finalization.py:241`.

Распределяет penalty по глобальным единицам и точно гасит residual.

Статические вызовы: `Decimal`, `ValidationError`, `_residual_coefficients`, `abs`, `calculate_finalization_penalty`, `corrected.quantize`, `corrections.get`, `int`, `list`, `replace`, `result.append`, `set`, `sum`, `zip`.

### `rows_from_inputs(current_rows, inputs)`

Исходник: `supplies/finalization.py:287`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `current.items`, `replace`, `rows.append`, `set`.

### `apply_supply_finalization(*, actor, supply_id, expected_revision_number, raw_rows)`

Исходник: `supplies/finalization.py:315`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(before_value - after_value).quantize`, `(difference * Decimal(row.global_quantity)).quantize`, `(row.corrected_cost * Decimal(calculation.resulting_quantity)).quantize`, `Decimal`, `Supply.objects.select_for_update`, `Supply.objects.select_for_update().get`, `SupplyFinalization.objects.create`, `SupplyFinalizationItem`, `SupplyFinalizationItem.objects.bulk_create`, `ValidationError`, `calculate_finalization_penalty`, `calculation.save`, `field_change`, `get_supply_finalization_context`, `getattr`, `history_items.append`, `int`, `len`, `logger.exception`, `logger.info`, `parse_finalization_inputs`, `product.full_clean`, `product.save`, `record_product_changes`, `row.difference_per_unit.quantize`, `rows_from_inputs`, `sum`, `sum((row.row_penalty for row in changed if row.change_source != 'auto'), Decimal('0.00')).quantize`, `supply.cost_calculations.select_for_update`, `transaction.atomic`.

## `supplies/management/commands/recalculate_warehouse_costs.py`

Одноразовый безопасный пересчёт истории приходов по физическому складу.

Импорты: `catalog.audit`, `catalog.models`, `collections`, `consignment.models`, `decimal`, `django.core.management.base`, `django.db`, `supplies.models`, `warehouse.models`, `warehouse.valuation`.

### `_product_filter(kind, product_id)`

Исходник: `supplies/management/commands/recalculate_warehouse_costs.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_warehouse_quantity_before(kind, product_id, moment)`

Исходник: `supplies/management/commands/recalculate_warehouse_costs.py:29`.

Восстанавливает складское количество непосредственно перед операцией.

Статические вызовы: `CommandError`, `ProductFieldChange.objects.filter`, `ProductFieldChange.objects.filter(event__created_at__gt=moment, field_name__startswith='warehouse_stock_', **_product_filter(kind, product_id)).values_list`, `_product_filter`, `int`, `warehouse_owned_quantity`.

### `_movement_stock_id(item)`

Исходник: `supplies/management/commands/recalculate_warehouse_costs.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ProductFieldChange.objects.filter`, `ProductFieldChange.objects.filter(event__action_kind=ProductChangeEvent.ActionKind.CONSIGNMENT, event__action_object_id=item.movement_id, field_name__startswith=prefix, **_product_filter(item.product_kind, getattr(item, f'{item.product_kind}_id'))).order_by`, `ProductFieldChange.objects.filter(event__action_kind=ProductChangeEvent.ActionKind.CONSIGNMENT, event__action_object_id=item.movement_id, field_name__startswith=prefix, **_product_filter(item.product_kind, getattr(item, f'{item.product_kind}_id'))).order_by('id').first`, `_product_filter`, `change.field_name.removeprefix`, `getattr`, `int`.

### `Command.add_arguments(self, parser)`

Исходник: `supplies/management/commands/recalculate_warehouse_costs.py:75`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `supplies/management/commands/recalculate_warehouse_costs.py:79`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(resulting_value / Decimal(resulting_quantity)).quantize`, `CommandError`, `ConsignmentMovementItem.objects.select_for_update`, `ConsignmentMovementItem.objects.select_for_update().select_related`, `ConsignmentMovementItem.objects.select_for_update().select_related('movement').filter`, `ConsignmentMovementItem.objects.select_for_update().select_related('movement').filter(product_kind=kind, **{product_field: product}).order_by`, `Decimal`, `Supply.objects.exclude`, `Supply.objects.exclude(revision_number=1).exists`, `Supply.objects.filter`, `Supply.objects.filter(cancelled_at__isnull=False).exists`, `SupplyCostCalculation.objects.filter`, `SupplyCostCalculation.objects.filter(product_kind=kind).values_list`, `SupplyCostCalculation.objects.select_for_update`, `SupplyCostCalculation.objects.select_for_update().select_related`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter(product_kind=kind, **{product_field: product}).order_by`, `SupplyFinalization.objects.exists`, `WarehouseTransfer.objects.exists`, `_movement_stock_id`, `_warehouse_quantity_before`, `calculations[0].old_unit_cost.quantize`, `event.save`, `events.extend`, `examples.append`, `field_change`, `item.save`, `len`, `list`, `lot.save`, `lot_costs.get`, `lot_quantities.get`, `max`, `next`, `old_value.quantize`, `product.cost.quantize`, `product.full_clean`, `product.save`, `product_model.objects.select_for_update`, `product_model.objects.select_for_update().filter`, `product_model.objects.select_for_update().filter(pk__in=product_ids).order_by`, `record_product_changes`, `resulting_value.quantize`, `self.stdout.write`, `self.style.SUCCESS`, `self.style.WARNING`, `set`, `sorted`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(**{product_field: product}).order_by`, `stock_model.objects.values_list`, `transaction.set_rollback`, `weighted_warehouse_cost`.

## `supplies/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует.

Импорты: `catalog.models`, `django.conf`, `django.core.validators`, `django.db`, `orders.arrival`, `partners.models`, `warehouse.models`.

### `Supply.item_count(self)`

Исходник: `supplies/models.py:102`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.cd_items.count`, `self.tech_items.count`.

### `Supply.is_cancelled(self)`

Исходник: `supplies/models.py:106`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Supply.__str__(self)`

Исходник: `supplies/models.py:109`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `Supply.save(self, *args, **kwargs)`

Исходник: `supplies/models.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `assert_document_finalized`, `super`, `super().save`.

### `SupplyCostCalculation.product(self)`

Исходник: `supplies/models.py:265`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyCostCalculation.__str__(self)`

Исходник: `supplies/models.py:268`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyExpense.__str__(self)`

Исходник: `supplies/models.py:284`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyRevision.__str__(self)`

Исходник: `supplies/models.py:333`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyRevisionItem.product(self)`

Исходник: `supplies/models.py:382`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyFinalization.__str__(self)`

Исходник: `supplies/models.py:451`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyFinalizationItem.product(self)`

Исходник: `supplies/models.py:533`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `SupplyFinalizationItem.__str__(self)`

Исходник: `supplies/models.py:536`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `supplies/services.py`

Транзакционные операции приёмки поставок.

Импорты: `catalog.audit`, `catalog.game_codes`, `catalog.models`, `collections`, `consignment.models`, `core.allocation`, `dataclasses`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `integrations.google_tasks`, `models`, `orders.arrival`, `orders.fulfillment`, `partners.models`, `pricing.services`, `warehouse.models`, `warehouse.storage_services`, `warehouse.valuation`.

### `_decimal(value, label)`

Исходник: `supplies/services.py:62`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `str`.

### `_normalise_lines(raw_lines)`

Исходник: `supplies/services.py:69`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplyLineInput`, `ValidationError`, `_decimal`, `int`, `lines.append`, `raw.get`, `str`, `str(raw.get('product_type', '')).lower`.

### `_normalise_expenses(raw_expenses)`

Исходник: `supplies/services.py:92`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplyExpenseInput`, `ValidationError`, `_decimal`, `amount.quantize`, `expenses.append`, `raw.get`, `str`, `str(raw.get('name', '')).strip`.

### `_normalise_weight_transport_cost(value)`

Исходник: `supplies/services.py:108`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `_decimal`, `amount.quantize`.

### `allocate_weight_transport_cost(*, lines, products, total_transport_cost)`

Исходник: `supplies/services.py:117`.

Распределяет целые копейки по весу строк методом наибольших остатков.

Статические вызовы: `ValidationError`, `allocate_amount`, `sum`.

### `accept_supply(*, accepted_by, warehouse_id, lines, expenses=(), weight_transport_cost=0, defer_balance=False, _pending_supply=None)`

Исходник: `supplies/services.py:137`.

Готовит приход и основание будущей оценки/проверки цен. Реальное проведение определяется штатным состоянием, а не названием функции.

Статические вызовы: `'; '.join`, `(cd_items if line.product_type == 'cd' else tech_items).append`, `(goods_total + expenses_total + weight_transport_cost).quantize`, `(line.purchase_unit_cost * line.quantity).quantize`, `CD.objects.active`, `CD.objects.active().select_for_update`, `CD.objects.active().select_for_update().filter`, `CD.objects.active().select_for_update().filter(pk__in=cd_ids).order_by`, `Decimal`, `Supplier.objects.in_bulk`, `Supply.objects.create`, `SupplyCDItem`, `SupplyCDItem.objects.bulk_create`, `SupplyCostCalculation`, `SupplyCostCalculation.objects.bulk_create`, `SupplyExpense`, `SupplyExpense.objects.bulk_create`, `SupplyTechItem`, `SupplyTechItem.objects.bulk_create`, `Tech.objects.active`, `Tech.objects.active().select_for_update`, `Tech.objects.active().select_for_update().filter`, `Tech.objects.active().select_for_update().filter(pk__in=tech_ids).order_by`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_normalise_expenses`, `_normalise_lines`, `_normalise_weight_transport_cost`, `_old_owned_quantity`, `addition['value'].quantize`, `allocate_weight_transport_cost`, `changes.append`, `cost_calculations.append`, `defaultdict`, `dict`, `effective_cost.quantize`, `enumerate`, `expense_per_unit.quantize`, `expenses_total.quantize`, `field_change`, `getattr`, `goods_total.quantize`, `incoming_line_value.quantize`, `inventory_additions.items`, `len`, `line.purchase_unit_cost.quantize`, `localcontext`, `logger.exception`, `logger.info`, `new_average.quantize`, `old_inventory_value.quantize`, `product.full_clean`, `product.save`, `products.values`, `record_product_changes`, `resulting_value.quantize`, `setattr`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_model`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse=warehouse, **{f'{product_field}_id': product_id}).first`, `sum`, `supply.cd_items.all`, `supply.cd_items.all().delete`, `supply.cost_calculations.all`, `supply.cost_calculations.all().delete`, `supply.expenses.all`, `supply.expenses.all().delete`, `supply.save`, `supply.tech_items.all`, `supply.tech_items.all().delete`, `supply_values.items`, `transaction.atomic`, `transport_per_unit.quantize`, `tuple`, `validate_supply_game_codes`, `validate_supply_snapshot`.

### `edit_pending_supply(*, actor, supply_id, expected_revision_number, warehouse_id, lines, expenses=(), weight_transport_cost=0, reason='')`

Исходник: `supplies/services.py:345`.

Декораторы: `transaction.atomic`.

Пересчитать ожидающий приход, сохранив редакцию и не меняя склад или цены.

Статические вызовы: `PermissionDenied`, `Supply.objects.select_for_update`, `Supply.objects.select_for_update().select_related`, `Supply.objects.select_for_update().select_related('warehouse', 'accepted_by').get`, `ValidationError`, `_snapshot_supply_revision`, `_supersede_supply_finalizations`, `accept_supply`, `actor.has_perm`, `hasattr`, `int`, `str`, `str(reason or 'Изменение состава до приёмки.').strip`, `supply.save`, `supply.trip_operation.calculation.get`, `timezone.now`.

### `confirm_supply_price_review(*, actor, supply_id, price_changes=None, expected_revision_number=None, independent_expenses=None)`

Исходник: `supplies/services.py:379`.

Декораторы: `transaction.atomic`.

Повторно проверяет ревизию и актуальный физический склад, затем атомарно применяет разрешённые цены, среднюю оценку и приход. Устаревший preview отклоняется.

Статические вызовы: `Supply.objects.select_for_update`, `Supply.objects.select_for_update().select_related`, `Supply.objects.select_for_update().select_related('warehouse').get`, `ValidationError`, `changes.append`, `field_change`, `getattr`, `int`, `len`, `list`, `lock_document_trip`, `logger.info`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `model.objects.select_for_update().filter(pk__in=ids).order_by`, `price_changes.get`, `product.full_clean`, `product.save`, `products.update`, `products.values`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_model`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse=supply.warehouse, **{f'{product_field}_id': key[1]}).first`, `supply.cost_calculations.select_for_update`, `supply.cost_calculations.select_for_update().select_related`, `supply.cost_calculations.select_for_update().select_related('cd', 'tech').order_by`, `supply.save`, `timezone.now`, `transaction.on_commit`, `update_product_prices`, `validate_supply_game_codes`, `warehouse_owned_quantity`.

### `_enqueue_google_sheets_after_supply()`

Исходник: `supplies/services.py:477`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_google_sheets_sync`, `logger.exception`.

### `_supply_configuration(product_type)`

Исходник: `supplies/services.py:485`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `_revision_item_values(item, product_type)`

Исходник: `supplies/services.py:493`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `_snapshot_supply_revision(*, supply, actor, reason, diff_summary)`

Исходник: `supplies/services.py:517`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplyExpense.objects.select_for_update`, `SupplyExpense.objects.select_for_update().filter`, `SupplyRevision.objects.create`, `SupplyRevisionExpense`, `SupplyRevisionExpense.objects.bulk_create`, `SupplyRevisionItem`, `SupplyRevisionItem.objects.bulk_create`, `_revision_item_values`, `item_model.objects.select_for_update`, `item_model.objects.select_for_update().select_related`, `item_model.objects.select_for_update().select_related('product').filter`, `revision_items.append`.

### `_supersede_supply_finalizations(*, supply, new_revision_number)`

Исходник: `supplies/services.py:549`.

Сохраняет историю, но не переносит старую финализацию на новый состав прихода.

Статические вызовы: `SupplyFinalization.objects.select_for_update`, `SupplyFinalization.objects.select_for_update().filter`, `finalizations.update`, `timezone.now`.

### `_external_owned_quantity_delta(*, product_type, product_id, after, through)`

Исходник: `supplies/services.py:561`.

Возвращает внешние изменения складского количества в (after, through].

Статические вызовы: `ProductChangeEvent.objects.filter`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude(action_kind=ProductChangeEvent.ActionKind.SUPPLY).prefetch_related`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude(action_kind=ProductChangeEvent.ActionKind.SUPPLY).prefetch_related('field_changes').order_by`, `ValidationError`, `change.field_name.startswith`, `event.field_changes.all`, `int`, `list`.

### `_replay_external_warehouse_events(*, product_type, product_id, after, through, quantity, cost)`

Исходник: `supplies/services.py:585`.

Применяет продажи, передачи, возвраты и приёмку пути между приходами.

Статические вызовы: `((Decimal(quantity) * cost + Decimal(delta) * incoming_cost) / Decimal(quantity + delta)).quantize`, `ConsignmentMovementItem.objects.filter`, `ConsignmentMovementItem.objects.filter(movement_id=event.action_object_id, movement__operation_type=ConsignmentMovement.OperationType.RETURN, product_kind=product_type, **product_filter).first`, `Decimal`, `ProductChangeEvent.objects.filter`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude(action_kind=ProductChangeEvent.ActionKind.SUPPLY).prefetch_related`, `ProductChangeEvent.objects.filter(created_at__gt=after, created_at__lte=through, **product_filter).exclude(action_kind=ProductChangeEvent.ActionKind.SUPPLY).prefetch_related('field_changes').order_by`, `ValidationError`, `change.field_name.startswith`, `event.field_changes.all`, `int`, `item_model.objects.filter`, `item_model.objects.filter(transfer_id=event.action_object_id, **{f'{product_type}_id': product_id}).first`.

### `_calculation_values(*, supply, product_type, product, old_quantity, old_cost, incoming)`

Исходник: `supplies/services.py:641`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(resulting_value / Decimal(resulting_quantity)).quantize`, `Decimal`, `ValidationError`, `incoming_value.quantize`, `old_value.quantize`, `resulting_value.quantize`.

### `_unreceived_supply_ids()`

Исходник: `supplies/services.py:669`.

Расчёты ожидающих и отменённых до приёмки приходов не входят в историю склада.

Статические вызовы: `Q`, `Supply.objects.filter`, `Supply.objects.filter(Q(status__in=(Supply.Status.PRICE_REVIEW_REQUIRED, Supply.Status.WAITING_TRIP_FINALIZATION)) | Q(status=Supply.Status.CANCELLED, revisions__diff_summary__unreceived_cancelled=True)).values`.

### `_replay_product_valuation(*, supply, product_type, product, incoming, old_target_calculation)`

Исходник: `supplies/services.py:677`.

Replays one product from the edited supply's original historical position.

Статические вызовы: `SupplyCostCalculation.objects.create`, `SupplyCostCalculation.objects.filter`, `SupplyCostCalculation.objects.filter(supply=supply, **product_filter).delete`, `SupplyCostCalculation.objects.select_for_update`, `SupplyCostCalculation.objects.select_for_update().select_related`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter(product_kind=product_type, supply__accepted_at__gt=supply.accepted_at, **product_filter).exclude`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter(product_kind=product_type, supply__accepted_at__gt=supply.accepted_at, **product_filter).exclude(supply_id__in=_unreceived_supply_ids()).order_by`, `ValidationError`, `_calculation_values`, `_external_owned_quantity_delta`, `_old_owned_quantity`, `_replay_external_warehouse_events`, `_supply_configuration`, `_unreceived_supply_ids`, `calculation.save`, `first.old_unit_cost.quantize`, `item_model.objects.filter`, `item_model.objects.filter(product_id=product.pk, supply__accepted_at__gt=supply.accepted_at).exclude`, `item_model.objects.filter(product_id=product.pk, supply__accepted_at__gt=supply.accepted_at).exclude(supply_id__in=_unreceived_supply_ids()).values_list`, `list`, `old_target_calculation.old_unit_cost.quantize`, `product.cost.quantize`, `product.full_clean`, `product.save`, `set`, `setattr`, `timezone.now`, `values.items`.

### `revise_supply(*, actor, supply_id, expected_revision_number, warehouse_id, lines, expenses, weight_transport_cost, reason)`

Исходник: `supplies/services.py:776`.

Декораторы: `transaction.atomic`.

Сохраняет ревизию принятого прихода и воспроизводит связанную оценку. Завершённые снимки старых продаж не заменяет текущей cost.

Статические вызовы: `'; '.join`, `(goods_total + expenses_total + weight_transport_cost).quantize`, `(line.purchase_unit_cost * line.quantity).quantize`, `CD.objects.active`, `CD.objects.active().select_for_update`, `CD.objects.active().select_for_update().filter`, `CD.objects.active().select_for_update().filter(pk__in=affected_cd_ids).order_by`, `Decimal`, `Supplier.objects.in_bulk`, `Supply.objects.select_for_update`, `Supply.objects.select_for_update().select_related`, `Supply.objects.select_for_update().select_related('warehouse', 'accepted_by').get`, `SupplyCDItem`, `SupplyCDItem.objects.bulk_create`, `SupplyCDItem.objects.filter`, `SupplyCDItem.objects.filter(supply=supply).delete`, `SupplyCostCalculation.objects.select_for_update`, `SupplyCostCalculation.objects.select_for_update().filter`, `SupplyExpense`, `SupplyExpense.objects.bulk_create`, `SupplyExpense.objects.filter`, `SupplyExpense.objects.filter(supply=supply).delete`, `SupplyRevisionResult`, `SupplyTechItem`, `SupplyTechItem.objects.bulk_create`, `SupplyTechItem.objects.filter`, `SupplyTechItem.objects.filter(supply=supply).delete`, `Tech.objects.active`, `Tech.objects.active().select_for_update`, `Tech.objects.active().select_for_update().filter`, `Tech.objects.active().select_for_update().filter(pk__in=affected_tech_ids).order_by`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().filter`, `Warehouse.objects.select_for_update().filter(pk=supply.warehouse_id).get`, `Warehouse.objects.select_for_update().get`, `_normalise_expenses`, `_normalise_lines`, `_normalise_weight_transport_cost`, `_replay_product_valuation`, `_snapshot_supply_revision`, `_supersede_supply_finalizations`, `_supply_configuration`, `allocate_weight_transport_cost`, `change_stock`, `changes.append`, `clear_storage_locations_if_zero`, `defaultdict`, `dict`, `effective_cost.quantize`, `enumerate`, `expense_per_unit.quantize`, `expenses_total.quantize`, `field_change`, `getattr`, `goods_total.quantize`, `incoming_additions.get`, `incoming_line_value.quantize`, `insufficient.append`, `int`, `item_model.objects.select_for_update`, `item_model.objects.select_for_update().select_related`, `item_model.objects.select_for_update().select_related('product', 'supplier').filter`, `item_model.objects.select_for_update().select_related('product', 'supplier').filter(supply=supply).order_by`, `len`, `line.purchase_unit_cost.quantize`, `list`, `localcontext`, `logger.exception`, `logger.info`, `logger.warning`, `new_cd_items.append`, `new_quantities.get`, `new_quantities.items`, `new_tech_items.append`, `old_calculations.get`, `old_items.extend`, `old_quantities.get`, `old_quantities.items`, `record_product_changes`, `set`, `sorted`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_changes[key].append`, `stock_model`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse_id__in=warehouse_ids, **{f'{product_field}_id__in': ids}).order_by`, `stocks.get`, `stocks.update`, `str`, `str(reason or '').strip`, `sum`, `supply.full_clean`, `supply.save`, `timezone.now`, `transport_per_unit.quantize`, `validate_supply_snapshot`.

### `_recalculated_cost(*, product_type, product_id, excluded_supply_id)`

Исходник: `supplies/services.py:1083`.

Повторяет сохранённую moving-average историю, исключая отменённые поставки.

Статические вызовы: `(replay_value / Decimal(replay_quantity)).quantize`, `Decimal`, `SupplyCostCalculation.objects.select_for_update`, `SupplyCostCalculation.objects.select_for_update().select_related`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter(product_kind=product_type, **product_filter).exclude`, `SupplyCostCalculation.objects.select_for_update().select_related('supply').filter(product_kind=product_type, **product_filter).exclude(supply_id__in=_unreceived_supply_ids()).order_by`, `ValidationError`, `_replay_external_warehouse_events`, `_supply_configuration`, `_unreceived_supply_ids`, `first.old_unit_cost.quantize`, `item_model.objects.filter`, `item_model.objects.filter(product_id=product_id, supply__accepted_at__gte=first.supply.accepted_at).exclude`, `item_model.objects.filter(product_id=product_id, supply__accepted_at__gte=first.supply.accepted_at).exclude(supply_id__in=_unreceived_supply_ids()).values_list`, `list`, `next`, `set`, `sum`, `timezone.now`.

### `cancel_supply(*, actor, supply_id, comment)`

Исходник: `supplies/services.py:1164`.

Декораторы: `transaction.atomic`.

Отменяет приход штатными количественными/стоимостными проверками и аудитом; не является удалением карточки товара.

Статические вызовы: `'; '.join`, `Supply.objects.select_for_update`, `Supply.objects.select_for_update().select_related`, `Supply.objects.select_for_update().select_related('warehouse').get`, `SupplyCancellationResult`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `_recalculated_cost`, `_snapshot_supply_revision`, `_supply_configuration`, `aggregated.items`, `aggregated.values`, `changes.append`, `clear_storage_locations_if_zero`, `defaultdict`, `field_change`, `getattr`, `insufficient.append`, `item_model.objects.select_for_update`, `item_model.objects.select_for_update().select_related`, `item_model.objects.select_for_update().select_related('product').filter`, `item_model.objects.select_for_update().select_related('product').filter(supply=supply).order_by`, `len`, `list`, `lock_document_trip`, `logger.info`, `logger.warning`, `product.full_clean`, `product.save`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().filter`, `product_model.objects.active().select_for_update().filter(pk__in=ids).order_by`, `products.items`, `products.update`, `record_product_changes`, `sorted`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse_id=supply.warehouse_id, **{f'{product_field}_id__in': ids}).order_by`, `stocks.get`, `stocks.update`, `str`, `str(comment or '').strip`, `sum`, `supply.full_clean`, `supply.save`, `timezone.now`.

## `supplies/urls.py`

Именованные HTTP-маршруты приложения приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует.

Импорты: `django.urls`.

## `supplies/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю приходов.

Проведение меняет остаток/оценку через сервис; предварительная проверка цен товар не приходует.

Импорты: `catalog.game_codes`, `catalog.models`, `catalog.product_fields`, `catalog.product_identifiers`, `catalog.product_search`, `core.decorators`, `django.contrib`, `django.contrib.auth.decorators`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `finalization`, `integrations.avito_check`, `models`, `orders.arrival_finalization`, `orders.arrival_models`, `orders.fulfillment_views`, `orders.models`, `partners.models`, `pricing.warnings`, `services`, `warehouse.form_defaults`, `warehouse.models`.

### `supply_list(request)`

Исходник: `supplies/views.py:42`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Count`, `Supply.objects.select_related`, `Supply.objects.select_related('accepted_by', 'warehouse', 'cancelled_by').annotate`, `list`, `permission_required`, `render`.

### `_parse_supply_post(post)`

Исходник: `supplies/views.py:51`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `all`, `len`, `post.get`, `post.getlist`, `range`, `zip`.

### `_parse_finalization_post(post)`

Исходник: `supplies/views.py:75`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `len`, `post.getlist`, `range`, `values.values`.

### `_submitted_supply_lines(post, user=None)`

Исходник: `supplies/views.py:90`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `enumerate`, `getattr`, `len`, `model.objects.active`, `model.objects.active().select_related`, `model.objects.active().select_related('platform' if product_type == 'cd' else 'product_type').get`, `post.getlist`, `requires_game_codes`, `rows.append`, `user.has_perm`, `value`.

### `_submitted_expenses(post)`

Исходник: `supplies/views.py:134`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `max`, `post.getlist`, `range`.

### `_supplier_options(user)`

Исходник: `supplies/views.py:147`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Supplier.objects.order_by`, `Supplier.objects.order_by('letter').values`, `user.has_perm`.

### `_current_supply_lines(supply, user)`

Исходник: `supplies/views.py:158`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `getattr(supply, related_name).select_related`, `requires_game_codes`, `rows.append`, `str`, `user.has_perm`.

### `supply_create(request)`

Исходник: `supplies/views.py:184`.

Декораторы: `permission_required('supplies.add_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Warehouse.objects.all`, `_parse_supply_post`, `_submitted_expenses`, `_submitted_supply_lines`, `_supplier_options`, `accept_supply`, `logger.warning`, `messages.error`, `messages.success`, `permission_required`, `redirect`, `render`, `request.GET.get`, `request.POST.get`, `single_warehouse_id`, `str`, `str(exc).lower`, `trip_supply_create`.

### `supply_edit(request, pk)`

Исходник: `supplies/views.py:226`.

Декораторы: `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `Supply.objects.select_related`, `ValidationError`, `Warehouse.objects.all`, `_current_supply_lines`, `_parse_supply_post`, `_submitted_expenses`, `_submitted_supply_lines`, `_supplier_options`, `edit_pending_supply if pending else revise_supply`, `get_object_or_404`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `str`, `supply.expenses.all`, `supply.refresh_from_db`.

### `supply_detail(request, pk)`

Исходник: `supplies/views.py:291`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Supply.objects.select_related`, `TripArrival.objects.filter`, `TripArrival.objects.filter(trip__trip_orders__operations__supply=supply).first`, `get_object_or_404`, `len`, `permission_required`, `render`, `request.user.has_perm`, `rows.append`, `supply.cd_items.all`, `supply.cost_calculations.select_related`, `supply.expenses.all`, `supply.finalizations.select_related`, `supply.finalizations.select_related('created_by').prefetch_related`, `supply.revisions.select_related`, `supply.tech_items.all`, `supply_has_complete_cost_calculations`.

### `supply_price_review(request, pk)`

Исходник: `supplies/views.py:358`.

Декораторы: `permission_required('supplies.add_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `MARKUP_FOR_PRICE.get`, `PRICE_PERMISSIONS.items`, `PermissionDenied`, `Supply.objects.select_related`, `Supply.objects.select_related('warehouse', 'accepted_by').prefetch_related`, `TripOrderOperation.objects.filter`, `TripOrderOperation.objects.filter(supply_id=pk, active=True, calculation__has_key='arrival_id').first`, `bool`, `confirm_supply_price_review`, `get_object_or_404`, `getattr`, `manual_search_url`, `messages.error`, `messages.success`, `permission_required`, `prepare_supply_price_review`, `price_warning`, `redirect`, `render`, `request.POST.get`, `request.user.has_perm`, `rows.append`, `supply.cost_calculations.all`, `values.get`, `wholesale_margin`.

### `supply_finalization(request, pk)`

Исходник: `supplies/views.py:426`.

Декораторы: `permission_required('supplies.finalize_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `_parse_finalization_post`, `apply_supply_finalization`, `calculate_finalization_penalty`, `finalization.items.count`, `get_object_or_404`, `get_supply_finalization_context`, `isinstance`, `messages.error`, `messages.success`, `permission_required`, `redirect`, `render`, `request.POST.get`.

### `supply_finalization_auto(request, pk)`

Исходник: `supplies/views.py:463`.

Декораторы: `require_POST`; `permission_required('supplies.finalize_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `_parse_finalization_post`, `auto_distribute_penalty`, `calculate_finalization_penalty`, `get_object_or_404`, `get_supply_finalization_context`, `int`, `parse_finalization_inputs`, `permission_required`, `request.POST.getlist`, `rows_from_inputs`, `selected.add`, `set`, `value.partition`.

### `supply_revision_detail(request, pk, revision_number)`

Исходник: `supplies/views.py:496`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SupplyRevision.objects.select_related`, `get_object_or_404`, `item.get_product_kind_display`, `len`, `permission_required`, `render`, `request.user.has_perm`, `revision.expenses.all`, `revision.items.all`.

### `supply_cancel(request, pk)`

Исходник: `supplies/views.py:527`.

Декораторы: `require_POST`; `permission_required('supplies.cancel_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `cancel_supply`, `isinstance`, `messages.error`, `messages.info`, `messages.success`, `permission_required`, `redirect`, `request.POST.get`.

### `product_autocomplete(request)`

Исходник: `supplies/views.py:550`.

Декораторы: `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply', 'consignment.transfer_stock', 'consignment.return_stock', 'warehouse.create_transfer', 'sales.create_sale', 'sales.edit_unpaid_postpay_sale')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').prefetch_related`, `CD.objects.active().select_related('platform').prefetch_related('barcodes').order_by`, `CDWarehouseStock.objects.filter`, `CDWarehouseStock.objects.filter(cd_id__in=cd_ids).values`, `CDWarehouseStock.objects.filter(cd_id__in=cd_ids).values('cd_id').annotate`, `CDWarehouseStock.objects.filter(cd_id__in=cd_ids).values('cd_id').annotate(total=Sum('quantity')).values_list`, `CDWarehouseStock.objects.filter(quantity__gt=0, cd_id__in=cd_ids).values_list`, `CDWarehouseStock.objects.filter(quantity__gt=0, cd_id__in=cd_ids).values_list('cd_id', 'warehouse_id').order_by`, `CDWarehouseStock.objects.filter(warehouse_id=warehouse_id, cd_id__in=cd_ids).values_list`, `CDWarehouseStock.objects.values`, `CDWarehouseStock.objects.values('cd_id').annotate`, `CDWarehouseStock.objects.values('cd_id').annotate(total=Sum('quantity')).filter`, `CDWarehouseStock.objects.values('cd_id').annotate(total=Sum('quantity')).filter(total__gt=0).values_list`, `CDWarehouseStorageAssignment.objects.filter`, `CDWarehouseStorageAssignment.objects.filter(stock__warehouse_id=warehouse_id, stock__cd_id__in=cd_ids).order_by`, `CDWarehouseStorageAssignment.objects.filter(stock__warehouse_id=warehouse_id, stock__cd_id__in=cd_ids).order_by('stock__cd_id', 'position', 'id').values_list`, `JsonResponse`, `Sum`, `SystemProduct.objects.select_related`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.active().select_related('product_type').prefetch_related`, `Tech.objects.active().select_related('product_type').prefetch_related('barcodes').order_by`, `TechWarehouseStock.objects.filter`, `TechWarehouseStock.objects.filter(quantity__gt=0, tech_id__in=tech_ids).values_list`, `TechWarehouseStock.objects.filter(quantity__gt=0, tech_id__in=tech_ids).values_list('tech_id', 'warehouse_id').order_by`, `TechWarehouseStock.objects.filter(tech_id__in=tech_ids).values`, `TechWarehouseStock.objects.filter(tech_id__in=tech_ids).values('tech_id').annotate`, `TechWarehouseStock.objects.filter(tech_id__in=tech_ids).values('tech_id').annotate(total=Sum('quantity')).values_list`, `TechWarehouseStock.objects.filter(warehouse_id=warehouse_id, tech_id__in=tech_ids).values_list`, `TechWarehouseStock.objects.values`, `TechWarehouseStock.objects.values('tech_id').annotate`, `TechWarehouseStock.objects.values('tech_id').annotate(total=Sum('quantity')).filter`, `TechWarehouseStock.objects.values('tech_id').annotate(total=Sum('quantity')).filter(total__gt=0).values_list`, `TechWarehouseStorageAssignment.objects.filter`, `TechWarehouseStorageAssignment.objects.filter(stock__warehouse_id=warehouse_id, stock__tech_id__in=tech_ids).order_by`, `TechWarehouseStorageAssignment.objects.filter(stock__warehouse_id=warehouse_id, stock__tech_id__in=tech_ids).order_by('stock__tech_id', 'position', 'id').values_list`, `Warehouse.objects.filter`, `Warehouse.objects.filter(pk=warehouse_id).exists`, `any`, `barcode_values`, `bool`, `cd_available.get`, `cd_locations.get`, `cd_locations.setdefault`, `cd_locations.setdefault(product_id, []).append`, `cd_warehouse_ids.get`, `cd_warehouse_ids.setdefault`, `cd_warehouse_ids.setdefault(product_id, []).append`, `cds.filter`, `dict`, `getattr`, `int`, `item.barcodes.all`, `len`, `list`, `next`, `permission_required_any`, `product.name.casefold`, `query.casefold`, `raw_items.split`, `request.GET.get`, `request.GET.get('context', '').strip`, `request.GET.get('items', '').strip`, `request.GET.get('q', '').strip`, `request.user.has_perm`, `requested_ids[product_type].add`, `requires_game_codes`, `results.extend`, `results.insert`, `search_product_querysets`, `selected_barcode`, `set`, `tech.filter`, `tech_available.get`, `tech_locations.get`, `tech_locations.setdefault`, `tech_locations.setdefault(product_id, []).append`, `tech_warehouse_ids.get`, `tech_warehouse_ids.setdefault`, `tech_warehouse_ids.setdefault(product_id, []).append`, `token.split`, `token.strip`.

### `supply_product_codes(request)`

Исходник: `supplies/views.py:735`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `permission_required_any`, `request.POST.get`, `set_game_codes`.

### `supply_product_weight(request)`

Исходник: `supplies/views.py:746`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `permission_required_any`, `request.POST.get`, `request.POST.get('product_type', '').lower`, `request.user.has_perm`, `set_product_weight`, `{'cd': 'catalog.change_cd_weight', 'tech': 'catalog.change_tech_weight'}.get`.

### `supply_product_barcode(request)`

Исходник: `supplies/views.py:770`.

Декораторы: `require_POST`; `permission_required('supplies.add_supply', raise_exception=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `add_product_barcode`, `permission_required`, `request.POST.get`, `request.POST.get('product_type', '').lower`, `request.user.has_perm`, `str`, `str(exc).lower`, `{'cd': 'catalog.change_cd_barcode', 'tech': 'catalog.change_tech_barcode'}.get`.

## `telegram_bots/__init__.py`

Личный Telegram-доступ сотрудников к существующим сервисам CRM.

## `telegram_bots/access.py`

Одноразовая привязка числового Telegram ID; контакты User.telegram не используются.

Импорты: `core.db_retry`, `datetime`, `django.contrib.auth`, `django.contrib.auth.models`, `django.core.exceptions`, `django.db`, `django.utils`, `models`.

### `BotDenied.__init__(self, category='denied', message='Доступ закрыт. Проверьте привязку и разрешения в CRM.')`

Исходник: `telegram_bots/access.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `check_access(access, *, require_link=True)`

Исходник: `telegram_bots/access.py:19`.

Новый User на каждой проверке исключает устаревший кэш Django permissions.

Статические вызовы: `BotDenied`, `StaffBot.objects.get`, `get_user_model`, `get_user_model().objects.filter`, `get_user_model().objects.filter(pk=access.user_id, is_active=True).first`, `user.has_perm`.

### `authorize(bot, telegram_id)`

Исходник: `telegram_bots/access.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BotDenied`, `StaffBotAccess.objects.filter`, `StaffBotAccess.objects.filter(bot=bot, telegram_user_id=telegram_id).first`, `check_access`.

### `issue_link(user, bot)`

Исходник: `telegram_bots/access.py:40`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BotDenied`, `StaffBot.objects.select_for_update`, `StaffBot.objects.select_for_update().get`, `StaffBotAccess.objects.filter`, `StaffBotAccess.objects.filter(bot=bot, user=user).first`, `StaffBotLink.objects.create`, `access.staffbotlink_set.filter`, `check_access`, `hashlib.sha256`, `hashlib.sha256(token.encode()).hexdigest`, `old.save`, `secrets.token_urlsafe`, `timedelta`, `timezone.now`, `token.encode`.

### `consume_link(bot, token, telegram_id, username='')`

Исходник: `telegram_bots/access.py:58`.

Вызывается внутри атомарного приёма update с блокировкой конкретного бота.

Статические вызовы: `BotDenied`, `StaffBotAccess.objects.filter`, `StaffBotAccess.objects.filter(bot=bot, telegram_user_id=telegram_id).exists`, `StaffBotLink.objects.select_related`, `StaffBotLink.objects.select_related('access').filter`, `StaffBotLink.objects.select_related('access').filter(access__bot=bot, token_hash=hashlib.sha256(token.encode()).hexdigest(), used_at__isnull=True, expires_at__gt=timezone.now()).first`, `access.save`, `check_access`, `hashlib.sha256`, `hashlib.sha256(token.encode()).hexdigest`, `isinstance`, `len`, `link.save`, `str`, `timezone.now`, `token.encode`.

### `set_employee_access(actor, bot, user, allowed)`

Исходник: `telegram_bots/access.py:81`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Permission.objects.get`, `StaffBot.objects.select_for_update`, `StaffBot.objects.select_for_update().get`, `StaffBotAccess.objects.get_or_create`, `access.save`, `access.staffbotlink_set.filter`, `link.save`, `timezone.now`, `user.user_permissions.add`.

## `telegram_bots/apps.py`

Назначение уточнять по экспортируемым символам.

Импорты: `django.apps`.

## `telegram_bots/client.py`

Минимальный Bot API без повторов отправки и без исключений с URL/токеном.

Импорты: `core.external_policy`.

### `TelegramError.__init__(self, category, *, uncertain=False)`

Исходник: `telegram_bots/client.py:7`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `TelegramClient.__init__(self, token, session=None)`

Исходник: `telegram_bots/client.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `requests.Session`, `require_live_operation`.

### `TelegramClient.call(self, method, data=None, *, files=None)`

Исходник: `telegram_bots/client.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `TelegramError`, `ValueError`, `isinstance`, `payload.get`, `require_live_operation`, `response.json`, `self._session.post`, `{401: 'unauthorized', 403: 'forbidden', 409: 'conflict', 429: 'rate_limited'}.get`.

### `TelegramClient.message(self, chat_id, text, reply_markup=None)`

Исходник: `telegram_bots/client.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.call`.

### `TelegramClient.document(self, chat_id, filename, content)`

Исходник: `telegram_bots/client.py:48`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.call`.

### `TelegramClient.close(self)`

Исходник: `telegram_bots/client.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._session.close`.

## `telegram_bots/configuration.py`

Секрет читается лениво только в live. Тестовая CRM не открывает файл ключа.

Импорты: `core.external_policy`, `django.conf`, `django.core.exceptions`, `django.db`, `models`, `pathlib`.

### `token_path()`

Исходник: `telegram_bots/configuration.py:15`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `getattr`.

### `token_configured()`

Исходник: `telegram_bots/configuration.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `os.environ.get`, `token_path`, `token_path().is_file`.

### `read_token()`

Исходник: `telegram_bots/configuration.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `os.environ.get`, `require_live_operation`, `token_path`, `token_path().read_text`, `token_path().read_text(encoding='utf-8').strip`, `validate_token`.

### `validate_token(value)`

Исходник: `telegram_bots/configuration.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `re.fullmatch`, `str`, `str(value).strip`.

### `save_token(value)`

Исходник: `telegram_bots/configuration.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `Path(name).unlink`, `ValidationError`, `os.chmod`, `os.fdopen`, `os.replace`, `path.is_symlink`, `require_live_operation`, `stream.write`, `tempfile.mkstemp`, `token_path`, `validate_token`.

### `expected_status()`

Исходник: `telegram_bots/configuration.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.filter`, `StaffBot.objects.filter(code='staff').first`, `token_configured`.

## `telegram_bots/documents.py`

Тонкий адаптер существующего Excel; формулы и отбор товаров остаются в price.excel.

Импорты: `access`, `django.conf`, `django.core.exceptions`, `django.utils`, `price.excel`, `warehouse.models`.

### `wholesale_document(access, warehouse_id)`

Исходник: `telegram_bots/documents.py:10`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `Warehouse.objects.filter`, `Warehouse.objects.filter(pk=warehouse_id).exists`, `check_access`, `generate_wholesale_price_xlsx`, `getattr`, `len`, `timezone.localdate`.

## `telegram_bots/forms.py`

Назначение уточнять по экспортируемым символам.

Импорты: `configuration`, `django`, `models`.

### `StaffBotForm.clean_token(self)`

Исходник: `telegram_bots/forms.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.cleaned_data.get`, `validate_token`.

### `StaffBotForm.clean(self)`

Исходник: `telegram_bots/forms.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `os.environ.get`, `self.add_error`, `self.initial.get`, `super`, `super().clean`, `token_configured`, `values.get`.

## `telegram_bots/handlers.py`

Приём update сохраняет квитанцию и задание до сетевого ответа; XLSX здесь не строится.

Импорты: `access`, `core.db_retry`, `datetime`, `django.db`, `django.utils`, `menu`, `models`, `warehouse.models`.

### `_positive_id(value)`

Исходник: `telegram_bots/handlers.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `isinstance`.

### `_private_context(update)`

Исходник: `telegram_bots/handlers.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_positive_id`, `callback.get`, `chat.get`, `isinstance`, `message.get`, `sender.get`, `update.get`.

### `_request_price(bot, access, warehouse_id, receipt, chat_id)`

Исходник: `telegram_bots/handlers.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BotDenied`, `StaffBotJob.objects.create`, `StaffBotJob.objects.filter`, `StaffBotJob.objects.filter(access=access, created_at__gt=timezone.now() - timedelta(seconds=bot.cooldown_seconds)).exists`, `StaffBotJob.objects.filter(access=access, state__in=['queued', 'generating', 'sending']).exists`, `Warehouse.objects.filter`, `Warehouse.objects.filter(pk=warehouse_id).exists`, `timedelta`, `timezone.now`.

### `_dispatch(bot, update, receipt)`

Исходник: `telegram_bots/handlers.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BotDenied`, `Warehouse.objects.order_by`, `_private_context`, `_request_price`, `authorize`, `callback.get`, `consume_link`, `data.split`, `data.startswith`, `int`, `isinstance`, `len`, `list`, `main_menu`, `message.get`, `sender.get`, `text.split`, `text.split(' ', 1)[1].strip`, `text.startswith`, `value.isascii`, `value.isdecimal`, `warehouse_menu`.

### `accept_update(bot_id, update)`

Исходник: `telegram_bots/handlers.py:73`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.select_for_update`, `StaffBot.objects.select_for_update().get`, `StaffBotUpdate.objects.get_or_create`, `_dispatch`, `_private_context`, `bot.save`, `callback.get`, `isinstance`, `max`, `receipt.save`, `update.get`.

## `telegram_bots/jobs.py`

Один исполнитель XLSX, отдельный от polling. Неопределённая отправка не повторяется.

Импорты: `access`, `client`, `core.db_retry`, `django.core.exceptions`, `django.db`, `django.utils`, `documents`, `models`.

### `claim_job(bot_id)`

Исходник: `telegram_bots/jobs.py:14`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBotJob.objects.select_for_update`, `StaffBotJob.objects.select_for_update().filter`, `StaffBotJob.objects.select_for_update().filter(bot_id=bot_id, state='queued').first`, `job.save`, `timezone.now`.

### `finish_job(job, state, category='', message_id=None)`

Исходник: `telegram_bots/jobs.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `job.save`, `timezone.now`.

### `run_job(job, client, *, owner=None)`

Исходник: `telegram_bots/jobs.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BotDenied`, `StaffBotAccess.objects.get`, `TelegramError`, `access.refresh_from_db`, `bot.refresh_from_db`, `check_access`, `client.document`, `client.message`, `finish_job`, `isinstance`, `job.save`, `result.get`, `timezone.now`, `wholesale_document`.

### `recover_interrupted(bot_id)`

Исходник: `telegram_bots/jobs.py:73`.

Вызывается только после получения эксклюзивной аренды и блокировки процесса.

Статические вызовы: `StaffBotJob.objects.filter`, `finish_job`.

## `telegram_bots/management/commands/run_telegram_staff_bot.py`

Отдельный управляемый процесс; отсутствие настройки не мешает веб-серверу.

Импорты: `django.conf`, `django.core.exceptions`, `django.core.management.base`, `integrations.worker_heartbeat`, `integrations.worker_runtime`, `telegram_bots.configuration`, `telegram_bots.models`, `telegram_bots.worker`.

### `Command.add_arguments(self, parser)`

Исходник: `telegram_bots/management/commands/run_telegram_staff_bot.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `telegram_bots/management/commands/run_telegram_staff_bot.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.get`, `expected_status`, `graceful_shutdown`, `monitored_worker`, `run_polling`, `self.stderr.write`, `self.stdout.write`, `uuid.uuid4`.

## `telegram_bots/menu.py`

Компактный реестр: добавление функции не меняет авторизацию или транспорт.

Импорты: `dataclasses`.

### `main_menu(user)`

Исходник: `telegram_bots/menu.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FUNCTIONS.values`, `user.has_perm`.

### `warehouse_menu(warehouses)`

Исходник: `telegram_bots/menu.py:23`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `telegram_bots/models.py`

Только конфигурация, доступ и техническая очередь; товары и деньги не изменяются.

Импорты: `django.conf`, `django.db`, `django.db.models`.

## `telegram_bots/monitoring.py`

Безопасный снимок для штатной страницы обработчиков, без Telegram ID и HTTP-вызовов.

Импорты: `django.db`, `django.db.models`, `models`.

### `queue_snapshot()`

Исходник: `telegram_bots/monitoring.py:18`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ERROR_LABELS.get`, `Max`, `StaffBot.objects.filter`, `StaffBot.objects.filter(code='staff').first`, `StaffBotJob.objects.filter`, `StaffBotJob.objects.filter(bot=bot, state='done').aggregate`, `StaffBotJob.objects.filter(bot=bot, state__in=['error', 'uncertain']).exists`, `StaffBotJob.objects.filter(bot=bot, state__in=['queued', 'generating', 'sending']).first`, `job.get_state_display`.

## `telegram_bots/urls.py`

Назначение уточнять по экспортируемым символам.

Импорты: `django.urls`.

## `telegram_bots/views.py`

Настройки только superuser; сотрудник видит лишь собственную привязку.

Импорты: `access`, `accounts.views`, `client`, `configuration`, `django.conf`, `django.contrib`, `django.contrib.auth`, `django.contrib.auth.decorators`, `django.core.exceptions`, `django.db`, `django.shortcuts`, `django.views.decorators.cache`, `django.views.decorators.debug`, `django.views.decorators.http`, `forms`, `integrations.worker_models`, `integrations.worker_monitoring`, `models`, `monitoring`.

### `_stub(request)`

Исходник: `telegram_bots/views.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `render`.

### `dashboard(request)`

Исходник: `telegram_bots/views.py:32`.

Декораторы: `sensitive_post_parameters('token')`; `superuser_required`; `never_cache`; `require_http_methods(['GET', 'POST'])`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ERROR_LABELS.get`, `STATUS_LABELS.get`, `StaffBot`, `StaffBot.objects.filter`, `StaffBot.objects.filter(code='staff').first`, `StaffBotAccess.objects.filter`, `StaffBotAccess.objects.filter(bot=bot).select_related`, `StaffBotForm`, `StaffBotJob.objects.filter`, `StaffBotJob.objects.filter(bot=bot).select_related`, `TelegramClient`, `TelegramError`, `WorkerService.objects.filter`, `WorkerService.objects.filter(code='telegram_staff').first`, `_stub`, `bool`, `bot.username.lower`, `by_user.get`, `client.call`, `client.close`, `expected_status`, `form.add_error`, `form.cleaned_data.get`, `form.is_valid`, `form.save`, `get_object_or_404`, `get_user_model`, `get_user_model().objects.order_by`, `getattr`, `isinstance`, `issue_link`, `list`, `logger.info`, `me.get`, `messages.error`, `messages.success`, `read_token`, `redirect`, `render`, `request.POST.get`, `require_http_methods`, `save_token`, `sensitive_post_parameters`, `set_employee_access`, `str`, `str(me.get('username', '')).lower`, `sum`, `token_configured`, `user.has_perm`, `webhook.get`.

### `connection(request)`

Исходник: `telegram_bots/views.py:105`.

Декораторы: `login_required`; `never_cache`; `require_http_methods(['GET', 'POST'])`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.filter`, `StaffBot.objects.filter(code='staff').first`, `StaffBotAccess.objects.filter`, `StaffBotAccess.objects.filter(bot=bot, user=request.user).first`, `ValidationError`, `_stub`, `issue_link`, `render`, `require_http_methods`.

## `telegram_bots/worker.py`

Long polling и исполнитель используют разные соединения; мониторинг — существующий.

Импорты: `client`, `configuration`, `core.db_retry`, `core.external_policy`, `datetime`, `django.db`, `django.utils`, `handlers`, `integrations.worker_runtime`, `jobs`, `models`.

### `lease(bot_id, owner, *, release=False)`

Исходник: `telegram_bots/worker.py:18`.

Декораторы: `retry_database_lock`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AlreadyRunning`, `StaffBot.objects.select_for_update`, `StaffBot.objects.select_for_update().get`, `bot.save`, `timedelta`, `timezone.now`.

### `connection_state(bot_id, category='')`

Исходник: `telegram_bots/worker.py:28`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.get`, `bot.save`, `fields.append`, `timezone.now`.

### `dispatch_reply(client, reply)`

Исходник: `telegram_bots/worker.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `client.call`, `client.message`, `reply.get`.

### `job_loop(bot_id, stop, owner, client_factory)`

Исходник: `telegram_bots/worker.py:49`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.get`, `claim_job`, `client.close`, `client_factory`, `close_old_connections`, `connections.close_all`, `read_token`, `run_job`, `stop.is_set`, `stop.wait`, `timezone.now`.

### `run_polling(bot_id, owner, stop, *, client_factory=TelegramClient, once=False)`

Исходник: `telegram_bots/worker.py:73`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StaffBot.objects.get`, `TelegramError`, `accept_update`, `bot.username.lower`, `client.call`, `client.close`, `client_factory`, `close_old_connections`, `connection_state`, `connections.close_all`, `dispatch_reply`, `executor.is_alive`, `executor.join`, `executor.start`, `executor_stop.set`, `expected_status`, `isinstance`, `lease`, `me.get`, `min`, `read_token`, `recover_interrupted`, `require_live_operation`, `stop.is_set`, `stop.wait`, `str`, `str(me.get('username', '')).lower`, `threading.Event`, `threading.Thread`, `webhook.get`.

## `warehouse/admin.py`

Регистрация моделей и разрешённых действий в Django Admin складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `django.contrib`, `models`.

### `CurrentStockAdmin.has_add_permission(self, request)`

Исходник: `warehouse/admin.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CurrentStockAdmin.has_change_permission(self, request, obj=None)`

Исходник: `warehouse/admin.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CurrentStockAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `warehouse/admin.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TransferHistoryAdmin.has_add_permission(self, request)`

Исходник: `warehouse/admin.py:74`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TransferHistoryAdmin.has_change_permission(self, request, obj=None)`

Исходник: `warehouse/admin.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TransferHistoryAdmin.has_delete_permission(self, request, obj=None)`

Исходник: `warehouse/admin.py:80`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `warehouse/apps.py`

Конфигурация приложения и его регистрация в Django складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `django.apps`.

### `WarehouseConfig.ready(self)`

Исходник: `warehouse/apps.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `warehouse/form_defaults.py`

Подстановка складских значений формы из доступного пользователю контекста.

Импорты: `django`, `models`.

### `single_warehouse_id()`

Исходник: `warehouse/form_defaults.py:7`.

Возвращает склад по умолчанию, только если во всей базе он один.

Статические вызовы: `Warehouse.objects.values_list`, `len`, `list`.

### `SingleWarehouseInitialMixin.__init__(self, *args, **kwargs)`

Исходник: `warehouse/form_defaults.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `field.queryset.filter`, `field.queryset.filter(pk=warehouse_id).exists`, `isinstance`, `self.fields.items`, `self.initial.get`, `single_warehouse_id`, `super`, `super().__init__`.

## `warehouse/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `django`, `form_defaults`, `models`.

### `WarehouseTransferForm.__init__(self, *args, source_warehouse, **kwargs)`

Исходник: `warehouse/forms.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Warehouse.objects.exclude`, `super`, `super().__init__`.

## `warehouse/inventory.py`

Канонический физический остаток всех складов для внешних площадок.

Импорты: `django.db.models`.

### `global_stock(product)`

Исходник: `warehouse/inventory.py:5`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `int`, `product.warehouse_stocks.aggregate`.

## `warehouse/models.py`

Схема данных, ограничения БД и вычисляемые свойства состояния складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `catalog.models`, `django.conf`, `django.core.exceptions`, `django.core.validators`, `django.db`, `storage_locations`.

### `Warehouse.__str__(self)`

Исходник: `warehouse/models.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `WarehouseStorageLocation._normalise_components(self)`

Исходник: `warehouse/models.py:65`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `StorageLocationValue`, `ValidationError`, `any`, `int`, `len`, `list`, `sorted`, `str`, `str(self.room or '').upper`, `tuple`.

### `WarehouseStorageLocation.full_clean(self, *args, **kwargs)`

Исходник: `warehouse/models.py:85`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self._normalise_components`, `super`, `super().full_clean`.

### `WarehouseStorageLocation.save(self, *args, **kwargs)`

Исходник: `warehouse/models.py:89`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.full_clean`, `super`, `super().save`.

### `WarehouseStorageLocation.__str__(self)`

Исходник: `warehouse/models.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CDWarehouseStock.__str__(self)`

Исходник: `warehouse/models.py:113`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `TechWarehouseStock.__str__(self)`

Исходник: `warehouse/models.py:133`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `WarehouseStorageAssignmentBase.clean(self)`

Исходник: `warehouse/models.py:147`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `super`, `super().clean`.

### `WarehouseStorageAssignmentBase.save(self, *args, **kwargs)`

Исходник: `warehouse/models.py:152`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.full_clean`, `super`, `super().save`.

### `WarehouseTransfer.position_count(self)`

Исходник: `warehouse/models.py:295`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.cd_items.count`, `self.tech_items.count`.

### `WarehouseTransfer.total_units(self)`

Исходник: `warehouse/models.py:299`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.cd_items.all`, `self.tech_items.all`, `sum`.

### `WarehouseTransfer.__str__(self)`

Исходник: `warehouse/models.py:304`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `warehouse/receipts.py`

Приём физически полученного возврата; идемпотентность задаёт документ-источник.

Импорты: `catalog.audit`, `catalog.models`, `django.db`, `models`, `services`.

### `receive_return(*, actor, warehouse_id, lines, label, sale_id)`

Исходник: `warehouse/receipts.py:10`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `normalise_product_lines`, `product_model.objects.select_for_update`, `product_model.objects.select_for_update().get`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_configuration`, `stock_model.objects.get_or_create`.

## `warehouse/revision_services.py`

Общие для склада циклы проверки; физические остатки здесь только читаются.

Импорты: `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `functools`, `itertools`, `models`, `storage_locations`, `storage_services`, `time`.

### `_retry_busy(operation)`

Исходник: `warehouse/revision_services.py:24`.

Повторяет целую короткую транзакцию при конкуренции записей SQLite.

Статические вызовы: `RevisionConflict`, `operation`, `range`, `sleep`, `str`, `str(exc).lower`, `wraps`.

### `allowed_kinds(user)`

Исходник: `warehouse/revision_services.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `tuple`, `user.has_perm`.

### `start_revision(*, warehouse_id, actor, expected_revision_id)`

Исходник: `warehouse/revision_services.py:47`.

Декораторы: `_retry_busy`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `RevisionConflict`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `WarehouseRevision.objects.create`, `WarehouseRevision.objects.filter`, `WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first`, `actor.has_perm`, `current.save`, `timezone.now`.

### `set_checked(*, warehouse_id, revision_id, kind, product_id, checked, actor)`

Исходник: `warehouse/revision_services.py:63`.

Декораторы: `_retry_busy`; `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `PermissionDenied`, `RevisionConflict`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `WarehouseRevision.objects.create`, `WarehouseRevision.objects.filter`, `WarehouseRevision.objects.filter(warehouse_id=warehouse_id).exists`, `WarehouseRevision.objects.filter(warehouse_id=warehouse_id, is_active=True).first`, `WarehouseRevisionItem.objects.get_or_create`, `actor.has_perm`, `allowed_kinds`, `item.save`, `model.objects.select_for_update`, `model.objects.select_for_update().filter`, `model.objects.select_for_update().filter(warehouse_id=warehouse_id, **{f'{kind}_id': product_id}).first`, `timezone.now`.

### `revision_rows(*, warehouse, revision, kinds)`

Исходник: `warehouse/revision_services.py:91`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Prefetch`, `assignment.objects.select_related`, `assignment.objects.select_related('location').order_by`, `bool`, `getattr`, `list`, `model.objects.filter`, `model.objects.filter(warehouse=warehouse, quantity__gt=0).select_related`, `model.objects.filter(warehouse=warehouse, quantity__gt=0).select_related(f'{kind}__{relation}').prefetch_related`, `parse_storage_location`, `revision.items.all`, `rows.append`, `states.get`, `stock.storage_assignments.all`, `storage_locations_for_stock`.

### `grouped_rows(rows, mode)`

Исходник: `warehouse/revision_services.py:123`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `group[0].upper`, `groupby`, `list`, `row['group'].casefold`, `row['product'].name.casefold`, `sorted`.

### `progress(rows)`

Исходник: `warehouse/revision_services.py:134`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `len`, `round`, `sum`.

## `warehouse/revision_views.py`

Мобильная ревизия локального склада и защищённые действия.

Импорты: `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `models`, `revision_services`.

### `revision_page(request, pk)`

Исходник: `warehouse/revision_views.py:18`.

Декораторы: `require_GET`; `permission_required_any(*ACCESS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehouseRevision.objects.filter`, `WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first`, `allowed_kinds`, `get_object_or_404`, `grouped_rows`, `len`, `permission_required_any`, `progress`, `render`, `request.GET.get`, `request.user.has_perm`, `revision_rows`.

### `revision_start(request, pk)`

Исходник: `warehouse/revision_views.py:34`.

Декораторы: `require_POST`; `permission_required_any('warehouse.view_warehouse_stock')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `ValidationError`, `get_object_or_404`, `int`, `isinstance`, `messages.error`, `messages.success`, `permission_required_any`, `redirect`, `request.POST.get`, `start_revision`.

### `revision_check(request, pk)`

Исходник: `warehouse/revision_views.py:50`.

Декораторы: `require_POST`; `permission_required_any(*ACCESS)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `WarehouseRevision.objects.filter`, `WarehouseRevision.objects.filter(warehouse=warehouse, is_active=True).first`, `allowed_kinds`, `get_object_or_404`, `int`, `next`, `permission_required_any`, `progress`, `request.POST.get`, `revision_rows`, `set_checked`.

## `warehouse/services.py`

Атомарные операции с межскладскими перемещениями.

Импорты: `catalog.audit`, `catalog.models`, `collections`, `django.core.exceptions`, `django.db`, `django.utils`, `models`, `storage_services`, `valuation`.

### `stock_configuration(product_type)`

Исходник: `warehouse/services.py:25`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `normalise_product_lines(raw_lines)`

Исходник: `warehouse/services.py:33`.

Проверяет строки и объединяет повторы одного товара.

Статические вызовы: `ValidationError`, `defaultdict`, `grouped.items`, `int`, `raw.get`, `str`, `str(raw.get('product_type', '')).lower`.

### `create_transfer(*, actor, source_warehouse_id, destination_warehouse_id, lines)`

Исходник: `warehouse/services.py:57`.

Декораторы: `transaction.atomic`.

Списывает товар у отправителя и фиксирует неизменяемый состав перемещения.

Статические вызовы: `CDWarehouseTransferItem`, `CDWarehouseTransferItem.objects.bulk_create`, `TechWarehouseTransferItem`, `TechWarehouseTransferItem.objects.bulk_create`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().filter`, `Warehouse.objects.select_for_update().filter(pk__in=(source_id, destination_id)).order_by`, `WarehouseTransfer.objects.create`, `cd_items.append`, `clear_storage_locations_if_zero`, `getattr`, `int`, `len`, `logger.info`, `normalise_product_lines`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().filter`, `product_model.objects.active().select_for_update().filter(pk__in=ids).order_by`, `products.update`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_configuration`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse_id=source_id, **{f'{product_field}_id__in': ids}).order_by`, `stocks.get`, `stocks.update`, `sum`, `tech_items.append`.

### `advance_transfer_status(*, actor, transfer_id, next_status)`

Исходник: `warehouse/services.py:157`.

Декораторы: `transaction.atomic`.

Выполняет только следующий переход; при приёмке зачисляет товар получателю.

Статические вызовы: `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `WarehouseTransfer.objects.select_for_update`, `WarehouseTransfer.objects.select_for_update().select_related`, `WarehouseTransfer.objects.select_for_update().select_related('source_warehouse', 'destination_warehouse').get`, `changes.append`, `existing.get`, `field_change`, `getattr`, `list`, `logger.info`, `product.full_clean`, `product.save`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().filter`, `record_product_changes`, `stock.full_clean`, `stock.save`, `stock_change`, `stock_model`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `timezone.now`, `transfer.cd_items.all`, `transfer.save`, `transfer.tech_items.all`, `transitions.get`, `update_fields.extend`, `warehouse_owned_quantity`, `weighted_warehouse_cost`.

## `warehouse/signals.py`

Реакции на сохранение моделей и запуск связанных действий складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `catalog.models`, `django.db.models`, `django.db.models.signals`, `django.dispatch`, `django.utils`, `models`.

### `_refresh_zero_stock_marker(*, product_model, product_id)`

Исходник: `warehouse/signals.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `product.warehouse_stocks.aggregate`, `product_model.objects.filter`, `product_model.objects.filter(pk=product_id).only`, `product_model.objects.filter(pk=product_id).only('zero_stock_since', 'has_been_in_stock').first`, `product_model.objects.filter(pk=product_id).update`, `timezone.now`.

### `refresh_cd_zero_stock_since(sender, instance, **kwargs)`

Исходник: `warehouse/signals.py:34`.

Декораторы: `receiver(post_save, sender=CDWarehouseStock)`; `receiver(post_delete, sender=CDWarehouseStock)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_refresh_zero_stock_marker`, `receiver`.

### `refresh_tech_zero_stock_since(sender, instance, **kwargs)`

Исходник: `warehouse/signals.py:40`.

Декораторы: `receiver(post_save, sender=TechWarehouseStock)`; `receiver(post_delete, sender=TechWarehouseStock)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_refresh_zero_stock_marker`, `receiver`.

### `_invalidate_revision_check(instance, *, deleted=False)`

Исходник: `warehouse/signals.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehouseRevisionItem.objects.filter`, `WarehouseRevisionItem.objects.filter(revision__warehouse_id=instance.warehouse_id, revision__is_active=True, invalidated_at__isnull=True, **{f'{kind}_id': getattr(instance, f'{kind}_id')}).update`, `getattr`, `isinstance`, `timezone.now`.

### `invalidate_revision_on_zero(sender, instance, raw=False, **kwargs)`

Исходник: `warehouse/signals.py:58`.

Декораторы: `receiver(post_save, sender=CDWarehouseStock)`; `receiver(post_save, sender=TechWarehouseStock)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_invalidate_revision_check`, `receiver`.

### `invalidate_revision_on_delete(sender, instance, **kwargs)`

Исходник: `warehouse/signals.py:65`.

Декораторы: `receiver(post_delete, sender=CDWarehouseStock)`; `receiver(post_delete, sender=TechWarehouseStock)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_invalidate_revision_check`, `receiver`.

## `warehouse/storage_locations.py`

Единый parser и normalizer физических мест хранения склада.

Импорты: `dataclasses`, `django.core.exceptions`.

### `StorageLocationValue.canonical(self)`

Исходник: `warehouse/storage_locations.py:32`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'\\'.join`, `str`.

### `_normalised_text(value)`

Исходник: `warehouse/storage_locations.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `str`, `str(value or '').replace`, `str(value or '').replace('–', '-').replace`, `str(value or '').replace('–', '-').replace('—', '-').strip`.

### `_positive_number(value)`

Исходник: `warehouse/storage_locations.py:51`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `int`.

### `parse_storage_location(value)`

Исходник: `warehouse/storage_locations.py:58`.

Разбирает одно место хранения по новому каноническому формату.

Статические вызовы: `StorageLocationValue`, `ValidationError`, `_LOCATION_RE.fullmatch`, `_normalised_text`, `_positive_number`, `match.groups`, `part.strip`, `raw_columns.split`, `room.upper`, `sorted`, `tuple`.

### `parse_storage_location_list(value)`

Исходник: `warehouse/storage_locations.py:75`.

Разбирает список locations, где запятая разделяет только разные места.

Статические вызовы: `ValidationError`, `_normalised_text`, `any`, `parse_storage_location`, `result.append`, `seen.add`, `set`, `text.split`, `token.strip`, `tuple`.

### `normalize_storage_location_list(value)`

Исходник: `warehouse/storage_locations.py:93`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `parse_storage_location_list`.

### `parse_storage_location_query(value)`

Исходник: `warehouse/storage_locations.py:97`.

Разбирает иерархический GET-фильтр: A, A1, A1-2 или A1-2-1.

Статические вызовы: `StorageLocationQuery`, `ValidationError`, `_QUERY_RE.fullmatch`, `_normalised_text`, `_positive_number`, `match.groups`, `part.strip`, `raw_columns.split`, `room.upper`, `sorted`, `tuple`.

### `normalize_location_autocomplete_token(value)`

Исходник: `warehouse/storage_locations.py:119`.

Безопасно упрощает только последний незавершённый token для подсказок.

Статические вызовы: `_normalised_text`, `_normalised_text(value).rsplit`, `re.sub`, `re.sub('\\s+', '', token).upper`.

## `warehouse/storage_services.py`

Атомарные операции с физическими местами хранения товарных остатков.

Импорты: `catalog.audit`, `catalog.models`, `dataclasses`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`, `storage_locations`.

### `assignment_configuration(product_type)`

Исходник: `warehouse/storage_services.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `storage_stock_configuration(product_type)`

Исходник: `warehouse/storage_services.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`.

### `storage_locations_value(assignments)`

Исходник: `warehouse/storage_services.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`.

### `storage_locations_for_stock(stock)`

Исходник: `warehouse/storage_services.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `stock.storage_assignments.all`, `storage_locations_value`.

### `storage_location_product_ids(*, warehouse, raw_query, include_cd=True, include_tech=True)`

Исходник: `warehouse/storage_services.py:60`.

Возвращает product IDs по структурному GET-фильтру, без substring-сравнений.

Статические вызовы: `CDWarehouseStorageAssignment.objects.filter`, `CDWarehouseStorageAssignment.objects.filter(location_id__in=location_ids, stock__warehouse=warehouse).values_list`, `TechWarehouseStorageAssignment.objects.filter`, `TechWarehouseStorageAssignment.objects.filter(location_id__in=location_ids, stock__warehouse=warehouse).values_list`, `WarehouseStorageLocation.objects.filter`, `locations.filter`, `locations.only`, `parse_storage_location_query`, `set`, `set(query.columns).issubset`.

### `autocomplete_storage_locations(*, warehouse, raw_query, include_cd=True, include_tech=True, limit=20)`

Исходник: `warehouse/storage_services.py:88`.

Подсказывает только реально используемые locations разрешённых типов текущего склада.

Статические вызовы: `Q`, `WarehouseStorageLocation.objects.filter`, `WarehouseStorageLocation.objects.filter(warehouse=warehouse).filter`, `WarehouseStorageLocation.objects.filter(warehouse=warehouse).filter(relation_filter).distinct`, `WarehouseStorageLocation.objects.filter(warehouse=warehouse).filter(relation_filter).distinct().order_by`, `list`, `location.canonical_value.startswith`, `matches`, `normalize_location_autocomplete_token`, `parse_storage_location_query`, `set`, `set(query.columns).issubset`.

### `_location_change(*, warehouse, old_value, new_value)`

Исходник: `warehouse/storage_services.py:120`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `field_change`.

### `update_storage_locations(*, actor, warehouse_id, product_type, product_id, raw_value, source=ProductChangeEvent.Source.CRM)`

Исходник: `warehouse/storage_services.py:130`.

Декораторы: `transaction.atomic`.

Заменяет весь упорядоченный список locations для одного WarehouseStock.

Статические вызовы: `', '.join`, `StorageLocationUpdateResult`, `ValidationError`, `Warehouse.objects.select_for_update`, `Warehouse.objects.select_for_update().get`, `WarehouseStorageLocation.objects.get_or_create`, `_location_change`, `assignment_configuration`, `assignment_model`, `assignment_model.objects.bulk_create`, `assignment_model.objects.filter`, `assignment_model.objects.filter(stock=stock).delete`, `assignment_model.objects.select_for_update`, `assignment_model.objects.select_for_update().select_related`, `assignment_model.objects.select_for_update().select_related('location').filter`, `assignment_model.objects.select_for_update().select_related('location').filter(stock=stock).order_by`, `enumerate`, `list`, `locations.append`, `logger.info`, `parse_storage_location_list`, `product_model.objects.active`, `product_model.objects.active().select_for_update`, `product_model.objects.active().select_for_update().get`, `record_product_changes`, `stock_model.objects.select_for_update`, `stock_model.objects.select_for_update().filter`, `stock_model.objects.select_for_update().filter(warehouse=warehouse, **{f'{product_field}_id': product.pk}).first`, `storage_locations_value`, `storage_stock_configuration`.

### `clear_storage_locations_if_zero(*, stock, actor, source=ProductChangeEvent.Source.CRM, action_kind='', action_object_id=None, action_label='')`

Исходник: `warehouse/storage_services.py:189`.

Удаляет assignments при нулевом остатке внутри транзакции исходной операции.

Статические вызовы: `_location_change`, `assignment_configuration`, `assignment_model.objects.filter`, `assignment_model.objects.filter(pk__in=[assignment.pk for assignment in assignments]).delete`, `assignment_model.objects.select_for_update`, `assignment_model.objects.select_for_update().select_related`, `assignment_model.objects.select_for_update().select_related('location').filter`, `assignment_model.objects.select_for_update().select_related('location').filter(stock=stock).order_by`, `getattr`, `hasattr`, `list`, `logger.info`, `record_product_changes`, `storage_locations_value`.

## `warehouse/urls.py`

Именованные HTTP-маршруты приложения складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `django.urls`.

## `warehouse/valuation.py`

Расчёт средней себестоимости только по физическому складскому остатку.

Импорты: `decimal`, `django.db.models`, `models`.

### `warehouse_owned_quantity(product_type, product_id)`

Исходник: `warehouse/valuation.py:12`.

Возвращает суммарный остаток товара на всех физических складах.

Статические вызовы: `Sum`, `ValueError`, `stock_model.objects.filter`, `stock_model.objects.filter(**{f'{product_field}_id': product_id}).aggregate`.

### `weighted_warehouse_cost(*, old_quantity, old_unit_cost, incoming_quantity, incoming_unit_cost)`

Исходник: `warehouse/valuation.py:25`.

Смешивает текущий физический остаток всех складов с приходом. Реализация/путь не входят в old_quantity; округление HALF_UP до копеек.

Статические вызовы: `(resulting_value / Decimal(resulting_quantity)).quantize`, `Decimal`, `ValueError`, `int`.

## `warehouse/views.py`

HTTP-обработчики: доступ, формы, вызов сервисов и ответ пользователю складов.

Различать физический остаток конкретного склада, реализацию и товар в пути.

Импорты: `catalog.models`, `catalog.product_filters`, `catalog.product_ordering`, `collections`, `consignment.models`, `core.decorators`, `django.contrib`, `django.core.exceptions`, `django.db.models`, `django.http`, `django.shortcuts`, `django.views.decorators.http`, `forms`, `models`, `services`, `storage_services`.

### `_totals(model, product_field)`

Исходник: `warehouse/views.py:42`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Sum`, `dict`, `model.objects.values_list`, `model.objects.values_list(f'{product_field}_id').annotate`.

### `_warehouse_stock_groups(warehouse, *, include_cd=True, include_tech=True, only_available=False, requested_quantities=None, filters=None, location_query='')`

Исходник: `warehouse/views.py:48`.

Группирует номенклатуру склада одинаково для остатков и перемещения.

Статические вызовы: `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').order_by`, `CD.objects.none`, `CDWarehouseStock.objects.filter`, `CDWarehouseStock.objects.filter(warehouse=warehouse).prefetch_related`, `CDWarehouseStorageAssignment.objects.select_related`, `CDWarehouseStorageAssignment.objects.select_related('location').order_by`, `Prefetch`, `ProductFilterState`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.active().select_related('brand', 'product_type').order_by`, `Tech.objects.none`, `TechWarehouseStock.objects.filter`, `TechWarehouseStock.objects.filter(warehouse=warehouse).prefetch_related`, `TechWarehouseStorageAssignment.objects.select_related`, `TechWarehouseStorageAssignment.objects.select_related('location').order_by`, `_totals`, `cd_consignment.get`, `cd_groups.items`, `cd_groups[product.platform].append`, `cd_locations.get`, `cd_products.filter`, `cd_quantities.get`, `cd_quantities.items`, `defaultdict`, `filter_product_querysets`, `list`, `products.filter`, `requested_quantities.get`, `sorted`, `storage_location_product_ids`, `storage_locations_for_stock`, `tech_consignment.get`, `tech_groups.items`, `tech_groups[product.product_type].append`, `tech_locations.get`, `tech_products.filter`, `tech_quantities.get`, `tech_quantities.items`.

### `global_stock_context(*, include_cd=True, include_tech=True, query='', filters=None)`

Исходник: `warehouse/views.py:130`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CD.objects.active`, `CD.objects.active().select_related`, `CD.objects.active().select_related('platform').order_by`, `CD.objects.none`, `CDWarehouseStock.objects.all`, `CDWarehouseTransferItem.objects.filter`, `CDWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses).values_list`, `CDWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses).values_list('cd_id').annotate`, `ProductFilterState`, `Sum`, `Tech.objects.active`, `Tech.objects.active().select_related`, `Tech.objects.active().select_related('brand', 'product_type').order_by`, `Tech.objects.none`, `TechWarehouseStock.objects.all`, `TechWarehouseTransferItem.objects.filter`, `TechWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses).values_list`, `TechWarehouseTransferItem.objects.filter(transfer__status__in=active_statuses).values_list('tech_id').annotate`, `Warehouse.objects.all`, `_totals`, `bool`, `cd_consignment.get`, `cd_groups.items`, `cd_groups[product.platform].append`, `cd_stocks.get`, `cd_transit.get`, `defaultdict`, `dict`, `filter_product_querysets`, `list`, `rows.append`, `sorted`, `sum`, `tech_brand_groups`, `tech_consignment.get`, `tech_groups.items`, `tech_groups.values`, `tech_groups[product.product_type].append`, `tech_stocks.get`, `tech_transit.get`.

### `global_stock(request)`

Исходник: `warehouse/views.py:219`.

Декораторы: `permission_required_any('warehouse.view_global_stock', 'catalog.view_cd', 'catalog.view_tech')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `context.update`, `global_stock_context`, `permission_required_any`, `product_filter_context`, `render`, `request.user.has_perm`.

### `warehouse_detail(request, pk)`

Исходник: `warehouse/views.py:238`.

Декораторы: `permission_required_any('warehouse.view_warehouse_stock', 'catalog.view_cd', 'catalog.view_tech')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `(request.GET.get('location') or '').strip`, `_warehouse_stock_groups`, `bool`, `context.update`, `get_object_or_404`, `permission_required_any`, `product_filter_context`, `render`, `request.GET.get`, `request.user.has_perm`, `tech_brand_groups`.

### `storage_location_autocomplete(request, pk)`

Исходник: `warehouse/views.py:288`.

Декораторы: `require_GET`; `permission_required_any('warehouse.view_warehouse_stock', 'catalog.view_cd', 'catalog.view_tech', 'catalog.view_nomenclature')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `JsonResponse`, `autocomplete_storage_locations`, `get_object_or_404`, `permission_required_any`, `request.GET.get`, `request.user.has_perm`.

### `storage_location_update(request, pk, product_type, product_id)`

Исходник: `warehouse/views.py:304`.

Декораторы: `require_POST`; `permission_required_any('warehouse.change_storage_location')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `JsonResponse`, `permission_required_any`, `request.POST.get`, `update_storage_locations`.

### `_parse_lines(post)`

Исходник: `warehouse/views.py:329`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `field_name.split`, `field_name.startswith`, `int`, `len`, `post.getlist`, `post.items`, `range`, `str`, `str(quantities[index]).strip`, `str(quantity).strip`, `table_lines.append`.

### `_requested_quantities(post)`

Исходник: `warehouse/views.py:365`.

Возвращает введённые количества для повторного показа формы с ошибкой.

Статические вызовы: `field_name.split`, `field_name.startswith`, `int`, `post.getlist`, `post.items`, `zip`.

### `transfer_list(request)`

Исходник: `warehouse/views.py:388`.

Декораторы: `permission_required_any('warehouse.view_transfers')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehouseTransfer.objects.select_related`, `WarehouseTransfer.objects.select_related('source_warehouse', 'destination_warehouse', 'created_by').prefetch_related`, `list`, `permission_required_any`, `render`, `request.user.has_perm`.

### `transfer_start(request)`

Исходник: `warehouse/views.py:407`.

Декораторы: `permission_required_any('warehouse.create_transfer')`.

Выбирает склад-отправитель перед открытием таблицы перемещения.

Статические вызовы: `WarehouseTransferSourceForm`, `form.is_valid`, `permission_required_any`, `redirect`, `render`.

### `_transfer_destination(request, transfer)`

Исходник: `warehouse/views.py:415`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `redirect`, `request.user.has_perm`.

### `transfer_detail(request, pk)`

Исходник: `warehouse/views.py:428`.

Декораторы: `permission_required_any('warehouse.view_transfers')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehouseTransfer.objects.select_related`, `WarehouseTransfer.objects.select_related('source_warehouse', 'destination_warehouse', 'created_by').prefetch_related`, `cd_groups.items`, `cd_groups[item.cd.platform].append`, `defaultdict`, `get_object_or_404`, `list`, `next_actions.get`, `permission_required_any`, `render`, `request.user.has_perm`, `sorted`, `tech_groups.items`, `tech_groups[item.tech.product_type].append`, `transfer.cd_items.all`, `transfer.tech_items.all`.

### `transfer_create(request, source_pk)`

Исходник: `warehouse/views.py:469`.

Декораторы: `permission_required_any('warehouse.create_transfer')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `WarehouseTransferForm`, `_parse_lines`, `_requested_quantities`, `_transfer_destination`, `_warehouse_stock_groups`, `create_transfer`, `form.add_error`, `form.is_valid`, `get_object_or_404`, `messages.success`, `permission_required_any`, `product_filter_context`, `render`, `request.user.has_perm`.

### `transfer_advance(request, pk)`

Исходник: `warehouse/views.py:512`.

Декораторы: `require_POST`; `permission_required_any('warehouse.mark_transfer_assembled', 'warehouse.mark_transfer_shipped', 'warehouse.mark_transfer_accepted')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `PermissionDenied`, `WarehouseTransfer.objects.filter`, `WarehouseTransfer.objects.filter(pk=pk).first`, `_transfer_destination`, `advance_transfer_status`, `isinstance`, `messages.error`, `messages.success`, `permission_by_status.get`, `permission_required_any`, `redirect`, `request.POST.get`, `request.user.has_perm`.

## `yandex_market/apps.py`

Конфигурация приложения и его регистрация в Django Яндекс Маркета FBS.

Удалённое состояние, локальная продажа и подтверждение сотрудника — разные уровни.

Импорты: `django.apps`.

### `YandexMarketConfig.ready(self)`

Исходник: `yandex_market/apps.py:12`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

## `yandex_market/client.py`

Официальный Partner API: точный JSON, таймаут, запрет редиректа ключа и журнал без PII.

Импорты: `core.external_policy`, `dataclasses`, `datetime`, `decimal`, `django.conf`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `integrations.crypto`, `models`, `pathlib`, `urllib.error`, `urllib.parse`, `urllib.request`.

### `api_key()`

Исходник: `yandex_market/client.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Path`, `decrypt_secret`, `path.exists`, `path.read_text`, `path.read_text('utf-8').strip`, `require_live_operation`, `value.strip`.

### `json_bytes(value)`

Исходник: `yandex_market/client.py:35`.

Decimal сериализуется числом JSON без промежуточного float.

Статические вызовы: `','.join`, `ValidationError`, `encode`, `encode(value).encode`, `isinstance`, `item.is_finite`, `item.items`, `json.dumps`, `str`.

### `safe_message(value, secret='')`

Исходник: `yandex_market/client.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `re.sub`, `str`, `value.replace`.

### `MarketError.__str__(self)`

Исходник: `yandex_market/client.py:66`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `NoRedirect.redirect_request(self, req, fp, code, msg, headers, newurl)`

Исходник: `yandex_market/client.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `YandexMarketClient.__init__(self, integration=None, *, key=None, job=None, actor=None, transport=None)`

Исходник: `yandex_market/client.py:76`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `NoRedirect`, `api_key`, `build_opener`, `require_live_operation`.

### `YandexMarketClient.reserve_budget(self, operation, contract, body)`

Исходник: `yandex_market/client.py:84`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(budget.window_start + timedelta(seconds=seconds) - now).total_seconds`, `ApiBudget.objects.filter`, `ApiBudget.objects.filter(pk=key).update`, `ApiBudget.objects.get_or_create`, `ApiBudget.objects.select_for_update`, `ApiBudget.objects.select_for_update().get`, `F`, `MarketError`, `budget.save`, `contract.get`, `int`, `isinstance`, `len`, `limits.get`, `max`, `path.startswith`, `path[4:].split`, `rule.get`, `timedelta`, `timezone.now`, `transaction.atomic`, `value.get`, `{'seconds': 1, 'minutes': 60, 'hours': 3600, 'days': 86400}.get`.

### `YandexMarketClient.call(self, operation, *, body=None, params=None, query=None, pdf=False, entity_id='')`

Исходник: `yandex_market/client.py:114`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `'; '.join`, `ApiLog.objects.create`, `MarketError`, `Request`, `RuntimeError`, `SyncJob.objects.filter`, `SyncJob.objects.filter(pk=self.job.pk, lease=self.job.lease).update`, `any`, `contract['path'].format`, `data.get`, `dict`, `e.get`, `errors.extend`, `getattr`, `hasattr`, `int`, `isinstance`, `json.loads`, `json_bytes`, `len`, `list`, `min`, `quote`, `raw.startswith`, `require_live_operation`, `response.headers.get`, `response.read`, `result.get`, `retry_after.isdigit`, `safe_message`, `self.reserve_budget`, `self.transport`, `str`, `time.monotonic`, `timezone.now`, `urlencode`, `values.items`, `values.setdefault`.

### `YandexMarketClient.pages(self, operation, *, body=None, key, params=None, limit=50)`

Исходник: `yandex_market/client.py:189`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketError`, `data.get`, `result.get`, `result.get('paging', {}).get`, `seen.add`, `self.call`, `set`.

### `YandexMarketClient.order(self, order_id)`

Исходник: `yandex_market/client.py:205`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(day + timedelta(days=2)).isoformat`, `(day - timedelta(days=1)).isoformat`, `MarketError`, `OrderMetadata.objects.filter`, `OrderMetadata.objects.filter(integration=self.integration, order_id=order_id).first`, `int`, `known.created_remote_at.date`, `order.get`, `self.pages`, `timedelta`.

## `yandex_market/content.py`

Контент отправляется только по изменённым полям, очистка всегда явная.

Импорты: `client`, `decimal`, `django.conf`, `django.core.exceptions`, `models`, `product_dimensions`, `urllib.parse`.

### `public_https(value)`

Исходник: `yandex_market/content.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `host.lower`, `host.lower().endswith`, `ipaddress.ip_address`, `urlparse`.

### `validate_schema(value, schema, path='Поле')`

Исходник: `yandex_market/content.py:38`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `int`, `isinstance`, `len`, `number.is_finite`, `schema.get`, `str`, `validate_schema`, `value.items`.

### `valid_gtin(value)`

Исходник: `yandex_market/content.py:80`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enumerate`, `int`, `len`, `reversed`, `sum`, `value.isascii`, `value.isdigit`.

### `api_numbers(value, schema)`

Исходник: `yandex_market/content.py:87`.

JSONField хранит Decimal строкой; по контракту API возвращаем числовой тип.

Статические вызовы: `Decimal`, `api_numbers`, `int`, `schema.get`, `schema.get('properties', {}).get`, `str`, `value.items`.

### `content_values_equal(key, left, right)`

Исходник: `yandex_market/content.py:101`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `api_numbers`.

### `validate_parameters(values, schema, *, require_all=True)`

Исходник: `yandex_market/content.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `constraints.get`, `definitions.get`, `definitions.items`, `grouped.get`, `grouped.setdefault`, `grouped.setdefault(parameter['id'], []).append`, `int`, `len`, `numeric_schema.update`, `parameter.get`, `parameter.get('unit', {}).get`, `schema.get`, `str`, `str(value.get('value', '')).lower`, `v.get`, `validate_schema`, `value.get`.

### `build_content(connection)`

Исходник: `yandex_market/content.py:154`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `CategorySchema.objects.filter`, `CategorySchema.objects.filter(category_id=connection.category_id).first`, `ValidationError`, `any`, `api_numbers`, `connection.media.filter`, `connection.media.filter(active=True).exists`, `connection_dimensions`, `dimensions_payload`, `payload.get`, `payload.pop`, `public_https`, `set`, `valid_gtin`, `validate_parameters`, `validate_schema`.

## `yandex_market/documents.py`

Официальные PDF Маркета и отдельные публичные изображения товаров.

Импорты: `PIL`, `client`, `content`, `core.external_policy`, `django.core.exceptions`, `django.core.files.base`, `django.db`, `django.db.models`, `io`, `models`, `queue`, `services`, `urllib.parse`, `urllib.request`.

### `label_cache_signature(order)`

Исходник: `yandex_market/documents.py:22`.

Коробки и состав определяют пригодность сохранённого ярлыка.

Статические вызовы: `hashlib.sha256`, `hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest`, `json.dumps`, `json.dumps(data, sort_keys=True, default=str).encode`.

### `request_labels(*, integration, orders, actor, format_name='A7', box_id=None, shipment_id=None, reuse=False)`

Исходник: `yandex_market/documents.py:30`.

Декораторы: `transaction.atomic`.

Официальный PDF получает worker; повторный запрос из продажи использует тот же документ.

Статические вызовы: `LabelDocument.objects.create`, `OrderMetadata.objects.select_for_update`, `OrderMetadata.objects.select_for_update().get`, `Q`, `ValidationError`, `actor.has_perm`, `any`, `audit`, `enqueue`, `int`, `label_cache_signature`, `len`, `order.labels.filter`, `order.labels.filter(format=format_name, cache_signature=values['cache_signature'], box_id=values.get('box_id'), shipment_id=values.get('shipment_id')).filter`, `order.labels.filter(format=format_name, cache_signature=values['cache_signature'], box_id=values.get('box_id'), shipment_id=values.get('shipment_id')).filter(Q(state__in=['pending', 'processing']) | Q(state='done') & ~Q(file='')).order_by`, `order.labels.filter(format=format_name, cache_signature=values['cache_signature'], box_id=values.get('box_id'), shipment_id=values.get('shipment_id')).filter(Q(state__in=['pending', 'processing']) | Q(state='done') & ~Q(file='')).order_by('-pk').first`, `str`, `str(box_id).isdecimal`, `str(shipment_id).isdecimal`, `values.get`, `values.update`.

### `download_public(url, *, pdf=False)`

Исходник: `yandex_market/documents.py:67`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `MarketError`, `NoRedirect`, `Request`, `ValidationError`, `any`, `build_opener`, `build_opener(NoRedirect()).open`, `data.startswith`, `host.endswith`, `ipaddress.ip_address`, `len`, `public_https`, `require_live_operation`, `response.read`, `socket.getaddrinfo`, `urlparse`.

### `save_image(connection, upload, *, position=None)`

Исходник: `yandex_market/documents.py:87`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `BytesIO`, `ContentFile`, `Image.open`, `Media`, `ValidationError`, `ValueError`, `connection.media.count`, `getattr`, `image.convert`, `image.convert('RGB').save`, `image.load`, `media.image.save`, `output.getvalue`.

### `process_label(document_id, client)`

Исходник: `yandex_market/documents.py:104`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ContentFile`, `LabelDocument.objects.select_related`, `LabelDocument.objects.select_related('order').get`, `MarketError`, `ValidationError`, `client.call`, `document.file.save`, `document.save`, `download_public`, `info.get`, `params.update`, `str`.

## `yandex_market/fbs_pricing.py`

Единый расчёт FBS: Decimal, объём упаковки и отдельная рекомендуемая цена.

Импорты: `catalog.audit`, `catalog.models`, `catalog.nomenclature_forms`, `catalog.product_fields`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `models`.

### `pricing_configuration(integration)`

Исходник: `yandex_market/fbs_pricing.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(integration.configuration or {}).get`, `copy.deepcopy`, `values.update`.

### `number(value, label, *, positive=False, percent=False)`

Исходник: `yandex_market/fbs_pricing.py:27`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `result.is_finite`, `result.quantize`, `str`.

### `middle_mile(volume, config)`

Исходник: `yandex_market/fbs_pricing.py:41`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `band.get`, `bands[-1].get`, `config.get`, `enumerate`, `first.to_integral_value`, `isinstance`, `len`, `max`, `min`, `min(fee, maximum).quantize`, `number`, `upper.to_integral_value`.

### `calculate_fbs_price(*, cost_price, desired_profit, length_cm, width_cm, height_cm, weight_g, placement_rate, configuration)`

Исходник: `yandex_market/fbs_pricing.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `_calculate`, `localcontext`.

### `_calculate(cost, profit, length, width, height, weight, placement, config)`

Исходник: `yandex_market/fbs_pricing.py:77`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `((branch_base - Decimal('0.02')) / divisor).to_integral_value`, `((profit - actual) / (100 * divisor)).to_integral_value`, `(price * rate).quantize`, `Decimal`, `ValidationError`, `any`, `branches.append`, `config.get`, `dict`, `expenses`, `fees.values`, `fixed.values`, `max`, `middle_mile`, `min`, `min(price * delivery_rate, delivery_max).quantize`, `number`, `numeric_weight.to_integral_value`, `range`, `raw_volume.to_integral_value`, `sum`, `threshold.to_integral_value`, `zip`.

### `product_context(product, integration=None, category=None)`

Исходник: `yandex_market/fbs_pricing.py:155`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CategorySchema.objects.filter`, `CategorySchema.objects.filter(category_id=category_id).first`, `Integration.objects.count`, `Integration.objects.first`, `ValidationError`, `connections.filter`, `connections.filter(integration=integration).first`, `len`, `list`, `product.yandex_connections.filter`, `product.yandex_connections.filter(active=True).select_related`.

### `product_calculation(product, *, integration=None, category=None, overrides=None, log_errors=True)`

Исходник: `yandex_market/fbs_pricing.py:181`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `calculate_fbs_price`, `copy.copy`, `getattr`, `isinstance`, `logger.warning`, `overrides.get`, `pricing_configuration`, `product_context`, `setattr`, `str`.

### `refresh_recommendation(product)`

Исходник: `yandex_market/fbs_pricing.py:208`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `product.save`, `product_calculation`, `result.get`.

### `refresh_recommendations(*, integration_id=None, category_id=None)`

Исходник: `yandex_market/fbs_pricing.py:217`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Q`, `model.objects.active`, `model.objects.active().filter`, `products.filter`, `products.filter(Q(yandex_pricing_category__category_id=category_id) | Q(yandex_connections__active=True, yandex_connections__category_id=category_id) | Q(yandex_connections__active=True, yandex_connections__category_id__isnull=True, yandex_connections__remote_offer__category_id=category_id)).distinct`, `products.select_related`, `products.select_related('yandex_pricing_integration', 'yandex_pricing_category').iterator`, `refresh_recommendation`.

### `save_product_inputs(*, actor, product, changes, version=None)`

Исходник: `yandex_market/fbs_pricing.py:232`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `actor.has_perm`, `changed_snapshots`, `changes.items`, `field_permissions_for`, `model_field.clean`, `product._meta.get_field`, `product.save`, `product_context`, `product_snapshot`, `product_version`, `record_product_changes`, `refresh_recommendation`, `setattr`, `transaction.atomic`, `type`, `type(product).objects.active`, `type(product).objects.active().select_for_update`, `type(product).objects.active().select_for_update().get`.

## `yandex_market/forms.py`

Серверная валидация пользовательского ввода и допустимого выбора Яндекс Маркета FBS.

Удалённое состояние, локальная продажа и подтверждение сотрудника — разные уровни.

Импорты: `content`, `decimal`, `django`, `django.core.exceptions`, `models`, `product_dimensions`, `warehouse.form_defaults`.

### `ObjectListWidget.__init__(self, schema)`

Исходник: `yandex_market/forms.py:32`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `super`, `super().__init__`.

### `ObjectListWidget.get_context(self, name, value, attrs)`

Исходник: `yandex_market/forms.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.schema.get`, `self.schema.get('properties', {}).items`, `spec.get`, `super`, `super().get_context`, `{'url': 'Ссылка HTTPS', 'title': 'Название', 'code': 'Код', 'type': 'Тип кода'}.get`.

### `IntegrationForm.clean(self)`

Исходник: `yandex_market/forms.py:50`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `any`, `char.isspace`, `data.get`, `data['new_api_key'].strip`, `getattr`, `self.add_error`, `self.instance.connections.exists`, `super`, `super().clean`.

### `ContentForm.__init__(self, *args, connection, **kwargs)`

Исходник: `yandex_market/forms.py:67`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'\n'.join`, `CONTENT_FIELDS.items`, `CategorySchema.objects.filter`, `CategorySchema.objects.filter(category_id=connection.category_id).first`, `connection.remote_offer.card.get`, `connection.remote_offer.snapshot.get`, `connection_dimensions`, `forms.CharField`, `forms.ChoiceField`, `forms.MultipleChoiceField`, `forms.TextInput`, `forms.Textarea`, `forms.TypedChoiceField`, `parameter.get`, `remote.get`, `remote.items`, `self._add_field`, `self.baseline.get`, `self.baseline.update`, `self.fields.values`, `self.parameter_schema.schema.get`, `str`, `super`, `super().__init__`, `v.get`, `values[0].get`.

### `ContentForm._add_field(self, path, schema, value)`

Исходник: `yandex_market/forms.py:112`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' · '.join`, `'\n'.join`, `'__'.join`, `(value or {}).get`, `Decimal`, `LABELS.get`, `ObjectListWidget`, `forms.CharField`, `forms.ChoiceField`, `forms.DecimalField`, `forms.IntegerField`, `forms.TextInput`, `forms.Textarea`, `getattr`, `json.dumps`, `len`, `schema.get`, `schema.get('items', {}).get`, `schema.get('properties', {}).items`, `self._add_field`, `str`, `str(value).lower`.

### `ContentForm.clean(self)`

Исходник: `yandex_market/forms.py:156`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `LABELS.get`, `ValidationError`, `bool`, `content.get`, `content.get('weightDimensions', {}).items`, `content.items`, `content.pop`, `custom.strip`, `data.get`, `int`, `isinstance`, `json.loads`, `len`, `line.strip`, `parameter.get`, `parameters.append`, `schema.get`, `schema.get('items', {}).get`, `self.add_error`, `self.parameter_schema.schema.get`, `self.paths.items`, `set`, `str`, `str(data.get(name + '_custom', '')).splitlines`, `str(value or '').splitlines`, `super`, `super().clean`, `target.setdefault`, `validate_parameters`, `validate_schema`, `value.splitlines`.

## `yandex_market/label_cache.py`

Предзагрузка ярлыков без печати; освобождение PDF после завершения заказа.

Импорты: `django.db`, `django.db.models.signals`, `django.dispatch`, `documents`, `models`, `sales.models`.

### `maintain_label_cache(order_id)`

Исходник: `yandex_market/label_cache.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OrderMetadata.objects.select_related`, `OrderMetadata.objects.select_related('integration__operator', 'sale').filter`, `OrderMetadata.objects.select_related('integration__operator', 'sale').filter(pk=order_id).first`, `document.file.delete`, `document.save`, `order.integration.operator.has_perm`, `order.labels.exclude`, `order.labels.exclude(cache_signature='').exclude`, `order.print_jobs.exclude`, `order.print_jobs.exclude(state__in=FINAL_PRINT_STATES).exists`, `request_labels`.

### `schedule_label_cache(order_id)`

Исходник: `yandex_market/label_cache.py:36`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `maintain_label_cache`, `transaction.on_commit`.

### `order_saved(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/label_cache.py:42`.

Декораторы: `receiver(post_save, sender=OrderMetadata, dispatch_uid='ym_order_label_cache')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `schedule_label_cache`.

### `sale_saved(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/label_cache.py:48`.

Декораторы: `receiver(post_save, sender=Sale, dispatch_uid='ym_sale_label_cleanup')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OrderMetadata.objects.filter`, `OrderMetadata.objects.filter(sale=instance).values_list`, `receiver`, `schedule_label_cache`.

### `print_saved(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/label_cache.py:55`.

Декораторы: `receiver(post_save, sender=MarketPrintJob, dispatch_uid='ym_print_label_cleanup')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `schedule_label_cache`.

## `yandex_market/management/commands/configure_yandex_market.py`

Первичная настройка отключённого подключения; только чтение внешнего API.

Импорты: `django.conf`, `django.contrib.auth`, `django.core.exceptions`, `django.core.management.base`, `integrations.crypto`, `pathlib`, `warehouse.models`, `yandex_market.client`, `yandex_market.models`, `yandex_market.services`.

### `Command.add_arguments(self, parser)`

Исходник: `yandex_market/management/commands/configure_yandex_market.py:21`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `parser.add_argument`.

### `Command.handle(self, *args, **options)`

Исходник: `yandex_market/management/commands/configure_yandex_market.py:31`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `CommandError`, `Integration.objects.get_or_create`, `Path`, `Path(temporary).exists`, `Path(temporary).unlink`, `Warehouse.objects.get`, `any`, `char.isspace`, `check_connection`, `encrypt_secret`, `get_user_model`, `get_user_model().objects.get`, `isinstance`, `os.chmod`, `os.fdopen`, `os.replace`, `refresh_catalog`, `self.stdout.write`, `self.style.SUCCESS`, `source.read_text`, `source.read_text('utf-8-sig').strip`, `str`, `stream.write`, `tempfile.mkstemp`.

## `yandex_market/models.py`

Данные Маркета отделены от номенклатуры, продаж и учётных остатков CRM.

Импорты: `decimal`, `django.conf`, `django.core.serializers.json`, `django.core.validators`, `django.db`, `django.db.models`, `django.utils`, `urllib.parse`.

### `json_field(**kwargs)`

Исходник: `yandex_market/models.py:14`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `models.JSONField`.

### `Integration.__str__(self)`

Исходник: `yandex_market/models.py:47`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `RemoteOffer.__str__(self)`

Исходник: `yandex_market/models.py:74`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `RemoteOffer.market_product_url(self)`

Исходник: `yandex_market/models.py:78`.

Декораторы: `property`.

Ссылка витрины из API с выбором кабинета продавца.

Статические вызовы: `isinstance`, `item.get`, `parse_qs`, `parse_qs(parts.query).get`, `parts.path.startswith`, `self.snapshot.get`, `str`, `urlsplit`.

### `RemoteOffer.hidden_in_store(self)`

Исходник: `yandex_market/models.py:97`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(self.snapshot.get('offer') or {}).get`, `any`, `isinstance`, `row.get`, `self.snapshot.get`, `str`.

### `OfferConnection.product(self)`

Исходник: `yandex_market/models.py:148`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `OfferConnection.product_kind(self)`

Исходник: `yandex_market/models.py:152`.

Декораторы: `property`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `CategorySchema.__str__(self)`

Исходник: `yandex_market/models.py:163`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `self.schema.get`.

## `yandex_market/orders.py`

Снимки внешнего заказа и штатные продажи; доставка, оплата и возврат независимы.

Импорты: `collections`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `django.utils.dateparse`, `models`, `packing`, `queue`, `sales.models`, `sales.notifications`, `sales.services`, `services`, `warehouse.receipts`.

### `aware_date(value)`

Исходник: `yandex_market/orders.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `parse_datetime`, `timezone.is_naive`.

### `item_amount(item)`

Исходник: `yandex_market/orders.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `ValidationError`, `amount.is_finite`, `amount.quantize`, `item.get`, `price.get`, `prices.get`, `str`.

### `available_actions(order)`

Исходник: `yandex_market/orders.py:64`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

### `action_payload(order, action)`

Исходник: `yandex_market/orders.py:72`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `available_actions`.

### `request_order_action(*, order_id, actor, action, boxes=None, expected_status=None)`

Исходник: `yandex_market/orders.py:83`.

Декораторы: `transaction.atomic`.

Ставит проверенное действие в существующую очередь, не меняя локальную доставку.

Статические вызовы: `OrderMetadata.objects.select_for_update`, `OrderMetadata.objects.select_for_update().select_related`, `OrderMetadata.objects.select_for_update().select_related('integration').get`, `ValidationError`, `action_payload`, `actor.has_perm`, `audit`, `enqueue`, `validate_boxes`.

### `import_order(integration, payload)`

Исходник: `yandex_market/orders.py:117`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `OrderMetadata.objects.filter`, `OrderMetadata.objects.filter(pk=order.pk).update`, `OrderMetadata.objects.get_or_create`, `ValidationError`, `_apply_order`, `int`, `payload.get`, `timezone.now`, `values.update`.

### `_apply_order(pk, payload)`

Исходник: `yandex_market/orders.py:135`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `Decimal`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('remote_offer', 'cd', 'tech').filter`, `OrderLine.objects.create`, `OrderMetadata.objects.filter`, `OrderMetadata.objects.filter(pk=pk).update`, `OrderMetadata.objects.select_for_update`, `OrderMetadata.objects.select_for_update().select_related`, `OrderMetadata.objects.select_for_update().select_related('integration', 'sale').get`, `STATUS_MAP.get`, `Sale.objects.get`, `ValidationError`, `advance_order_status`, `any`, `aware_date`, `bool`, `cancel_sale`, `connections.get`, `create_market_sale`, `delivery.get`, `isinstance`, `item.get`, `item_amount`, `len`, `lines.append`, `list`, `order.lines.select_related`, `order.save`, `payload.get`, `references.append`, `require_staff_acknowledgement`, `sequence.index`, `status.get`, `timezone.now`, `unit_price.quantize`.

### `save_return(order, payload)`

Исходник: `yandex_market/orders.py:236`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OrderMetadata.objects.filter`, `OrderMetadata.objects.filter(pk=order.pk).update`, `ReturnMetadata.objects.update_or_create`, `ValidationError`, `int`, `payload.get`.

### `accept_return(*, return_pk, warehouse_id, actor)`

Исходник: `yandex_market/orders.py:249`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AuditEvent.objects.create`, `ReturnMetadata.objects.filter`, `ReturnMetadata.objects.filter(pk=return_pk, accepted_at__isnull=True).update`, `ReturnMetadata.objects.select_related`, `ReturnMetadata.objects.select_related('order__sale', 'order__integration').get`, `ValidationError`, `by_offer.get`, `defaultdict`, `isinstance`, `item.get`, `line.save`, `lines.append`, `list`, `order.lines.select_for_update`, `order.lines.select_for_update().select_related`, `quantities.items`, `receive_return`, `record.save`, `record.snapshot.get`, `str`, `timezone.now`.

## `yandex_market/packing.py`

Состав и коробки заказа FBS; изменение упаковки влияет на актуальность официального ярлыка.

Импорты: `client`, `collections`, `content`, `django.core.exceptions`.

### `validate_boxes(order, boxes)`

Исходник: `yandex_market/packing.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `bool`, `defaultdict`, `dict`, `item.get`, `iter`, `len`, `list`, `next`, `partials.items`, `partials[item['id']].append`, `range`, `sorted`, `validate_schema`.

## `yandex_market/pricing_forms.py`

Параметры FBS и габариты без копирования веса или категорий Маркета.

Импорты: `catalog.nomenclature_forms`, `catalog.product_fields`, `decimal`, `django`, `django.core.exceptions`, `django.forms`, `fbs_pricing`, `models`.

### `FBSSettingsForm.__init__(self, *args, integration, **kwargs)`

Исходник: `yandex_market/pricing_forms.py:26`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `pricing_configuration`, `super`, `super().__init__`.

### `FBSSettingsForm.clean(self)`

Исходник: `yandex_market/pricing_forms.py:29`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `super`, `super().clean`, `values.get`.

### `clean_configuration(form, bands)`

Исходник: `yandex_market/pricing_forms.py:44`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `bands.is_valid`, `form.add_error`, `form.cleaned_data.items`, `form.is_valid`, `format`, `isinstance`, `middle_mile`, `row.get`, `str`.

### `FBSProductForm.__init__(self, *args, product, user, **kwargs)`

Исходник: `yandex_market/pricing_forms.py:79`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `bool`, `field_permissions_for`, `getattr`, `product_context`, `product_version`, `super`, `super().__init__`, `type`, `user.has_perm`.

### `FBSProductForm.clean(self)`

Исходник: `yandex_market/pricing_forms.py:96`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `', '.join`, `ValidationError`, `set`, `sorted`, `super`, `super().clean`.

### `category_rates_initial()`

Исходник: `yandex_market/pricing_forms.py:105`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CategorySchema.objects.order_by`, `CategorySchema.objects.order_by('name', 'category_id').values`, `list`.

## `yandex_market/pricing_signals.py`

Пересчёт рекомендации не изменяет опубликованную цену и не ставит API-задачи.

Импорты: `catalog.models`, `django.db.models.signals`, `django.dispatch`, `fbs_pricing`, `models`.

### `remember_inputs(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:14`.

Декораторы: `receiver(pre_save, sender=CD, dispatch_uid='fbs_cd_before')`; `receiver(pre_save, sender=Tech, dispatch_uid='fbs_tech_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values`, `sender.objects.filter(pk=instance.pk).values(*FIELDS).first`, `set`, `set(update_fields).intersection`.

### `inputs_changed(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:22`.

Декораторы: `receiver(post_save, sender=CD, dispatch_uid='fbs_cd_after')`; `receiver(post_save, sender=Tech, dispatch_uid='fbs_tech_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `getattr`, `instance._meta.get_field`, `receiver`, `refresh_recommendation`, `set`, `set(update_fields).intersection`.

### `remember_settings(sender, instance, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:32`.

Декораторы: `receiver(pre_save, sender=Integration, dispatch_uid='fbs_settings_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(previous or {}).get`, `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values_list`, `sender.objects.filter(pk=instance.pk).values_list('configuration', flat=True).first`.

### `settings_changed(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:38`.

Декораторы: `receiver(post_save, sender=Integration, dispatch_uid='fbs_settings_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(instance.configuration or {}).get`, `getattr`, `receiver`, `refresh_recommendations`.

### `remember_rate(sender, instance, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:44`.

Декораторы: `receiver(pre_save, sender=CategorySchema, dispatch_uid='fbs_category_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values_list`, `sender.objects.filter(pk=instance.pk).values_list('placement_rate', flat=True).first`.

### `rate_changed(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:49`.

Декораторы: `receiver(post_save, sender=CategorySchema, dispatch_uid='fbs_category_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `receiver`, `refresh_recommendations`.

### `connection_changed(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:55`.

Декораторы: `receiver(post_save, sender=OfferConnection, dispatch_uid='fbs_connection_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `refresh_recommendation`, `set`, `set(update_fields).intersection`.

### `remember_remote_category(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:64`.

Декораторы: `receiver(pre_save, sender=RemoteOffer, dispatch_uid='fbs_remote_category_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values_list`, `sender.objects.filter(pk=instance.pk).values_list('category_id', flat=True).first`.

### `remote_category_changed(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/pricing_signals.py:71`.

Декораторы: `receiver(post_save, sender=RemoteOffer, dispatch_uid='fbs_remote_category_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `getattr`, `instance.connections.filter`, `instance.connections.filter(active=True, category_id__isnull=True).select_related`, `receiver`, `refresh_recommendation`.

## `yandex_market/pricing_views.py`

Настройки тарифов FBS и заполнение только отсутствующих характеристик.

Импорты: `django.contrib`, `django.db`, `django.shortcuts`, `fbs_pricing`, `models`, `pricing_forms`, `product_dimensions`, `services`, `views`.

### `settings_view(request, pk)`

Исходник: `yandex_market/pricing_views.py:14`.

Декораторы: `access('manage_settings')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CategoryRateFormSet`, `CategorySchema.objects.get_or_create`, `FBSSettingsForm`, `Integration.objects.select_for_update`, `Integration.objects.select_for_update().get`, `MiddleMileFormSet`, `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(integration=integration, category_id__isnull=False).values`, `access`, `audit`, `category.full_clean`, `category.save`, `category_rates_initial`, `clean_configuration`, `fill_integration_dimensions`, `form.add_error`, `get_object_or_404`, `initial_rates.setdefault`, `initial_rates.values`, `len`, `list`, `locked.save`, `messages.success`, `pricing_configuration`, `rates.is_valid`, `redirect`, `render`, `request.POST.get`, `transaction.atomic`.

## `yandex_market/product_content.py`

Показ сохранённых данных Маркета в карточке товара без запросов к API.

Импорты: `content`, `django.urls`, `forms`, `models`.

### `_text(value)`

Исходник: `yandex_market/product_content.py:9`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `'\n'.join`, `LABELS.get`, `_text`, `isinstance`, `str`, `value.items`.

### `_fields(values, prefix=())`

Исходник: `yandex_market/product_content.py:19`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' · '.join`, `LABELS.get`, `_fields`, `_text`, `isinstance`, `values.items`.

### `saved_product_content(connection)`

Исходник: `yandex_market/product_content.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CategorySchema.objects.filter`, `CategorySchema.objects.filter(category_id=connection.category_id).first`, `_fields`, `_text`, `category.schema.get`, `choices.get`, `connection.media.all`, `content.get`, `content.items`, `content.update`, `definition.get`, `definition.get('unit', {}).get`, `definitions.get`, `fields.append`, `list`, `offer.get`, `offer.items`, `remote.card.get`, `remote.snapshot.get`, `reverse`, `row.get`.

## `yandex_market/product_dimensions.py`

Общие размеры товара. Маркет дополняет пустые поля, ручные значения сохраняет.

Импорты: `catalog.audit`, `catalog.models`, `content`, `decimal`, `django.core.exceptions`, `django.db`, `models`.

### `dimensions_payload(product, fallback=None, *, preserve_weight=False)`

Исходник: `yandex_market/product_dimensions.py:16`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `(fallback or {}).get`, `Decimal`, `Decimal(str(value)).is_finite`, `SIZE_KEYS.items`, `SIZE_KEYS.values`, `ValidationError`, `all`, `any`, `fallback.get`, `getattr`, `number.is_finite`, `str`, `values.values`.

### `connection_dimensions(connection)`

Исходник: `yandex_market/product_dimensions.py:40`.

Размеры из CRM; у существующего offer сохраняем его вес с упаковкой.

Статические вызовы: `any`, `connection.content.get`, `connection.remote_offer.snapshot.get`, `connection.remote_offer.snapshot.get('offer', {}).get`, `dimensions_payload`, `fallback.update`, `getattr`.

### `prepare_connection_dimensions(connection)`

Исходник: `yandex_market/product_dimensions.py:57`.

Подготовить локальную правку размеров без отправки в Маркет и записи в БД.

Статические вызовы: `connection.content.get`, `connection.remote_offer.snapshot.get`, `connection.remote_offer.snapshot.get('offer', {}).get`, `connection_dimensions`, `content_values_equal`, `set`, `sorted`.

### `save_dimensions(product, dimensions, *, actor, only_missing, source)`

Исходник: `yandex_market/product_dimensions.py:73`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `SIZE_KEYS.items`, `ValidationError`, `bool`, `changed_snapshots`, `dimensions.get`, `field_change`, `getattr`, `grams.to_integral_value`, `int`, `list`, `logger.info`, `logger.warning`, `product._meta.get_field`, `product._meta.get_field('weight_grams').clean`, `product._meta.get_field(field).clean`, `product.save`, `product_snapshot`, `record_product_changes`, `setattr`, `str`, `type`, `type(product).objects.active`, `type(product).objects.active().select_for_update`, `type(product).objects.active().select_for_update().get`, `updates.items`.

### `fill_remote_dimensions(remote, *, actor=None)`

Исходник: `yandex_market/product_dimensions.py:109`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `int`, `remote.connections.filter`, `remote.connections.filter(active=True).select_related`, `remote.snapshot.get`, `remote.snapshot.get('offer', {}).get`, `save_dimensions`.

### `fill_integration_dimensions(integration, *, actor)`

Исходник: `yandex_market/product_dimensions.py:121`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `connection.content.get`, `connection.remote_offer.snapshot.get`, `connection.remote_offer.snapshot.get('offer', {}).get`, `int`, `integration.connections.filter`, `integration.connections.filter(active=True).select_related`, `save_dimensions`.

## `yandex_market/queue.py`

Независимая DB-очередь с поколениями: изменения во время HTTP не теряются.

Импорты: `datetime`, `django.db`, `django.db.models`, `django.utils`, `models`.

### `enqueue(integration, kind, key, payload=None, *, actor=None, delay=0)`

Исходник: `yandex_market/queue.py:11`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `SyncJob.objects.filter`, `SyncJob.objects.filter(key=f'ym:{integration.pk}:{kind}:{key}').update`, `SyncJob.objects.filter(pk=job.pk).exclude`, `SyncJob.objects.filter(pk=job.pk).exclude(state='running').update`, `SyncJob.objects.filter(pk=job.pk).update`, `SyncJob.objects.get_or_create`, `job.payload.get`, `job.refresh_from_db`, `timedelta`, `timezone.now`, `transaction.atomic`.

### `enqueue_product(connection_id, *, delay=3, actor=None)`

Исходник: `yandex_market/queue.py:30`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=connection.pk).update`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('integration').filter`, `OfferConnection.objects.select_related('integration').filter(pk=connection_id, active=True, managed=True, integration__enabled=True).first`, `enqueue`.

### `product_after_commit(connection_id, *, delay=3, actor=None)`

Исходник: `yandex_market/queue.py:40`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `enqueue_product`, `transaction.on_commit`.

## `yandex_market/services.py`

Настройки, офферы и управляемые действия FBS с аудитом и существующей очередью.

Импорты: `catalog.models`, `client`, `content`, `core.external_policy`, `decimal`, `django.conf`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.db.models.functions`, `django.utils`, `integrations.crypto`, `models`, `pathlib`, `product_dimensions`, `queue`, `warehouse.inventory`.

### `audit(integration, actor, action, entity_id, **details)`

Исходник: `yandex_market/services.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `AuditEvent.objects.create`, `str`.

### `connections_with_stock(queryset)`

Исходник: `yandex_market/services.py:24`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Coalesce`, `Sum`, `Value`, `queryset.annotate`.

### `refresh_trade_snapshots(integration, *, client, offer_ids=None)`

Исходник: `yandex_market/services.py:28`.

Только чтение цены и доступного остатка; значения CRM не изменяются.

Статические вызовы: `'; '.join`, `MarketError`, `any`, `errors.append`, `len`, `max`, `refresh`, `str`.

### `_refresh_price_snapshots(integration, *, client, offer_ids=None)`

Исходник: `yandex_market/services.py:43`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(integration=integration, offer_id=row['offerId']).update`, `client.call`, `client.call(operation, body=body).get`, `client.call(operation, body=body).get('result', {}).get`, `client.pages`, `row.get`, `row.get('price', {}).get`, `str`, `timezone.now`.

### `_refresh_stock_snapshots(integration, *, client, offer_ids=None)`

Исходник: `yandex_market/services.py:53`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(integration=integration, offer_id=row['offerId']).update`, `client.call`, `client.call('getStocks', body=body).get`, `client.call('getStocks', body=body).get('result', {}).get`, `client.call('getStocksOnPartnerWarehouses', body=body).get`, `client.call('getStocksOnPartnerWarehouses', body=body).get('result', {}).get`, `client.pages`, `max`, `row.get`, `stocks.get`, `timezone.now`.

### `check_connection(integration, *, client=None)`

Исходник: `yandex_market/services.py:71`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `YandexMarketClient`, `any`, `c.get`, `campaign.get`, `campaign.get('business', {}).get`, `client.call`, `client.call('getBusinessSettings', body={}).get`, `client.call('getBusinessSettings', body={}).get('result', {}).get`, `client.pages`, `configuration.get`, `integration.save`, `list`, `m.get`, `next`, `target.get`, `timezone.now`, `w.get`.

### `store_api_key(value)`

Исходник: `yandex_market/services.py:100`.

Файл содержит только шифротекст; смена ключа требует повторной проверки кабинетов.

Статические вызовы: `Integration.objects.all`, `Integration.objects.all().update`, `Path`, `Path(temporary).exists`, `Path(temporary).unlink`, `ValidationError`, `any`, `char.isspace`, `encrypt_secret`, `os.chmod`, `os.fdopen`, `os.replace`, `require_live_operation`, `str`, `str(value).strip`, `stream.write`, `tempfile.mkstemp`.

### `store_offer(integration, row, card=None)`

Исходник: `yandex_market/services.py:128`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `Integration.objects.filter`, `Integration.objects.filter(pk=integration.pk).update`, `RemoteOffer.objects.update_or_create`, `bool`, `card.get`, `fill_remote_dimensions`, `mapping.get`, `offer.get`, `row.get`, `timezone.now`, `values.update`.

### `refresh_catalog(integration, *, client=None, include_trade=True)`

Исходник: `yandex_market/services.py:146`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(integration=integration, offer_id=card['offerId']).update`, `YandexMarketClient`, `card.get`, `client.pages`, `refresh_trade_snapshots`, `store_offer`.

### `refresh_offer(remote, *, client=None)`

Исходник: `yandex_market/services.py:161`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `YandexMarketClient`, `c.get`, `client.call`, `client.call('getOfferCardsContentStatus', body={'offerIds': [remote.offer_id], 'withRecommendations': True}).get`, `client.call('getOfferCardsContentStatus', body={'offerIds': [remote.offer_id], 'withRecommendations': True}).get('result', {}).get`, `data.get`, `data.get('result', {}).get`, `next`, `r.get`, `r.get('offer', {}).get`, `refresh_trade_snapshots`, `result.refresh_from_db`, `store_offer`.

### `refresh_category(category_id, *, client)`

Исходник: `yandex_market/services.py:176`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `CategorySchema.objects.filter`, `CategorySchema.objects.filter(category_id=category_id).update`, `CategorySchema.objects.update_or_create`, `F`, `ValidationError`, `client.call`, `data.get`, `int`, `result.get`, `timezone.now`, `transaction.atomic`.

### `bind_offer(*, remote_id, product_kind, product_id, actor)`

Исходник: `yandex_market/services.py:188`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OfferConnection.objects.create`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(integration=remote.integration, active=True, **{product_kind: product}).exists`, `OfferConnection.objects.filter(remote_offer=remote).exists`, `OfferConnection.objects.filter(remote_offer=remote, active=True).exists`, `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(pk=remote_id).update`, `RemoteOffer.objects.select_for_update`, `RemoteOffer.objects.select_for_update().select_related`, `RemoteOffer.objects.select_for_update().select_related('integration').get`, `ValidationError`, `actor.has_perm`, `audit`, `connection.save`, `model.objects.active`, `model.objects.active().get`, `prepare_connection_dimensions`, `product_after_commit`, `{'cd': CD, 'tech': Tech}.get`.

### `ensure_unlink_allowed(connection)`

Исходник: `yandex_market/services.py:224`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReturnMetadata.objects.filter`, `ReturnMetadata.objects.filter(order__lines__connection=connection, accepted_at__isnull=True).exclude`, `ReturnMetadata.objects.filter(order__lines__connection=connection, accepted_at__isnull=True).exclude(status='CANCELLED').exists`, `SyncJob.objects.filter`, `SyncJob.objects.filter(integration=connection.integration, kind='product', payload__connection_id=connection.pk, state__in=['pending', 'running']).exists`, `SyncJob.objects.filter(integration=connection.integration, kind='reconcile', state='running').exists`, `ValidationError`, `connection.order_lines.filter`, `connection.order_lines.filter(order__sale__cancelled_at__isnull=True).exclude`, `connection.order_lines.filter(order__sale__cancelled_at__isnull=True).exclude(order__status__in=['CANCELLED', 'DELIVERED']).exists`, `job.payload.get`.

### `unlink_offer(connection_id, actor, *, replacement=None)`

Исходник: `yandex_market/services.py:239`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=connection_id).update`, `OfferConnection.objects.select_for_update`, `OfferConnection.objects.select_for_update().select_related`, `OfferConnection.objects.select_for_update().select_related('integration', 'remote_offer').get`, `audit`, `bind_offer`, `connection.save`, `ensure_unlink_allowed`.

### `create_offer(*, integration, product_kind, product_id, actor)`

Исходник: `yandex_market/services.py:254`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `Integration.objects.filter`, `Integration.objects.filter(pk=integration.pk).update`, `RemoteOffer.objects.create`, `RemoteOffer.objects.filter`, `RemoteOffer.objects.filter(integration=integration, offer_id=offer_id).exists`, `ValidationError`, `bind_offer`, `connection.save`, `content.items`, `model.objects.active`, `model.objects.active().get`, `prepare_connection_dimensions`, `product.barcodes.values_list`, `product_kind.upper`, `valid_gtin`, `{'cd': CD, 'tech': Tech}.get`.

### `activate(connection_id, actor, *, sell)`

Исходник: `yandex_market/services.py:280`.

Декораторы: `transaction.atomic`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=connection_id).update`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('remote_offer', 'cd', 'tech', 'integration').get`, `ValidationError`, `audit`, `build_content`, `connection.save`, `prepare_connection_dimensions`, `product_after_commit`.

### `set_offer_hidden(connection_id, actor, *, hidden, client=None)`

Исходник: `yandex_market/services.py:301`.

Меняет видимость предложения, сохраняя связь, цену и складской остаток.

Статические вызовы: `MarketError`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('integration', 'remote_offer').get`, `ValidationError`, `YandexMarketClient`, `actor.has_perm`, `audit`, `client.call`, `refresh_offer`, `response.get`.

### `resume_display_after_sync(connection, *, client, price, quantity)`

Исходник: `yandex_market/services.py:320`.

Снимаем скрытие один раз, после передачи цены и остатка из CRM.

Статические вызовы: `AuditEvent.objects.filter`, `AuditEvent.objects.filter(integration=connection.integration, entity_id=str(connection.pk), action='resume_display_requested').select_related`, `AuditEvent.objects.filter(integration=connection.integration, entity_id=str(connection.pk), action='resume_display_requested').select_related('actor').order_by`, `AuditEvent.objects.filter(integration=connection.integration, entity_id=str(connection.pk), action='resume_display_requested').select_related('actor').order_by('-pk').first`, `MarketError`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=connection.pk, revision=connection.revision, resume_display_pending=True).update`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('integration', 'cd', 'tech').filter`, `OfferConnection.objects.select_related('integration', 'cd', 'tech').filter(pk=connection.pk, revision=connection.revision, active=True, managed=True, sell_on_yandex=True, resume_display_pending=True, integration__enabled=True, integration__checked_at__isnull=False).first`, `audit`, `bool`, `client.call`, `global_stock`, `response.get`, `str`, `transaction.atomic`.

### `sync_product(connection_id, *, client=None, force=False)`

Исходник: `yandex_market/services.py:346`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Decimal`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=connection.pk).update`, `OfferConnection.objects.filter(pk=connection.pk, revision=connection.revision).update`, `OfferConnection.objects.filter(pk=connection.pk, revision=revision).update`, `OfferConnection.objects.select_related`, `OfferConnection.objects.select_related('integration', 'remote_offer', 'cd', 'tech').prefetch_related`, `OfferConnection.objects.select_related('integration', 'remote_offer', 'cd', 'tech').prefetch_related('media').get`, `ValidationError`, `YandexMarketClient`, `build_content`, `client.call`, `dict`, `global_stock`, `hashlib.sha256`, `hashlib.sha256(json_bytes({'content': content, 'price': price, 'quantity': quantity})).hexdigest`, `json_bytes`, `len`, `prepare_connection_dimensions`, `resume_display_after_sync`, `sent.get`, `str`, `timezone.now`, `timezone.now().isoformat`.

### `sync_price_stock_batch(integration, connection_ids, *, client, sync_prices=True, sync_stocks=True)`

Исходник: `yandex_market/services.py:405`.

Сверка отправляет пачки до 100 товаров; перед отправкой заново читает CRM.

Статические вызовы: `Coalesce`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=row.pk).update`, `OfferConnection.objects.filter(pk=row.pk, revision=row.revision).update`, `OfferConnection.objects.filter(pk__in=connection_ids[offset:offset + 100], integration=integration, active=True, managed=True).select_related`, `OfferConnection.objects.filter(pk__in=connection_ids[offset:offset + 100], integration=integration, active=True, managed=True).select_related('remote_offer', 'cd', 'tech').annotate`, `Sum`, `Value`, `client.call`, `dict`, `enqueue`, `len`, `list`, `prepare_connection_dimensions`, `prices.append`, `processed.append`, `range`, `stocks.append`, `str`, `timezone.now`, `timezone.now().isoformat`, `values.update`.

## `yandex_market/signals.py`

Реакции на сохранение моделей и запуск связанных действий Яндекс Маркета FBS.

Удалённое состояние, локальная продажа и подтверждение сотрудника — разные уровни.

Импорты: `catalog.models`, `django.db.models`, `django.db.models.signals`, `django.dispatch`, `models`, `product_dimensions`, `queue`, `warehouse.models`.

### `remember_product(sender, instance, **kwargs)`

Исходник: `yandex_market/signals.py:20`.

Декораторы: `receiver(pre_save, sender=CD, dispatch_uid='ym_cd_before')`; `receiver(pre_save, sender=Tech, dispatch_uid='ym_tech_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values`, `sender.objects.filter(pk=instance.pk).values(*PRODUCT_FIELDS).first`.

### `remember_quantity(sender, instance, **kwargs)`

Исходник: `yandex_market/signals.py:26`.

Декораторы: `receiver(pre_save, sender=CDWarehouseStock, dispatch_uid='ym_cd_stock_before')`; `receiver(pre_save, sender=TechWarehouseStock, dispatch_uid='ym_tech_stock_before')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `receiver`, `sender.objects.filter`, `sender.objects.filter(pk=instance.pk).values_list`, `sender.objects.filter(pk=instance.pk).values_list('quantity', flat=True).first`.

### `stock_changed(sender, instance, raw=False, **kwargs)`

Исходник: `yandex_market/signals.py:32`.

Декораторы: `receiver(post_save, sender=CDWarehouseStock, dispatch_uid='ym_cd_stock_after')`; `receiver(post_save, sender=TechWarehouseStock, dispatch_uid='ym_tech_stock_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OfferConnection.objects.filter`, `OfferConnection.objects.filter(active=True, managed=True, **{f'{kind}_id': getattr(instance, f'{kind}_id')}).values_list`, `getattr`, `product_after_commit`, `receiver`.

### `product_changed(sender, instance, raw=False, update_fields=None, **kwargs)`

Исходник: `yandex_market/signals.py:42`.

Декораторы: `receiver(post_save, sender=CD, dispatch_uid='ym_cd_after')`; `receiver(post_save, sender=Tech, dispatch_uid='ym_tech_after')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(active=True, managed=True, **{kind: instance}).select_related`, `OfferConnection.objects.filter(pk=connection.pk).update`, `changed.intersection`, `dict`, `dirty.add`, `getattr`, `prepare_connection_dimensions`, `product_after_commit`, `receiver`, `set`, `set(update_fields).intersection`, `setattr`, `sorted`.

## `yandex_market/tasks.py`

Короткий захват задачи; HTTP всегда выполняется за пределами транзакции.

Импорты: `client`, `datetime`, `decimal`, `django.core.exceptions`, `django.db`, `django.db.models`, `django.utils`, `documents`, `models`, `orders`, `packing`, `queue`, `services`, `warehouse.inventory`.

### `reconcile_orders(integration, client)`

Исходник: `yandex_market/tasks.py:22`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `client.order`, `client.pages`, `import_order`, `integration.orders.exclude`, `integration.orders.exclude(status__in=['CANCELLED', 'DELIVERED', 'RETURNED', 'PARTIALLY_RETURNED']).exclude`, `integration.orders.exclude(status__in=['CANCELLED', 'DELIVERED', 'RETURNED', 'PARTIALLY_RETURNED']).exclude(status='', sale__isnull=True).iterator`, `order.save`, `str`, `timezone.now`.

### `reconcile_returns(integration, client)`

Исходник: `yandex_market/tasks.py:46`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OrderMetadata.objects.get_or_create`, `client.pages`, `save_return`.

### `reconcile(integration, client)`

Исходник: `yandex_market/tasks.py:52`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `'; '.join`, `MarketError`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(integration=integration, active=True, managed=True).select_related`, `any`, `bool`, `connections_with_stock`, `enqueue`, `errors.append`, `integration.save`, `isinstance`, `len`, `max`, `mismatches.items`, `mismatches.setdefault`, `mismatches.setdefault((prices_checked, stocks_checked), []).append`, `reconcile_orders`, `reconcile_returns`, `refresh_catalog`, `refresh_trade_snapshots`, `stage`, `timezone.now`, `unread.append`.

### `process(job)`

Исходник: `yandex_market/tasks.py:98`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `ValidationError`, `WebhookEvent.objects.filter`, `WebhookEvent.objects.filter(pk=event.pk).update`, `WebhookEvent.objects.get`, `YandexMarketClient`, `action_payload`, `client.call`, `client.call('getOrderLabelsData', params={'orderId': order_id}, entity_id=order_id).get`, `client.order`, `event.save`, `import_order`, `labels.get`, `order.save`, `payload.get`, `process_label`, `reconcile`, `refresh_catalog`, `response.get`, `response.get('result', response).get`, `save_return`, `sync_price_stock_batch`, `sync_product`, `timezone.now`, `validate_boxes`.

### `ensure_periodic_jobs()`

Исходник: `yandex_market/tasks.py:150`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Integration.objects.filter`, `SyncJob.objects.filter`, `SyncJob.objects.filter(key=f'ym:{integration.pk}:event:{event_id}').exists`, `SyncJob.objects.filter(key=f'ym:{integration.pk}:periodic', state='error', run_after__lte=now).update`, `SyncJob.objects.filter(state='running', updated_at__lt=now - timedelta(minutes=20)).update`, `SyncJob.objects.get_or_create`, `WebhookEvent.objects.filter`, `WebhookEvent.objects.filter(integration=integration, state='pending').values_list`, `enqueue`, `timedelta`, `timezone.now`.

### `claim_job()`

Исходник: `yandex_market/tasks.py:165`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Case`, `F`, `IntegerField`, `SyncJob.objects.filter`, `SyncJob.objects.filter(pk=candidate.pk, state='pending', generation=candidate.generation).update`, `SyncJob.objects.filter(state='pending', run_after__lte=timezone.now()).annotate`, `SyncJob.objects.filter(state='pending', run_after__lte=timezone.now()).annotate(priority=Case(When(kind__in=['event', 'order', 'order_action'], then=Value(0)), When(kind='reconcile', then=Value(2)), default=Value(1), output_field=IntegerField())).order_by`, `SyncJob.objects.select_related`, `SyncJob.objects.select_related('integration', 'actor').get`, `Value`, `When`, `candidates.first`, `timezone.now`, `uuid.uuid4`.

### `process_one_job()`

Исходник: `yandex_market/tasks.py:179`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `F`, `Integration.objects.filter`, `Integration.objects.filter(pk=job.integration_id).update`, `LabelDocument.objects.filter`, `LabelDocument.objects.filter(pk=job.payload.get('document_id')).update`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=job.payload.get('connection_id')).update`, `OfferConnection.objects.filter(pk__in=job.payload.get('connection_ids', []), integration=job.integration).update`, `SyncJob.objects.filter`, `ValidationError`, `WebhookEvent.objects.filter`, `WebhookEvent.objects.filter(pk=job.payload.get('event_id')).update`, `claim_job`, `ensure_periodic_jobs`, `job.key.endswith`, `job.payload.get`, `len`, `min`, `process`, `selector.first`, `selector.update`, `str`, `timedelta`, `timezone.now`, `type`.

## `yandex_market/urls.py`

Именованные HTTP-маршруты приложения Яндекс Маркета FBS.

Удалённое состояние, локальная продажа и подтверждение сотрудника — разные уровни.

Импорты: `django.urls`.

## `yandex_market/views.py`

Интерфейс Маркета: каждое изменение проверяет право и подтверждение на сервере.

Импорты: `catalog.models`, `catalog.product_search`, `client`, `content`, `django.conf`, `django.contrib`, `django.contrib.auth.decorators`, `django.core`, `django.core.exceptions`, `django.core.paginator`, `django.db`, `django.db.models`, `django.http`, `django.shortcuts`, `django.urls`, `django.utils`, `django.views.decorators.debug`, `django.views.decorators.http`, `documents`, `forms`, `functools`, `models`, `orders`, `product_dimensions`, `queue`, `services`, `warehouse.inventory`, `warehouse.models`.

### `access(permission='view_integration', *, post=False)`

Исходник: `yandex_market/views.py:34`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `' '.join`, `isinstance`, `login_required`, `messages.error`, `permission_required`, `permission_required(f'yandex_market.{permission}', raise_exception=True)`, `redirect`, `render`, `require_POST`, `str`, `view`, `wraps`.

### `confirmed(request)`

Исходник: `yandex_market/views.py:51`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `request.POST.get`.

### `connection_query()`

Исходник: `yandex_market/views.py:56`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OfferConnection.objects.select_related`.

### `selected_integration(request)`

Исходник: `yandex_market/views.py:60`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Integration.objects.order_by`, `Integration.objects.order_by('pk').first`, `get_object_or_404`, `key.isdecimal`, `request.GET.get`, `request.POST.get`.

### `dashboard(request)`

Исходник: `yandex_market/views.py:66`.

Декораторы: `access()`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ApiLog.objects.filter`, `CD.objects.active`, `Integration.objects.all`, `Paginator`, `Paginator(rows, 40).get_page`, `Prefetch`, `Q`, `ReturnMetadata.objects.filter`, `ReturnMetadata.objects.filter(order__integration=integration).select_related`, `ReturnMetadata.objects.filter(order__integration=integration).select_related('order', 'warehouse').order_by`, `Tech.objects.active`, `access`, `any`, `connection_query`, `connection_query().filter`, `connections_with_stock`, `connections_with_stock(connection_query().filter(integration=integration, active=True)).order_by`, `filter_products_by_text`, `filter_products_by_text(CD.objects.active(), query, product_kind='cd').values`, `filter_products_by_text(Tech.objects.active(), query, product_kind='tech').values`, `integration.connections.filter`, `integration.connections.filter(active=True).count`, `integration.jobs.exclude`, `integration.jobs.exclude(last_error='').order_by`, `integration.jobs.filter`, `integration.jobs.filter(state='error').count`, `integration.offers.count`, `integration.offers.select_related`, `integration.orders.count`, `integration.orders.select_related`, `integration.orders.select_related('sale').all`, `mismatches.append`, `query.casefold`, `render`, `request.GET.get`, `request.GET.get('q', '').strip`, `rows.exclude`, `rows.filter`, `rows.prefetch_related`, `rows.values_list`, `rows.values_list('pk', 'name', 'offer_id', 'market_sku').iterator`, `selected_integration`, `str`, `str(value or '').casefold`.

### `settings_view(request, pk=None)`

Исходник: `yandex_market/views.py:131`.

Декораторы: `access('manage_settings')`; `sensitive_post_parameters('new_api_key')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `IntegrationForm`, `access`, `any`, `api_key`, `audit`, `bool`, `form.cleaned_data.get`, `form.is_valid`, `form.save`, `get_object_or_404`, `instance.save`, `messages.success`, `redirect`, `render`, `sensitive_post_parameters`, `store_api_key`, `transaction.atomic`.

### `categories(request, pk)`

Исходник: `yandex_market/views.py:151`.

Декораторы: `access('edit_content')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `Paginator`, `Paginator(rows, 50).get_page`, `YandexMarketClient`, `YandexMarketClient(integration, actor=request.user).call`, `YandexMarketClient(integration, actor=request.user).call('getCategoriesTree', body={}).get`, `access`, `connection_query`, `flatten`, `get_object_or_404`, `integration.configuration.get`, `integration.save`, `name.casefold`, `node.get`, `redirect`, `render`, `request.GET.get`, `request.GET.get('q', '').strip`, `request.GET.get('q', '').strip().casefold`, `rows.append`, `str`.

### `check(request, pk)`

Исходник: `yandex_market/views.py:174`.

Декораторы: `access('manage_settings', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `YandexMarketClient`, `access`, `audit`, `check_connection`, `get_object_or_404`, `messages.success`, `redirect`.

### `synchronize(request, pk)`

Исходник: `yandex_market/views.py:183`.

Декораторы: `access('retry_sync', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `access`, `confirmed`, `enqueue`, `get_object_or_404`, `messages.success`, `redirect`, `request.POST.get`, `reverse`.

### `bind(request, pk)`

Исходник: `yandex_market/views.py:196`.

Декораторы: `access('bind_offer')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OfferConnection.objects.filter`, `OfferConnection.objects.filter(remote_offer=remote).exists`, `RemoteOffer.objects.select_related`, `ValidationError`, `YandexMarketClient`, `access`, `bind_offer`, `confirmed`, `connection_query`, `connection_query().filter`, `connection_query().filter(remote_offer=remote, active=True).first`, `filter_products_by_text`, `get_object_or_404`, `global_stock`, `messages.success`, `messages.warning`, `model.objects.active`, `product_id.isdecimal`, `products.extend`, `redirect`, `refresh_category`, `refresh_offer`, `render`, `request.GET.get`, `request.GET.get('q', '').strip`, `request.POST.get`, `request.user.has_perm`, `signing.dumps`, `signing.loads`, `unlink_offer`, `{'cd': CD, 'tech': Tech}[kind].objects.active`.

### `new_offer(request)`

Исходник: `yandex_market/views.py:240`.

Декораторы: `access('bind_offer', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `YandexMarketClient`, `YandexMarketClient(integration, actor=request.user).call`, `YandexMarketClient(integration, actor=request.user).call('getOfferMappings', body={'offerIds': [offer_id]}).get`, `YandexMarketClient(integration, actor=request.user).call('getOfferMappings', body={'offerIds': [offer_id]}).get('result', {}).get`, `access`, `confirmed`, `create_offer`, `get_object_or_404`, `kind.upper`, `messages.info`, `redirect`, `request.POST.get`, `request.user.has_perm`, `row.get`, `row.get('offer', {}).get`, `store_offer`, `{'cd': CD, 'tech': Tech}[kind].objects.active`.

### `connection_detail(request, pk)`

Исходник: `yandex_market/views.py:261`.

Декораторы: `access()`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ContentForm`, `DELETE_FIELDS.items`, `F`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=pk).update`, `OfferConnection.objects.filter(pk=pk, revision=form.cleaned_data['revision']).update`, `ValidationError`, `access`, `audit`, `connection.integration.auditevent_set.filter`, `connection.integration.auditevent_set.filter(entity_id=str(pk)).select_related`, `connection.integration.auditevent_set.filter(entity_id=str(pk)).select_related('actor').order_by`, `connection.media.filter`, `connection_query`, `content_values_equal`, `dict`, `dirty.add`, `form.baseline.get`, `form.cleaned_data['content'].get`, `form.cleaned_data['content'].items`, `form.is_valid`, `get_object_or_404`, `global_stock`, `messages.success`, `product_after_commit`, `redirect`, `render`, `request.user.has_perm`, `save_dimensions`, `set`, `sorted`, `str`, `transaction.atomic`.

### `content_action(request, pk)`

Исходник: `yandex_market/views.py:300`.

Декораторы: `access('edit_content', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `OfferConnection.objects.filter`, `OfferConnection.objects.filter(pk=pk).update`, `ValidationError`, `YandexMarketClient`, `access`, `activate`, `audit`, `category_id.isdecimal`, `confirmed`, `connection.content.pop`, `connection.media.filter`, `connection.media.filter(active=True).count`, `connection.media.filter(active=True).update`, `connection.media.filter(active=True).values_list`, `connection.media.filter(pk=media_id).update`, `connection.save`, `connection_query`, `connection_query().get`, `dirty.add`, `dirty.discard`, `dirty.update`, `enumerate`, `get_object_or_404`, `int`, `len`, `media.save`, `product_after_commit`, `redirect`, `refresh_category`, `refresh_offer`, `request.FILES.getlist`, `request.POST.get`, `request.POST.getlist`, `request.user.has_perm`, `save_image`, `set`, `set_offer_hidden`, `sorted`, `str`, `transaction.atomic`.

### `unlink(request, pk)`

Исходник: `yandex_market/views.py:381`.

Декораторы: `access('rebind_offer', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `access`, `confirmed`, `messages.success`, `redirect`, `unlink_offer`.

### `order_detail(request, pk)`

Исходник: `yandex_market/views.py:389`.

Декораторы: `access()`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OrderMetadata.objects.select_related`, `Warehouse.objects.all`, `access`, `available_actions`, `get_object_or_404`, `order.labels.order_by`, `order.returns.all`, `render`.

### `order_action(request, pk)`

Исходник: `yandex_market/views.py:396`.

Декораторы: `access('manage_orders', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `OrderMetadata.objects.select_related`, `ValidationError`, `access`, `confirmed`, `get_object_or_404`, `json.loads`, `messages.success`, `redirect`, `request.POST.get`, `request_order_action`.

### `return_accept(request, pk)`

Исходник: `yandex_market/views.py:412`.

Декораторы: `access('accept_return', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ReturnMetadata.objects.select_related`, `accept_return`, `access`, `confirmed`, `get_object_or_404`, `messages.success`, `redirect`, `request.POST.get`.

### `label_request(request)`

Исходник: `yandex_market/views.py:422`.

Декораторы: `access('print_labels', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `ValidationError`, `access`, `confirmed`, `get_object_or_404`, `i.isdecimal`, `int`, `integration.orders.filter`, `len`, `list`, `redirect`, `request.POST.get`, `request.POST.getlist`, `request_labels`, `set`.

### `label_detail(request, pk)`

Исходник: `yandex_market/views.py:438`.

Декораторы: `access('print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `LabelDocument.objects.select_related`, `access`, `get_object_or_404`, `render`.

### `label_file(request, pk)`

Исходник: `yandex_market/views.py:443`.

Декораторы: `access('print_labels')`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FileResponse`, `access`, `document.file.open`, `get_object_or_404`, `request.GET.get`.

### `public_media(request, public_id)`

Исходник: `yandex_market/views.py:453`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `FileResponse`, `get_object_or_404`, `media.image.open`.

### `retry(request, pk)`

Исходник: `yandex_market/views.py:462`.

Декораторы: `access('retry_sync', post=True)`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `SyncJob.objects.filter`, `SyncJob.objects.filter(pk=pk).exclude`, `SyncJob.objects.filter(pk=pk).exclude(state='running').update`, `SyncJob.objects.select_related`, `ValidationError`, `access`, `audit`, `confirmed`, `get_object_or_404`, `redirect`, `request.user.has_perm`, `reverse`, `timezone.now`.

## `yandex_market/webhooks.py`

Публичный приём уведомлений Яндекса с проверкой входящего контекста и защитой повторов.

Импорты: `django.conf`, `django.db`, `django.db.models`, `django.http`, `django.utils`, `django.views.decorators.csrf`, `django.views.decorators.http`, `models`, `queue`.

### `allowed_source(request)`

Исходник: `yandex_market/webhooks.py:20`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `any`, `ipaddress.ip_address`, `ipaddress.ip_network`, `request.META.get`, `request.META.get('HTTP_X_FORWARDED_FOR', '').split`, `reversed`, `value.strip`.

### `notification(request)`

Исходник: `yandex_market/webhooks.py:37`.

Декораторы: `csrf_exempt`; `require_POST`.

Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.

Статические вызовы: `F`, `Integration.objects.filter`, `Integration.objects.filter(pk=integration.pk).update`, `Integration.objects.get`, `JsonResponse`, `WebhookEvent.objects.get_or_create`, `allowed_source`, `enqueue`, `hashlib.sha256`, `hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest`, `int`, `json.dumps`, `json.dumps(payload, sort_keys=True, separators=(',', ':')).encode`, `json.loads`, `len`, `timezone.now`, `timezone.now().isoformat`, `transaction.atomic`, `transaction.on_commit`.
