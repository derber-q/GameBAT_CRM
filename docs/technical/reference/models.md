# Схема собственных приложений

<!-- Сгенерировано scripts/build_technical_reference.py; не редактировать вручную. -->

Справочник исходников и метаданных схемы, без рабочих записей/ключей. Перегенерация: `.venv/Scripts/python.exe scripts/build_technical_reference.py`.

Конкретных собственных моделей: **134**.

Метаданные моделей не показывают значения записей. `blank/null/editable` не заменяют ограничения формы, permissions и проверки сервиса. `on_delete=CASCADE` не означает разрешённое пользовательское удаление документа.

## `core.CurrencyRate` — курс валют

Кэш валютной пары для интерфейса; исторические документы хранят собственные курсы.

Таблица `core_currencyrate`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `pair` | CharField; null=False; blank=False; editable=True; max_length=7 | Валютная пара; choices: USD_RUB → USD/RUB; AED_RUB → AED/RUB; USD_AED → USD/AED |
| `rate` | DecimalField; null=True; blank=True; editable=True; max_digits=16; decimal_places=6 | Курс |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |

Permissions: [('access_admin_panel', 'Может входить в административную панель')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: ('rate__gte', 0), ('rate__isnull', True)) name='currency_rate_nonnegative'>]`; unique_together: `()`.

## `accounts.User` — пользователь

Пользователь CRM с Django permissions; защищённый документ не является публичным медиа.

Таблица `accounts_user`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `password` | CharField; null=False; blank=False; editable=True; max_length=128 | пароль |
| `last_login` | DateTimeField; null=True; blank=True; editable=True | последний вход |
| `is_superuser` | BooleanField; null=False; blank=False; editable=True | статус суперпользователя |
| `username` | CharField; null=False; blank=False; editable=True; max_length=150 | имя пользователя |
| `first_name` | CharField; null=False; blank=True; editable=True; max_length=150 | имя |
| `last_name` | CharField; null=False; blank=True; editable=True; max_length=150 | фамилия |
| `email` | CharField; null=False; blank=True; editable=True; max_length=254 | адрес электронной почты |
| `is_staff` | BooleanField; null=False; blank=False; editable=True | статус персонала |
| `is_active` | BooleanField; null=False; blank=False; editable=True | активный |
| `date_joined` | DateTimeField; null=False; blank=False; editable=True | дата регистрации |
| `full_name` | CharField; null=False; blank=True; editable=True; max_length=255 | Ф.И.О. |
| `phone_1` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №1 |
| `phone_2` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №2 |
| `phone_3` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №3 |
| `telegram` | CharField; null=False; blank=True; editable=True; max_length=100 | Telegram |
| `verification_document` | FileField; null=False; blank=True; editable=True; max_length=100 | Подтверждающий документ |
| `groups` | ManyToManyField; null=False; blank=True; editable=True | группы → auth.Group |
| `user_permissions` | ManyToManyField; null=False; blank=True; editable=True | права пользователя → auth.Permission |

Permissions: [('view_user_document', 'Может просматривать подтверждающие документы'), ('reset_user_password', 'Может сбрасывать пароли пользователей')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `accounts.PermissionSetMetadata` — описание набора прав

Дополнительные метаданные набора прав Django Group; не второй источник permissions.

Таблица `accounts_permissionsetmetadata`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `group` | OneToOneField; null=False; blank=False; editable=True | Набор прав → auth.Group; on_delete=CASCADE |
| `description` | TextField; null=False; blank=True; editable=True | Описание |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `catalog.Platform` — платформа

Игровая платформа; не площадка реализации SalesPlatform.

Таблица `catalog_platform`; порядок `('name',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=120 | Название |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: expressions=(Lower(F(name)),) name='platform_name_ci_unique'>]`; unique_together: `()`.

## `catalog.Brand` — бренд

Справочник брендов техники для карточек, фильтров и группировки.

Таблица `catalog_brand`; порядок `('name',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=120 | Название |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `catalog.ProductType` — тип товара

Тип техники, участвующий в фильтрах и закупочных тарифах.

Таблица `catalog_producttype`; порядок `('name',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=120 | Название |
| `procurement_delivery_group` | CharField; null=False; blank=False; editable=True; max_length=16 | Тариф доставки закупочного прайса; choices: general → Прочая техника; devices → Консоли, мини-ПК и VR/AR; storage → Память и накопители |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `catalog.GameSeries` — игровая серия

Игровая серия для группировки номенклатуры, не издание отдельного диска.

Таблица `catalog_gameseries`; порядок `('name', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `normalized_name` | CharField; null=False; blank=False; editable=False; max_length=255 | Нормализованное название |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создано |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `catalog.CD` — CD

Карточка диска/игры с платформой и серией; физическое наличие хранится по складам.

Таблица `catalog_cd`; порядок `('name', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `created_at` | DateTimeField; null=True; blank=True; editable=False | Создан |
| `created_by` | ForeignKey; null=True; blank=True; editable=False | Кем создан → accounts.User; on_delete=SET_NULL |
| `creation_source` | CharField; null=False; blank=False; editable=False; max_length=16 | Происхождение карточки; choices: unknown → Происхождение не подтверждено; web → Веб-форма номенклатуры; automatic → Команда, скрипт или автоматическое создание |
| `newness_months` | PositiveIntegerField; null=False; blank=False; editable=True | Срок новинки, месяцев |
| `newness_until` | DateTimeField; null=True; blank=True; editable=False | Новинка до |
| `newness_backfill_checked_at` | DateTimeField; null=True; blank=True; editable=False | Проверка переноса статуса новинки |
| `description` | TextField; null=False; blank=True; editable=True | Описание |
| `title_image` | FileField; null=False; blank=True; editable=True; max_length=100 | Титульное фото |
| `sku` | CharField; null=False; blank=True; editable=True; max_length=100 | Артикул |
| `quantity_on_consignment` | PositiveIntegerField; null=False; blank=False; editable=False | На реализации |
| `zero_stock_since` | DateTimeField; null=True; blank=True; editable=False | Нулевой складской остаток с |
| `has_been_in_stock` | BooleanField; null=False; blank=False; editable=False | Ранее был на физическом складе |
| `cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Средняя себестоимость |
| `avito_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Цена Avito |
| `wholesale_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Оптовая цена |
| `wholesale_site_enabled` | BooleanField; null=False; blank=False; editable=True | Публиковать на оптовой витрине |
| `exclude_from_supplier_template` | BooleanField; null=False; blank=False; editable=True | Не отображать в шаблоне для поставщиков |
| `yandex_market_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Цена Яндекс Маркет |
| `avito_markup_from_wholesale` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Наценка от опта для Avito |
| `yandex_markup_from_wholesale` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Наценка от опта для Яндекс Маркет |
| `comment` | TextField; null=False; blank=True; editable=True | Комментарий |
| `yandex_calculated_price` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Рассчитанная цена FBS, ₽ |
| `yandex_pricing_integration` | ForeignKey; null=True; blank=True; editable=True | Подключение для расчёта FBS → yandex_market.Integration; on_delete=SET_NULL |
| `yandex_pricing_category` | ForeignKey; null=True; blank=True; editable=True | Категория для расчёта FBS → yandex_market.CategorySchema; on_delete=SET_NULL |
| `is_archived` | BooleanField; null=False; blank=False; editable=True | Удалён из активной номенклатуры |
| `archived_at` | DateTimeField; null=True; blank=True; editable=False | Дата удаления |
| `archived_by` | ForeignKey; null=True; blank=True; editable=False | Кем удалён → accounts.User; on_delete=SET_NULL |
| `yandex_desired_profit` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Желаемая чистая прибыль, ₽ |
| `length_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Длина упаковки, см |
| `width_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Ширина упаковки, см |
| `height_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Высота упаковки, см |
| `platform` | ForeignKey; null=False; blank=False; editable=True | Платформа → catalog.Platform; on_delete=PROTECT |
| `game_series` | ForeignKey; null=True; blank=True; editable=True | Игровая серия → catalog.GameSeries; on_delete=PROTECT |
| `cusa_ppsa_code` | CharField; null=False; blank=True; editable=True; max_length=100 | CUSA/PPSA код |
| `weight_grams` | PositiveIntegerField; null=False; blank=True; editable=True | Вес, г |

Permissions: [('view_nomenclature', 'Номенклатура: просмотр'), ('change_cd_platform', 'CD: изменение платформы'), ('change_cd_game_series', 'CD: изменение игровой серии'), ('change_cd_name', 'CD: изменение названия'), ('change_cd_description', 'CD: изменение описания'), ('change_cd_sku', 'CD: изменение артикула'), ('change_cd_barcode', 'CD: изменение штрихкода'), ('change_cd_weight', 'CD: изменение веса'), ('change_cd_cusa_ppsa_code', 'CD: изменение CUSA/PPSA'), ('change_cd_comment', 'CD: изменение комментария'), ('change_cd_media', 'CD: изменение изображений')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity_on_consignment__gte', 0)) name='cd_consignment_nonnegative'>, <CheckConstraint: condition=(AND: ('cost__gte', 0)) name='cd_cost_nonnegative'>, <CheckConstraint: condition=(OR: ('avito_price__gte', 0), ('avito_price__isnull', True)) name='cd_avito_price_nonnegative'>, <CheckConstraint: condition=(OR: ('wholesale_price__gte', 0), ('wholesale_price__isnull', True)) name='cd_wholesale_price_nonnegative'>, <CheckConstraint: condition=(OR: ('yandex_market_price__gte', 0), ('yandex_market_price__isnull', True)) name='cd_yandex_price_nonnegative'>, <CheckConstraint: condition=(OR: ('avito_markup_from_wholesale__gte', 0), ('avito_markup_from_wholesale__isnull', True)) name='cd_avito_markup_nonnegative'>, <CheckConstraint: condition=(OR: ('yandex_markup_from_wholesale__gte', 0), ('yandex_markup_from_wholesale__isnull', True)) name='cd_yandex_markup_nonnegative'>, <CheckConstraint: condition=(AND: ('weight_grams__gt', 0)) name='cd_weight_positive'>]`; unique_together: `()`.

## `catalog.Tech` — техника

Карточка техники с брендом и типом; остатки площадок и складов учитываются отдельно.

Таблица `catalog_tech`; порядок `('name', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `created_at` | DateTimeField; null=True; blank=True; editable=False | Создан |
| `created_by` | ForeignKey; null=True; blank=True; editable=False | Кем создан → accounts.User; on_delete=SET_NULL |
| `creation_source` | CharField; null=False; blank=False; editable=False; max_length=16 | Происхождение карточки; choices: unknown → Происхождение не подтверждено; web → Веб-форма номенклатуры; automatic → Команда, скрипт или автоматическое создание |
| `newness_months` | PositiveIntegerField; null=False; blank=False; editable=True | Срок новинки, месяцев |
| `newness_until` | DateTimeField; null=True; blank=True; editable=False | Новинка до |
| `newness_backfill_checked_at` | DateTimeField; null=True; blank=True; editable=False | Проверка переноса статуса новинки |
| `description` | TextField; null=False; blank=True; editable=True | Описание |
| `title_image` | FileField; null=False; blank=True; editable=True; max_length=100 | Титульное фото |
| `sku` | CharField; null=False; blank=True; editable=True; max_length=100 | Артикул |
| `quantity_on_consignment` | PositiveIntegerField; null=False; blank=False; editable=False | На реализации |
| `zero_stock_since` | DateTimeField; null=True; blank=True; editable=False | Нулевой складской остаток с |
| `has_been_in_stock` | BooleanField; null=False; blank=False; editable=False | Ранее был на физическом складе |
| `cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Средняя себестоимость |
| `avito_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Цена Avito |
| `wholesale_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Оптовая цена |
| `wholesale_site_enabled` | BooleanField; null=False; blank=False; editable=True | Публиковать на оптовой витрине |
| `exclude_from_supplier_template` | BooleanField; null=False; blank=False; editable=True | Не отображать в шаблоне для поставщиков |
| `yandex_market_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Цена Яндекс Маркет |
| `avito_markup_from_wholesale` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Наценка от опта для Avito |
| `yandex_markup_from_wholesale` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Наценка от опта для Яндекс Маркет |
| `comment` | TextField; null=False; blank=True; editable=True | Комментарий |
| `length_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Длина упаковки, см |
| `width_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Ширина упаковки, см |
| `height_cm` | DecimalField; null=True; blank=True; editable=True; max_digits=8; decimal_places=3 | Высота упаковки, см |
| `yandex_calculated_price` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Рассчитанная цена FBS, ₽ |
| `yandex_pricing_integration` | ForeignKey; null=True; blank=True; editable=True | Подключение для расчёта FBS → yandex_market.Integration; on_delete=SET_NULL |
| `yandex_pricing_category` | ForeignKey; null=True; blank=True; editable=True | Категория для расчёта FBS → yandex_market.CategorySchema; on_delete=SET_NULL |
| `is_archived` | BooleanField; null=False; blank=False; editable=True | Удалён из активной номенклатуры |
| `archived_at` | DateTimeField; null=True; blank=True; editable=False | Дата удаления |
| `archived_by` | ForeignKey; null=True; blank=True; editable=False | Кем удалён → accounts.User; on_delete=SET_NULL |
| `yandex_desired_profit` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Желаемая чистая прибыль, ₽ |
| `brand` | ForeignKey; null=False; blank=False; editable=True | Бренд → catalog.Brand; on_delete=PROTECT |
| `product_type` | ForeignKey; null=False; blank=False; editable=True | Тип товара → catalog.ProductType; on_delete=PROTECT |
| `weight_grams` | PositiveIntegerField; null=True; blank=True; editable=True | Вес, г |

Permissions: [('change_tech_brand', 'Tech: изменение бренда'), ('change_tech_product_type', 'Tech: изменение типа товара'), ('change_tech_name', 'Tech: изменение названия'), ('change_tech_description', 'Tech: изменение описания'), ('change_tech_sku', 'Tech: изменение артикула'), ('change_tech_barcode', 'Tech: изменение штрихкода'), ('change_tech_weight', 'Tech: изменение веса'), ('change_tech_comment', 'Tech: изменение комментария'), ('change_tech_media', 'Tech: изменение изображений')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity_on_consignment__gte', 0)) name='tech_consignment_nonnegative'>, <CheckConstraint: condition=(AND: ('cost__gte', 0)) name='tech_cost_nonnegative'>, <CheckConstraint: condition=(OR: ('avito_price__gte', 0), ('avito_price__isnull', True)) name='tech_avito_price_nonnegative'>, <CheckConstraint: condition=(OR: ('wholesale_price__gte', 0), ('wholesale_price__isnull', True)) name='tech_wholesale_price_nonnegative'>, <CheckConstraint: condition=(OR: ('yandex_market_price__gte', 0), ('yandex_market_price__isnull', True)) name='tech_yandex_price_nonnegative'>, <CheckConstraint: condition=(OR: ('avito_markup_from_wholesale__gte', 0), ('avito_markup_from_wholesale__isnull', True)) name='tech_avito_markup_nonnegative'>, <CheckConstraint: condition=(OR: ('yandex_markup_from_wholesale__gte', 0), ('yandex_markup_from_wholesale__isnull', True)) name='tech_yandex_markup_nonnegative'>, <CheckConstraint: condition=(OR: ('weight_grams__gt', 0), ('weight_grams__isnull', True)) name='tech_weight_positive_or_null'>]`; unique_together: `()`.

## `catalog.ProductSupplierExclusion` — исключение поставщика для товара

Исключение товара из нового выбора поставщика; старые закупочные снимки сохраняются.

Таблица `catalog_productsupplierexclusion`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=CASCADE |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=CASCADE |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | supplier → partners.Supplier; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Исключён |
| `created_by` | ForeignKey; null=True; blank=True; editable=True | created by → accounts.User; on_delete=SET_NULL |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='supplier_exclusion_exact_product'>, <UniqueConstraint: fields=('cd', 'supplier') name='unique_supplier_exclusion_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('tech', 'supplier') name='unique_supplier_exclusion_tech' condition=(AND: ('tech__isnull', False))>]`; unique_together: `()`.

## `catalog.ProductImage` — изображение товара

Защищённое изображение карточки с порядком галереи.

Таблица `catalog_productimage`; порядок `('image_kind', 'sort_order', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=True | CD → catalog.CD; on_delete=CASCADE |
| `tech` | ForeignKey; null=True; blank=True; editable=True | Tech → catalog.Tech; on_delete=CASCADE |
| `image_kind` | CharField; null=False; blank=False; editable=True; max_length=16 | Категория; choices: additional → Дополнительное фото; product → Изображение продукта |
| `image` | FileField; null=False; blank=False; editable=True; max_length=100 | Изображение |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | Порядок |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Добавлено |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='product_image_exact_product'>]`; unique_together: `()`.

## `catalog.ProductRemovalEvent` — удаление товара

След контролируемого удаления/архивации карточки без уничтожения истории операции.

Таблица `catalog_productremovalevent`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `action` | CharField; null=False; blank=False; editable=True; max_length=16 | Действие; choices: hard_delete → Безвозвратное удаление; archive → Удаление с сохранением истории |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | Тип товара |
| `product_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | ID товара |
| `product_sku` | CharField; null=False; blank=True; editable=True; max_length=100 | Артикул |
| `product_name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `reason` | TextField; null=False; blank=False; editable=True | Причина |
| `actor` | ForeignKey; null=True; blank=True; editable=True | Пользователь → accounts.User; on_delete=SET_NULL |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата и время |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `catalog.SystemProduct` — системная позиция

Две внутренние позиции, не являющиеся физической номенклатурой.

Таблица `catalog_systemproduct`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `kind` | CharField; null=False; blank=False; editable=False; max_length=24 | Системный тип; choices: DIGITAL_PRODUCT → Цифровой товар; EXPENSE → Расход |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('kind__in', ('DIGITAL_PRODUCT', 'EXPENSE'))) name='system_product_known_kind'>]`; unique_together: `()`.

## `catalog.BarcodeRegistry` — регистрация штрихкода

Глобальный реестр строковых штрихкодов, включая альтернативные и ведущие нули.

Таблица `catalog_barcoderegistry`; порядок `('value',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `value` | CharField; null=False; blank=False; editable=True; max_length=100 | Штрихкод |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | Тип товара; choices: cd → CD; tech → Tech; system → Системная позиция |
| `cd` | ForeignKey; null=True; blank=True; editable=True | CD → catalog.CD; on_delete=CASCADE |
| `tech` | ForeignKey; null=True; blank=True; editable=True | Tech → catalog.Tech; on_delete=CASCADE |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `system_product` | OneToOneField; null=True; blank=True; editable=True | Системная позиция → catalog.SystemProduct; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('system_product__isnull', True), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('system_product__isnull', True), ('tech__isnull', False)), (AND: ('cd__isnull', True), ('product_kind', 'system'), ('system_product__isnull', False), ('tech__isnull', True))) name='barcode_registry_exact_product'>]`; unique_together: `()`.

## `catalog.ProductChangeEvent` — событие изменения товара

Неизменяемое событие аудита карточки/связанной операции.

Таблица `catalog_productchangeevent`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `actor` | ForeignKey; null=True; blank=True; editable=False | Пользователь → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата и время |
| `source` | CharField; null=False; blank=False; editable=False; max_length=24 | Источник; choices: nomenclature → Номенклатура; crm → CRM; django_admin → Django Admin |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | CD → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | Tech → catalog.Tech; on_delete=PROTECT |
| `action_kind` | CharField; null=False; blank=True; editable=False; max_length=32 | Тип связанного действия; choices: sale → Продажа; warehouse_transfer → Перемещение; consignment → Реализация; supply → Поставка; supply_finalization → Финализация прихода |
| `action_object_id` | PositiveBigIntegerField; null=True; blank=True; editable=False | ID связанного действия |
| `action_label` | CharField; null=False; blank=True; editable=False; max_length=120 | Номер связанного действия |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='product_change_event_exact_product'>, <CheckConstraint: condition=(OR: (AND: ('action_kind', ''), ('action_label', ''), ('action_object_id__isnull', True)), (AND: (NOT (AND: ('action_kind', ''))), ('action_object_id__isnull', False), (NOT (AND: ('action_label', ''))))) name='product_change_event_valid_action'>]`; unique_together: `()`.

## `catalog.ProductFieldChange` — изменение поля товара

Старое и новое значение одного поля события аудита.

Таблица `catalog_productfieldchange`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `event` | ForeignKey; null=False; blank=False; editable=False | Событие → catalog.ProductChangeEvent; on_delete=CASCADE |
| `field_name` | CharField; null=False; blank=False; editable=False; max_length=100 | Поле |
| `field_label` | CharField; null=False; blank=False; editable=False; max_length=255 | Название поля |
| `old_value` | TextField; null=False; blank=True; editable=False | Старое значение |
| `new_value` | TextField; null=False; blank=True; editable=False | Новое значение |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `partners.Supplier` — поставщик

Поставщик закупки с отдельно защищёнными реквизитами.

Таблица `partners_supplier`; порядок `('letter',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `letter` | CharField; null=False; blank=False; editable=True; max_length=8 | Буква |
| `highlight_color` | CharField; null=False; blank=False; editable=True; max_length=7 | Цвет |
| `legal_entity` | CharField; null=False; blank=False; editable=True; max_length=255 | Юридическое лицо |
| `email` | CharField; null=False; blank=True; editable=True; max_length=254 | Email |
| `phone_1` | CharField; null=False; blank=False; editable=True; max_length=40 | Телефон №1 |
| `phone_2` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №2 |
| `phone_3` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №3 |
| `website` | CharField; null=False; blank=True; editable=True; max_length=200 | Сайт |
| `telegram` | CharField; null=False; blank=True; editable=True; max_length=100 | Telegram |
| `priority` | PositiveIntegerField; null=False; blank=False; editable=True | Приоритет |

Permissions: [('view_supplier_details', 'Может видеть полные данные поставщиков')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `partners.SalesPlatform` — площадка реализации

Площадка реализации со своими партиями; не игровая Platform.

Таблица `partners_salesplatform`; порядок `('name',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `address` | CharField; null=False; blank=False; editable=True; max_length=500 | Адрес |
| `legal_entity` | CharField; null=False; blank=False; editable=True; max_length=255 | Юридическое лицо |
| `phone_1` | CharField; null=False; blank=False; editable=True; max_length=40 | Телефон №1 |
| `phone_2` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №2 |
| `phone_3` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №3 |
| `email` | CharField; null=False; blank=True; editable=True; max_length=254 | Email |
| `telegram` | CharField; null=False; blank=True; editable=True; max_length=100 | Telegram |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `partners.Partner` — партнёр

Единый контрагент, связывающий финансовую карточку и клиентские сценарии.

Таблица `partners_partner`; порядок `('name', 'pk')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `creation_key` | UUIDField; null=False; blank=False; editable=False; max_length=32 | creation key |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `contact_person` | CharField; null=False; blank=True; editable=True; max_length=255 | Контактное лицо |
| `phone_1` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №1 |
| `phone_2` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №2 |
| `telegram` | CharField; null=False; blank=True; editable=True; max_length=100 | Telegram |
| `address` | TextField; null=False; blank=True; editable=True | Адрес |
| `platform` | OneToOneField; null=True; blank=True; editable=True | Площадка реализации → partners.SalesPlatform; on_delete=PROTECT |
| `creditor` | OneToOneField; null=False; blank=False; editable=False | Кредиторский счёт → creditors.Creditor; on_delete=PROTECT |
| `is_archived` | BooleanField; null=False; blank=False; editable=True | В архиве |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: [('view_partner_contacts', 'Может просматривать контакты партнёров')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `warehouse.Warehouse` — склад

Физический склад с собственной кассой, сейфом и остатками.

Таблица `warehouse_warehouse`; порядок `('name',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |

Permissions: [('view_global_stock', 'Может просматривать общие остатки'), ('view_warehouse_stock', 'Может просматривать остатки отдельного склада'), ('change_storage_location', 'Может изменять места хранения товаров')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `warehouse.WarehouseStorageLocation` — место хранения на складе

Каноническое физическое место, уникальное внутри конкретного склада.

Таблица `warehouse_warehousestoragelocation`; порядок `('room', 'rack', 'shelf', 'canonical_value', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=CASCADE |
| `room` | CharField; null=False; blank=False; editable=True; max_length=1 | Помещение |
| `rack` | PositiveIntegerField; null=False; blank=False; editable=True | Стеллаж |
| `shelf` | PositiveIntegerField; null=False; blank=False; editable=True | Полка |
| `columns` | JSONField; null=False; blank=True; editable=True | Столбцы |
| `canonical_value` | CharField; null=False; blank=False; editable=False; max_length=255 | Каноническое значение |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('warehouse', 'canonical_value') name='unique_storage_location_per_warehouse'>, <CheckConstraint: condition=(AND: ('rack__gt', 0)) name='storage_location_rack_positive'>, <CheckConstraint: condition=(AND: ('shelf__gt', 0)) name='storage_location_shelf_positive'>]`; unique_together: `()`.

## `warehouse.CDWarehouseStock` — остаток CD на складе

Физический остаток конкретного диска на конкретном складе.

Таблица `warehouse_cdwarehousestock`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `cd` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('warehouse', 'cd') name='unique_cd_warehouse_stock'>, <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='cd_warehouse_quantity_nonnegative'>]`; unique_together: `()`.

## `warehouse.TechWarehouseStock` — остаток техники на складе

Физический остаток конкретной техники на конкретном складе.

Таблица `warehouse_techwarehousestock`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `tech` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('warehouse', 'tech') name='unique_tech_warehouse_stock'>, <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='tech_warehouse_quantity_nonnegative'>]`; unique_together: `()`.

## `warehouse.CDWarehouseStorageAssignment` — размещение CD на складе

Назначение мест хранения диска на данном складе, без самостоятельного количества.

Таблица `warehouse_cdwarehousestorageassignment`; порядок `('position', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `position` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Порядок |
| `stock` | ForeignKey; null=False; blank=False; editable=True | Остаток CD → warehouse.CDWarehouseStock; on_delete=CASCADE |
| `location` | ForeignKey; null=False; blank=False; editable=True | Место хранения → warehouse.WarehouseStorageLocation; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('stock', 'location') name='unique_cd_stock_storage_location'>, <UniqueConstraint: fields=('stock', 'position') name='unique_cd_stock_storage_position'>]`; unique_together: `()`.

## `warehouse.TechWarehouseStorageAssignment` — размещение техники на складе

Назначение мест хранения техники на данном складе, без отдельной оценки партии.

Таблица `warehouse_techwarehousestorageassignment`; порядок `('position', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `position` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Порядок |
| `stock` | ForeignKey; null=False; blank=False; editable=True | Остаток Tech → warehouse.TechWarehouseStock; on_delete=CASCADE |
| `location` | ForeignKey; null=False; blank=False; editable=True | Место хранения → warehouse.WarehouseStorageLocation; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('stock', 'location') name='unique_tech_stock_storage_location'>, <UniqueConstraint: fields=('stock', 'position') name='unique_tech_stock_storage_position'>]`; unique_together: `()`.

## `warehouse.WarehouseRevision` — ревизия склада

Сессия проверки наличия выбранного склада; отметка проверки не проводит движение.

Таблица `warehouse_warehouserevision`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | warehouse → warehouse.Warehouse; on_delete=PROTECT |
| `started_at` | DateTimeField; null=False; blank=True; editable=False | started at |
| `started_by` | ForeignKey; null=True; blank=False; editable=True | started by → accounts.User; on_delete=SET_NULL |
| `is_active` | BooleanField; null=False; blank=False; editable=True | is active |
| `closed_at` | DateTimeField; null=True; blank=True; editable=True | closed at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('warehouse',) name='one_active_warehouse_revision' condition=(AND: ('is_active', True))>, <CheckConstraint: condition=(OR: (AND: ('closed_at__isnull', True), ('is_active', True)), (AND: ('closed_at__isnull', False), ('is_active', False))) name='warehouse_revision_closed_state'>]`; unique_together: `()`.

## `warehouse.WarehouseRevisionItem` — отметка ревизии склада

Результат сверки одной позиции в конкретной сессии ревизии.

Таблица `warehouse_warehouserevisionitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `revision` | ForeignKey; null=False; blank=False; editable=True | revision → warehouse.WarehouseRevision; on_delete=CASCADE |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=PROTECT |
| `checked` | BooleanField; null=False; blank=False; editable=True | checked |
| `checked_at` | DateTimeField; null=True; blank=True; editable=True | checked at |
| `checked_by` | ForeignKey; null=True; blank=False; editable=True | checked by → accounts.User; on_delete=SET_NULL |
| `invalidated_at` | DateTimeField; null=True; blank=True; editable=True | invalidated at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='revision_item_one_product'>, <UniqueConstraint: fields=('revision', 'cd') name='unique_revision_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('revision', 'tech') name='unique_revision_tech' condition=(AND: ('tech__isnull', False))>, <CheckConstraint: condition=(OR: ('checked', False), ('checked_at__isnull', False)) name='revision_checked_has_date'>]`; unique_together: `()`.

## `warehouse.WarehouseTransfer` — межскладское перемещение

Документ перемещения: отправка, путь и приёмка различаются.

Таблица `warehouse_warehousetransfer`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `source_warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад-отправитель → warehouse.Warehouse; on_delete=PROTECT |
| `destination_warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад-получатель → warehouse.Warehouse; on_delete=PROTECT |
| `status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус; choices: created → Создан; assembled → Собран; shipped → Отправлен; accepted → Принят |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | Создал → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |
| `assembled_at` | DateTimeField; null=True; blank=True; editable=False | Собран |
| `shipped_at` | DateTimeField; null=True; blank=True; editable=False | Отправлен |
| `accepted_at` | DateTimeField; null=True; blank=True; editable=False | Принят |
| `assembled_by` | ForeignKey; null=True; blank=True; editable=False | Собрал → accounts.User; on_delete=PROTECT |
| `shipped_by` | ForeignKey; null=True; blank=True; editable=False | Отправил → accounts.User; on_delete=PROTECT |
| `accepted_by` | ForeignKey; null=True; blank=True; editable=False | Принял → accounts.User; on_delete=PROTECT |

Permissions: [('view_transfers', 'Может просматривать перемещения'), ('create_transfer', 'Может создавать перемещения'), ('mark_transfer_assembled', 'Может отмечать перемещение собранным'), ('mark_transfer_shipped', 'Может отмечать перемещение отправленным'), ('mark_transfer_accepted', 'Может принимать перемещение')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(NOT (AND: ('source_warehouse', F(destination_warehouse)))) name='warehouse_transfer_different_destinations'>]`; unique_together: `()`.

## `warehouse.CDWarehouseTransferItem` — позиция CD в перемещении

Неизменяемая строка перемещения диска с количественным/стоимостным снимком.

Таблица `warehouse_cdwarehousetransferitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_cost_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы |
| `transfer` | ForeignKey; null=False; blank=False; editable=True | Перемещение → warehouse.WarehouseTransfer; on_delete=PROTECT |
| `cd` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('transfer', 'cd') name='unique_cd_transfer_item'>, <CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='cd_transfer_quantity_positive'>]`; unique_together: `()`.

## `warehouse.TechWarehouseTransferItem` — позиция техники в перемещении

Неизменяемая строка перемещения техники с сохранёнными условиями.

Таблица `warehouse_techwarehousetransferitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_cost_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы |
| `transfer` | ForeignKey; null=False; blank=False; editable=True | Перемещение → warehouse.WarehouseTransfer; on_delete=PROTECT |
| `tech` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('transfer', 'tech') name='unique_tech_transfer_item'>, <CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='tech_transfer_quantity_positive'>]`; unique_together: `()`.

## `supplies.Supply` — поставка

Приход выбранного склада; проверка цен и фактическая приёмка — разные этапы.

Таблица `supplies_supply`; порядок `('-accepted_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `accepted_at` | DateTimeField; null=False; blank=True; editable=False | Принята |
| `accepted_by` | ForeignKey; null=False; blank=False; editable=True | Принял → accounts.User; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад поступления → warehouse.Warehouse; on_delete=PROTECT |
| `status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус; choices: price_review → Требуется проверка цен; trip_finalization → Ждёт финализации рейса; accepted → Принята; cancelled → Отменена |
| `total_units` | PositiveIntegerField; null=False; blank=False; editable=True | Физических единиц |
| `goods_total_before_expenses` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Товары до расходов |
| `expenses_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Дополнительные расходы |
| `weight_transport_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Транспортные расходы по весу |
| `total_weight_grams` | PositiveBigIntegerField; null=True; blank=True; editable=False | Общий вес поставки, г |
| `grand_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Итого |
| `cancelled_at` | DateTimeField; null=True; blank=True; editable=False | Отменена |
| `cancelled_by` | ForeignKey; null=True; blank=True; editable=False | Отменил → accounts.User; on_delete=PROTECT |
| `cancellation_comment` | TextField; null=False; blank=True; editable=False | Причина отмены |
| `revision_number` | PositiveIntegerField; null=False; blank=False; editable=False | Текущая редакция |
| `last_revised_at` | DateTimeField; null=True; blank=True; editable=False | Последнее изменение |
| `last_revised_by` | ForeignKey; null=True; blank=True; editable=False | Последним изменил → accounts.User; on_delete=PROTECT |
| `price_reviewed_at` | DateTimeField; null=True; blank=True; editable=False | Цены подтверждены |
| `price_reviewed_by` | ForeignKey; null=True; blank=True; editable=False | Цены подтвердил → accounts.User; on_delete=PROTECT |

Permissions: [('cancel_supply', 'Может отменять принятые приходы'), ('edit_accepted_supply', 'Может редактировать принятые приходы'), ('finalize_supply', 'Может выполнять финализацию прихода')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('total_units__gt', 0)) name='supply_total_units_positive'>, <CheckConstraint: condition=(AND: ('goods_total_before_expenses__gte', 0)) name='supply_goods_total_nonnegative'>, <CheckConstraint: condition=(AND: ('expenses_total__gte', 0)) name='supply_expenses_total_nonnegative'>, <CheckConstraint: condition=(AND: ('weight_transport_cost__gte', 0)) name='supply_weight_transport_nonnegative'>, <CheckConstraint: condition=(OR: ('total_weight_grams__gt', 0), ('total_weight_grams__isnull', True)) name='supply_total_weight_positive_or_legacy'>, <CheckConstraint: condition=(AND: ('grand_total__gte', 0)) name='supply_grand_total_nonnegative'>, <CheckConstraint: condition=(OR: (AND: ('cancellation_comment', ''), ('cancelled_at__isnull', True), ('cancelled_by__isnull', True), ('status', 'accepted')), (AND: ('cancellation_comment', ''), ('cancelled_at__isnull', True), ('cancelled_by__isnull', True), ('status__in', ('price_review', 'trip_finalization'))), (AND: ('cancelled_at__isnull', False), ('cancelled_by__isnull', False), ('status', 'cancelled'), (NOT (AND: ('cancellation_comment', ''))))) name='supply_cancellation_fields_consistent'>]`; unique_together: `()`.

## `supplies.SupplyCDItem` — позиция CD в поставке

Строка диска в приходе с закупкой, расходами и возможным источником рейса.

Таблица `supplies_supplycditem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `trip_cost_row` | ForeignKey; null=True; blank=True; editable=False | trip cost row → orders.TripCostRow; on_delete=PROTECT |
| `trip_cost_slot` | PositiveSmallIntegerField; null=False; blank=False; editable=False | trip cost slot |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | Поставщик → partners.Supplier; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `purchase_unit_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Закупочная цена единицы |
| `allocated_expense_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Расход на единицу |
| `weight_grams_snapshot` | PositiveIntegerField; null=True; blank=True; editable=False | Вес единицы на момент прихода, г |
| `line_weight_grams` | PositiveBigIntegerField; null=True; blank=True; editable=False | Вес строки, г |
| `allocated_transport_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Транспортные расходы строки |
| `transport_cost_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Транспортные расходы на единицу |
| `effective_unit_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Итоговая цена единицы |
| `base_line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Закупочная сумма строки |
| `final_line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Итоговая сумма строки |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=False; editable=True; max_length=100 | Артикул |
| `supplier_letter_snapshot` | CharField; null=False; blank=False; editable=True; max_length=8 | Буква поставщика |
| `supplier_color_snapshot` | CharField; null=False; blank=False; editable=True; max_length=7 | Цвет поставщика |
| `supplier_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название поставщика |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Поставка → supplies.Supply; on_delete=PROTECT |
| `product` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='supply_cd_quantity_positive'>, <CheckConstraint: condition=(AND: ('purchase_unit_cost__gte', 0)) name='supply_cd_cost_nonnegative'>, <CheckConstraint: condition=(AND: ('allocated_expense_per_unit__gte', 0)) name='supply_cd_allocated_nonnegative'>, <CheckConstraint: condition=(OR: ('weight_grams_snapshot__gt', 0), ('weight_grams_snapshot__isnull', True)) name='supply_cd_weight_positive_or_legacy'>, <CheckConstraint: condition=(OR: ('line_weight_grams__gt', 0), ('line_weight_grams__isnull', True)) name='supply_cd_line_weight_positive_or_legacy'>, <CheckConstraint: condition=(AND: ('allocated_transport_cost__gte', 0)) name='supply_cd_transport_nonnegative'>, <CheckConstraint: condition=(AND: ('transport_cost_per_unit__gte', 0)) name='supply_cd_transport_unit_nonnegative'>, <CheckConstraint: condition=(AND: ('effective_unit_cost__gte', 0)) name='supply_cd_effective_nonnegative'>, <CheckConstraint: condition=(AND: ('base_line_total__gte', 0)) name='supply_cd_base_total_nonnegative'>, <CheckConstraint: condition=(AND: ('final_line_total__gte', 0)) name='supply_cd_final_total_nonnegative'>]`; unique_together: `()`.

## `supplies.SupplyTechItem` — позиция техники в поставке

Строка техники в приходе; вес и расходы участвуют в расчёте оценки.

Таблица `supplies_supplytechitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `trip_cost_row` | ForeignKey; null=True; blank=True; editable=False | trip cost row → orders.TripCostRow; on_delete=PROTECT |
| `trip_cost_slot` | PositiveSmallIntegerField; null=False; blank=False; editable=False | trip cost slot |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | Поставщик → partners.Supplier; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `purchase_unit_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Закупочная цена единицы |
| `allocated_expense_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Расход на единицу |
| `weight_grams_snapshot` | PositiveIntegerField; null=True; blank=True; editable=False | Вес единицы на момент прихода, г |
| `line_weight_grams` | PositiveBigIntegerField; null=True; blank=True; editable=False | Вес строки, г |
| `allocated_transport_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Транспортные расходы строки |
| `transport_cost_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Транспортные расходы на единицу |
| `effective_unit_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Итоговая цена единицы |
| `base_line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Закупочная сумма строки |
| `final_line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Итоговая сумма строки |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=False; editable=True; max_length=100 | Артикул |
| `supplier_letter_snapshot` | CharField; null=False; blank=False; editable=True; max_length=8 | Буква поставщика |
| `supplier_color_snapshot` | CharField; null=False; blank=False; editable=True; max_length=7 | Цвет поставщика |
| `supplier_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название поставщика |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Поставка → supplies.Supply; on_delete=PROTECT |
| `product` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='supply_tech_quantity_positive'>, <CheckConstraint: condition=(AND: ('purchase_unit_cost__gte', 0)) name='supply_tech_cost_nonnegative'>, <CheckConstraint: condition=(AND: ('allocated_expense_per_unit__gte', 0)) name='supply_tech_allocated_nonnegative'>, <CheckConstraint: condition=(OR: ('weight_grams_snapshot__gt', 0), ('weight_grams_snapshot__isnull', True)) name='supply_tech_weight_positive_or_legacy'>, <CheckConstraint: condition=(OR: ('line_weight_grams__gt', 0), ('line_weight_grams__isnull', True)) name='supply_tech_line_weight_positive_or_legacy'>, <CheckConstraint: condition=(AND: ('allocated_transport_cost__gte', 0)) name='supply_tech_transport_nonnegative'>, <CheckConstraint: condition=(AND: ('transport_cost_per_unit__gte', 0)) name='supply_tech_transport_unit_nonnegative'>, <CheckConstraint: condition=(AND: ('effective_unit_cost__gte', 0)) name='supply_tech_effective_nonnegative'>, <CheckConstraint: condition=(AND: ('base_line_total__gte', 0)) name='supply_tech_base_total_nonnegative'>, <CheckConstraint: condition=(AND: ('final_line_total__gte', 0)) name='supply_tech_final_total_nonnegative'>]`; unique_together: `()`.

## `supplies.SupplyCostCalculation` — расчёт себестоимости поставки

Исторический снимок средневзвешенного расчёта для одного товара.

Таблица `supplies_supplycostcalculation`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Поставка → supplies.Supply; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | CD → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | Техника → catalog.Tech; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=False; editable=False; max_length=100 | Артикул |
| `old_owned_quantity` | PositiveIntegerField; null=False; blank=False; editable=False | Количество на физических складах до поставки |
| `old_unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость до поставки |
| `old_inventory_value` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Стоимость остатка до поставки |
| `incoming_quantity` | PositiveIntegerField; null=False; blank=False; editable=False | Поступило |
| `incoming_value` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Стоимость поступления с расходами |
| `resulting_quantity` | PositiveIntegerField; null=False; blank=False; editable=False | Количество после поставки |
| `resulting_value` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Общая стоимость после поставки |
| `resulting_unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Новая себестоимость |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='supply_cost_calculation_exact_product'>, <UniqueConstraint: fields=('supply', 'cd') name='unique_supply_cd_cost_calculation' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('supply', 'tech') name='unique_supply_tech_cost_calculation' condition=(AND: ('tech__isnull', False))>, <CheckConstraint: condition=(AND: ('incoming_quantity__gt', 0)) name='supply_cost_incoming_quantity_positive'>]`; unique_together: `()`.

## `supplies.SupplyExpense` — дополнительный расход

Независимый дополнительный расход прихода, распределяемый учётным сервисом.

Таблица `supplies_supplyexpense`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Поставка → supplies.Supply; on_delete=PROTECT |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название расхода |
| `amount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('amount__gte', 0)) name='supply_expense_nonnegative'>]`; unique_together: `()`.

## `supplies.SupplyRevision` — редакция принятого прихода

Историческая версия исправления принятого прихода.

Таблица `supplies_supplyrevision`; порядок `('-revision_number', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Приход → supplies.Supply; on_delete=PROTECT |
| `revision_number` | PositiveIntegerField; null=False; blank=False; editable=False | Номер редакции |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создана |
| `created_by` | ForeignKey; null=False; blank=False; editable=False | Автор изменения → accounts.User; on_delete=PROTECT |
| `reason` | TextField; null=False; blank=False; editable=False | Причина изменения |
| `warehouse` | ForeignKey; null=False; blank=False; editable=False | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `accepted_at_snapshot` | DateTimeField; null=False; blank=False; editable=False | Историческая дата прихода |
| `accepted_by_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Принял |
| `total_units` | PositiveIntegerField; null=False; blank=False; editable=False | Физических единиц |
| `goods_total_before_expenses` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Товары до расходов |
| `expenses_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Дополнительные расходы |
| `weight_transport_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Транспортные расходы по весу |
| `total_weight_grams` | PositiveBigIntegerField; null=True; blank=True; editable=False | Общий вес, г |
| `grand_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Итого |
| `diff_summary` | JSONField; null=False; blank=True; editable=False | Сводка изменений |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('supply', 'revision_number') name='unique_supply_revision_number'>]`; unique_together: `()`.

## `supplies.SupplyRevisionItem` — позиция редакции прихода

Сохранённые значения строки конкретной ревизии прихода.

Таблица `supplies_supplyrevisionitem`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `revision` | ForeignKey; null=False; blank=False; editable=True | Редакция → supplies.SupplyRevision; on_delete=CASCADE |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | tech → catalog.Tech; on_delete=PROTECT |
| `supplier` | ForeignKey; null=False; blank=False; editable=False | supplier → partners.Supplier; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=False | Количество |
| `purchase_unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Закупка за единицу |
| `allocated_expense_per_unit` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Обычный расход за единицу |
| `weight_grams_snapshot` | PositiveIntegerField; null=True; blank=True; editable=False | Вес единицы, г |
| `line_weight_grams` | PositiveBigIntegerField; null=True; blank=True; editable=False | Вес строки, г |
| `allocated_transport_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Транспорт строки |
| `transport_cost_per_unit` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Транспорт за единицу |
| `effective_unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Итог за единицу |
| `base_line_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Закупка строки |
| `final_line_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Итого строки |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=True; editable=False; max_length=100 | Артикул |
| `supplier_letter_snapshot` | CharField; null=False; blank=False; editable=False; max_length=8 | Буква поставщика |
| `supplier_color_snapshot` | CharField; null=False; blank=False; editable=False; max_length=7 | Цвет поставщика |
| `supplier_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название поставщика |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='supply_revision_item_exact_product'>]`; unique_together: `()`.

## `supplies.SupplyRevisionExpense` — расход редакции прихода

Снимок расходов версии прихода, а не текущая настройка.

Таблица `supplies_supplyrevisionexpense`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `revision` | ForeignKey; null=False; blank=False; editable=True | Редакция → supplies.SupplyRevision; on_delete=CASCADE |
| `name` | CharField; null=False; blank=False; editable=False; max_length=255 | Название расхода |
| `amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Сумма |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `supplies.SupplyFinalization` — финализация прихода

Неизменяемая история перераспределения глобальной себестоимости.

Таблица `supplies_supplyfinalization`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supply` | ForeignKey; null=False; blank=False; editable=True | Приход → supplies.Supply; on_delete=PROTECT |
| `created_by` | ForeignKey; null=False; blank=False; editable=False | Выполнил → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата и время |
| `supply_revision_number` | PositiveIntegerField; null=False; blank=False; editable=False | Редакция прихода |
| `total_penalty_before_distribution` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Неустойка до автораспределения |
| `status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус; choices: applied → Применена; superseded → Утратила актуальность после редакции прихода |
| `superseded_at` | DateTimeField; null=True; blank=True; editable=False | Утратила актуальность |
| `superseded_by_revision_number` | PositiveIntegerField; null=True; blank=True; editable=False | Заменена редакцией |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('status', 'applied'), ('superseded_at__isnull', True), ('superseded_by_revision_number__isnull', True)), (AND: ('status', 'superseded'), ('superseded_at__isnull', False), ('superseded_by_revision_number__isnull', False))) name='supply_finalization_status_consistent'>]`; unique_together: `()`.

## `supplies.SupplyFinalizationItem` — позиция финализации прихода

Стоимость строки до/после конкретной финализации.

Таблица `supplies_supplyfinalizationitem`; порядок `('product_kind', 'product_name_snapshot', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `finalization` | ForeignKey; null=False; blank=False; editable=True | Финализация → supplies.SupplyFinalization; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | CD → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | Техника → catalog.Tech; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=True; editable=False; max_length=100 | Артикул |
| `global_quantity_snapshot` | PositiveIntegerField; null=False; blank=False; editable=False | Остаток на физических складах |
| `old_global_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Старая себестоимость |
| `new_global_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Новая себестоимость |
| `difference_per_unit` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Изменение на единицу |
| `value_difference` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Изменение стоимости остатка |
| `change_source` | CharField; null=False; blank=False; editable=False; max_length=8 | Способ изменения; choices: manual → Вручную; auto → Автораспределение |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='supply_finalization_item_exact_product'>, <UniqueConstraint: fields=('finalization', 'cd') name='unique_supply_finalization_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('finalization', 'tech') name='unique_supply_finalization_tech' condition=(AND: ('tech__isnull', False))>, <CheckConstraint: condition=(AND: ('old_global_cost__gte', 0)) name='supply_finalization_old_cost_nonnegative'>, <CheckConstraint: condition=(AND: ('new_global_cost__gte', 0)) name='supply_finalization_new_cost_nonnegative'>]`; unique_together: `()`.

## `consignment.ConsignmentActionReceipt` — consignment action receipt

Одна проведённая операция на ключ запроса, включая повторную отправку POST.

Таблица `consignment_consignmentactionreceipt`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `key` | UUIDField; null=False; blank=False; editable=False; max_length=32 | key |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | created by → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | product kind |
| `stock_id` | PositiveIntegerField; null=False; blank=False; editable=True | stock id |
| `action` | CharField; null=False; blank=False; editable=True; max_length=8 | action |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `consignment.CDConsignmentStock` — остаток CD на реализации

CDConsignmentStock(id, lot_key, platform, warehouse, quantity, receivable_per_unit, unit_cost, cd)

Таблица `consignment_cdconsignmentstock`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `lot_key` | CharField; null=False; blank=True; editable=False; max_length=100 | Партия |
| `platform` | ForeignKey; null=False; blank=False; editable=True | Площадка → partners.SalesPlatform; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад-источник → warehouse.Warehouse; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `receivable_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=16; decimal_places=2 | Сумма к получению за единицу |
| `unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы партии |
| `cd` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: [('transfer_stock', 'Может передавать товар на реализацию'), ('return_stock', 'Может возвращать товар с реализации'), ('change_consignment_reward', 'Может изменять вознаграждение на реализации')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('platform', 'warehouse', 'cd', 'lot_key') name='unique_cd_platform_warehouse_lot'>, <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='cd_stock_quantity_nonnegative'>, <CheckConstraint: condition=(AND: ('receivable_per_unit__gte', 0)) name='cd_stock_receivable_nonnegative'>]`; unique_together: `()`.

## `consignment.TechConsignmentStock` — остаток техники на реализации

TechConsignmentStock(id, lot_key, platform, warehouse, quantity, receivable_per_unit, unit_cost, tech)

Таблица `consignment_techconsignmentstock`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `lot_key` | CharField; null=False; blank=True; editable=False; max_length=100 | Партия |
| `platform` | ForeignKey; null=False; blank=False; editable=True | Площадка → partners.SalesPlatform; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад-источник → warehouse.Warehouse; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `receivable_per_unit` | DecimalField; null=False; blank=False; editable=True; max_digits=16; decimal_places=2 | Сумма к получению за единицу |
| `unit_cost` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы партии |
| `tech` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('platform', 'warehouse', 'tech', 'lot_key') name='unique_tech_platform_warehouse_lot'>, <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='tech_stock_quantity_nonnegative'>, <CheckConstraint: condition=(AND: ('receivable_per_unit__gte', 0)) name='tech_stock_receivable_nonnegative'>]`; unique_together: `()`.

## `consignment.ConsignmentMovement` — операция реализации

Неизменяемый документ передачи на реализацию или возврата.

Таблица `consignment_consignmentmovement`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `operation_type` | CharField; null=False; blank=False; editable=False; max_length=16 | Операция; choices: transfer → Передача на реализацию; return → Возврат с реализации |
| `platform` | ForeignKey; null=False; blank=False; editable=False | Площадка → partners.SalesPlatform; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=False; blank=False; editable=False | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `created_by` | ForeignKey; null=False; blank=False; editable=False | Выполнил → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата и время |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `consignment.ConsignmentMovementItem` — позиция операции реализации

ConsignmentMovementItem(id, movement, product_kind, cd, tech, product_name_snapshot, product_sku_snapshot, quantity, receivable_per_unit, unit_cost_snapshot, warehouse_quantity_before, warehouse_quantity_after, consignment_quantity_before, consignment_quantity_after)

Таблица `consignment_consignmentmovementitem`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `movement` | ForeignKey; null=False; blank=False; editable=True | Операция → consignment.ConsignmentMovement; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | CD → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | Техника → catalog.Tech; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `product_sku_snapshot` | CharField; null=False; blank=False; editable=False; max_length=100 | Артикул |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=False | Количество |
| `receivable_per_unit` | DecimalField; null=False; blank=False; editable=False; max_digits=16; decimal_places=2 | Сумма к получению за единицу |
| `unit_cost_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы |
| `warehouse_quantity_before` | PositiveIntegerField; null=False; blank=False; editable=False | Остаток склада до |
| `warehouse_quantity_after` | PositiveIntegerField; null=False; blank=False; editable=False | Остаток склада после |
| `consignment_quantity_before` | PositiveIntegerField; null=False; blank=False; editable=False | На реализации до |
| `consignment_quantity_after` | PositiveIntegerField; null=False; blank=False; editable=False | На реализации после |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='consignment_movement_item_quantity_positive'>, <CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='consignment_movement_item_exact_product'>, <UniqueConstraint: fields=('movement', 'cd') name='unique_consignment_movement_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('movement', 'tech') name='unique_consignment_movement_tech' condition=(AND: ('tech__isnull', False))>]`; unique_together: `()`.

## `pricing.SupplierCDPrice` — текущая цена поставщика на CD

Текущее AED-предложение поставщика на диск; не историческая закупочная партия.

Таблица `pricing_suppliercdprice`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | Поставщик → partners.Supplier; on_delete=PROTECT |
| `price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Текущая цена |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлена |
| `cd` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: [('view_pricing', 'Может просматривать ценообразование'), ('view_supplier_prices', 'Может просматривать текущие цены поставщиков'), ('change_supplier_prices', 'Может изменять текущие цены поставщиков'), ('change_retail_price', 'Может изменять цены Avito'), ('change_wholesale_price', 'Может изменять оптовые цены'), ('change_yandex_market_price', 'Может изменять цены Яндекс Маркет')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('supplier', 'cd') name='unique_supplier_cd_price'>, <CheckConstraint: condition=(AND: ('price__gte', 0)) name='supplier_cd_price_nonnegative'>]`; unique_together: `()`.

## `pricing.SupplierTechPrice` — текущая цена поставщика на технику

Текущее AED-предложение поставщика на технику.

Таблица `pricing_suppliertechprice`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | Поставщик → partners.Supplier; on_delete=PROTECT |
| `price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Текущая цена |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлена |
| `tech` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('supplier', 'tech') name='unique_supplier_tech_price'>, <CheckConstraint: condition=(AND: ('price__gte', 0)) name='supplier_tech_price_nonnegative'>]`; unique_together: `()`.

## `sales.PrintAgent` — print agent

PrintAgent(id, name, printer_name, token_hash, enabled, session, last_seen_at, printer_available, version, last_error, incident, incident_started_at)

Таблица `sales_printagent`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | UUIDField; null=False; blank=False; editable=False; max_length=32 | id |
| `name` | CharField; null=False; blank=False; editable=True; max_length=120 | name |
| `printer_name` | CharField; null=False; blank=False; editable=True; max_length=200 | printer name |
| `token_hash` | CharField; null=False; blank=False; editable=False; max_length=64 | token hash |
| `enabled` | BooleanField; null=False; blank=False; editable=True | enabled |
| `session` | UUIDField; null=True; blank=False; editable=False; max_length=32 | session |
| `last_seen_at` | DateTimeField; null=True; blank=False; editable=False | last seen at |
| `printer_available` | BooleanField; null=True; blank=False; editable=False | printer available |
| `version` | CharField; null=False; blank=True; editable=False; max_length=32 | version |
| `last_error` | CharField; null=False; blank=True; editable=False; max_length=200 | last error |
| `incident` | UUIDField; null=True; blank=False; editable=False; max_length=32 | incident |
| `incident_started_at` | DateTimeField; null=True; blank=False; editable=False | incident started at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `sales.Sale` — продажа

Продажа со снимками строк и независимыми статусами сборки/оплаты/отмены.

Таблица `sales_sale`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `direct_delivery` | BooleanField; null=False; blank=False; editable=False | Прямая отгрузка по заказу рейса |
| `procurement_prepaid_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Ранее оплачено по закупочному заказу |
| `consignment_report_id` | UUIDField; null=True; blank=True; editable=False; max_length=32 | Отчёт площадки |
| `operation_kind` | CharField; null=False; blank=False; editable=False; max_length=24 | Вид операции; choices: normal → Обычная продажа; DIGITAL_PRODUCT → Цифровой товар; EXPENSE → Расход |
| `creation_key` | UUIDField; null=True; blank=True; editable=False; max_length=32 | Ключ создания |
| `creation_fingerprint` | CharField; null=False; blank=True; editable=False; max_length=64 | creation fingerprint |
| `visible_id` | CharField; null=False; blank=False; editable=False; max_length=40 | Номер продажи |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `consignment_platform` | ForeignKey; null=True; blank=True; editable=False | Площадка реализации → partners.SalesPlatform; on_delete=PROTECT |
| `price_type` | CharField; null=False; blank=False; editable=True; max_length=24 | Тип цены; choices: retail → Цена Avito; wholesale → Оптовая; yandex_market → Яндекс Маркет; consignment → Реализация |
| `sale_type` | CharField; null=False; blank=False; editable=True; max_length=24 | Тип продажи; choices: retail → Розница; wholesale → Опт; avito → Авито; yandex_market → Яндексмаркет; consignment → Реализация |
| `payment_method` | CharField; null=False; blank=False; editable=True; max_length=24 | Способ оплаты; choices: undefined → Не определён; cash → Наличные; cash_postpay → Наличные — постоплата; bank_account → Банковский перевод; bank_transfer_postpay → Банковский перевод — постоплата; partner_debt → В долг |
| `order_status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус заказа; choices: created → Создан; assembled → Собран; delivered → Доставлен |
| `payment_status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус оплаты; choices: unpaid → Не оплачен; paid → Оплачен |
| `created_by` | ForeignKey; null=True; blank=True; editable=True | Создал → accounts.User; on_delete=PROTECT |
| `storefront_source` | CharField; null=False; blank=True; editable=True; max_length=32 | Источник |
| `wholesale_contact` | ForeignKey; null=True; blank=True; editable=True | Оптовый контакт → resource_storefront.WholesaleContact; on_delete=PROTECT |
| `partner` | ForeignKey; null=True; blank=True; editable=True | Заказчик → partners.Partner; on_delete=PROTECT |
| `partner_name_snapshot` | CharField; null=False; blank=True; editable=True; max_length=255 | Заказчик на момент продажи |
| `debt_repayment_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Погашение долга партнёра |
| `debt_offset_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Взаимозачёт долга GameBAT |
| `buyer_name_snapshot` | CharField; null=False; blank=True; editable=True; max_length=160 | Контактное имя на момент заказа |
| `buyer_phone_snapshot` | CharField; null=False; blank=True; editable=True; max_length=40 | Основной телефон на момент заказа |
| `buyer_address_snapshot` | TextField; null=False; blank=True; editable=True | Адрес на момент заказа |
| `buyer_extra_phone` | CharField; null=False; blank=True; editable=True; max_length=40 | Дополнительный телефон покупателя |
| `buyer_comment` | TextField; null=False; blank=True; editable=True | Комментарий покупателя |
| `buyer_contact_methods` | JSONField; null=False; blank=True; editable=True | Способы связи покупателя |
| `buyer_telegram` | CharField; null=False; blank=True; editable=True; max_length=80 | Telegram покупателя |
| `buyer_whatsapp` | CharField; null=False; blank=True; editable=True; max_length=40 | WhatsApp покупателя |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создана |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлена |
| `completed_at` | DateTimeField; null=True; blank=True; editable=False | Завершена |
| `paid_at` | DateTimeField; null=True; blank=True; editable=False | Оплата подтверждена |
| `paid_by` | ForeignKey; null=True; blank=True; editable=False | Подтвердил оплату → accounts.User; on_delete=PROTECT |
| `total_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Сумма |
| `cash_received_amount` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Получено от покупателя |
| `extra_cash_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Сумма сверх стоимости |
| `note` | TextField; null=False; blank=True; editable=True | Примечание |
| `cancelled_at` | DateTimeField; null=True; blank=True; editable=False | Отменена |
| `cancelled_by` | ForeignKey; null=True; blank=True; editable=False | Отменил → accounts.User; on_delete=PROTECT |
| `cancellation_comment` | TextField; null=False; blank=True; editable=False | Причина отмены |
| `refunded_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Возвращённая сумма |

Permissions: [('view_sales', 'Может просматривать незавершённые продажи'), ('view_completed_sales', 'Может просматривать завершённые продажи'), ('view_sale_detail', 'Может просматривать подробности продажи'), ('create_sale', 'Может создавать продажи'), ('edit_unpaid_postpay_sale', 'Может изменять неоплаченную продажу с постоплатой'), ('advance_order_status', 'Может менять статус заказа'), ('mark_sale_paid', 'Может подтверждать оплату продажи'), ('import_wholesale_price', 'Может импортировать оптовый XLSX в новую продажу'), ('cancel_sale', 'Может отменять продажи'), ('view_sales_statistics', 'Может просматривать статистику продаж и прибыль'), ('export_sales_statistics', 'Может экспортировать статистику продаж')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (NOT (AND: ('direct_delivery', True))), (AND: ('operation_kind', 'normal'), ('sale_type', 'wholesale'))) name='sale_direct_delivery_wholesale'>, <CheckConstraint: condition=(AND: ('procurement_prepaid_amount__gte', 0)) name='sale_procurement_prepaid_nonnegative'>, <CheckConstraint: condition=(OR: (NOT (AND: ('operation_kind', 'EXPENSE'))), (AND: ('extra_cash_amount', 0), ('total_amount', 0), (OR: ('cash_received_amount__isnull', True), ('cash_received_amount', 0)))) name='expense_sale_no_revenue'>, <CheckConstraint: condition=(OR: (NOT (AND: ('payment_method', 'undefined'))), ('payment_status', 'unpaid')) name='sale_undefined_payment_unpaid'>, <CheckConstraint: condition=(AND: ('total_amount__gte', 0)) name='sale_total_nonnegative'>, <CheckConstraint: condition=(AND: ('refunded_amount__gte', 0)) name='sale_refund_nonnegative'>, <CheckConstraint: condition=(OR: (AND: ('cash_received_amount__isnull', True), ('refunded_amount__lte', F(total_amount))), (AND: ('cash_received_amount__isnull', False), ('refunded_amount__lte', F(cash_received_amount)))) name='sale_refund_not_above_received'>, <CheckConstraint: condition=(OR: ('cash_received_amount__isnull', True), ('cash_received_amount__gte', F(total_amount)), ('payment_method', 'partner_debt'), (AND: ('cash_received_amount__gte', 0), ('debt_repayment_amount', 0), ('extra_cash_amount', 0), ('operation_kind__in', ('normal', 'DIGITAL_PRODUCT')), ('partner__isnull', False), ('payment_status', 'paid'), ('sale_type', 'wholesale'), ('cash_received_amount__lte', <CombinedExpression: F(total_amount) - F(debt_offset_amount)>))) name='sale_cash_received_not_below_total'>, <CheckConstraint: condition=(AND: ('extra_cash_amount__gte', 0)) name='sale_extra_cash_nonnegative'>, <CheckConstraint: condition=(AND: ('debt_offset_amount__gte', 0), ('debt_repayment_amount__gte', 0), (NOT (AND: ('debt_offset_amount__gt', 0), ('debt_repayment_amount__gt', 0)))) name='sale_debt_amounts_valid'>, <CheckConstraint: condition=(OR: (AND: ('debt_offset_amount', 0), ('debt_repayment_amount', 0)), (AND: ('operation_kind__in', ('normal', 'DIGITAL_PRODUCT')), ('partner__isnull', False), ('payment_status', 'paid'), ('sale_type', 'wholesale'))) name='sale_debt_requires_paid_partner'>, <CheckConstraint: condition=(OR: (AND: ('debt_offset_amount', 0), ('debt_repayment_amount', 0)), ('cash_received_amount', <CombinedExpression: F(total_amount) + F(debt_repayment_amount) + F(extra_cash_amount) - F(debt_offset_amount)>), (AND: ('cash_received_amount__gte', 0), ('debt_repayment_amount', 0), ('extra_cash_amount', 0), ('cash_received_amount__lte', <CombinedExpression: F(total_amount) - F(debt_offset_amount)>))) name='sale_partner_payment_reconciles'>, <CheckConstraint: condition=(OR: (NOT (AND: ('payment_method', 'partner_debt'))), (AND: ('cash_received_amount', 0), ('cash_received_amount__isnull', False), ('debt_offset_amount', 0), ('debt_repayment_amount', 0), ('extra_cash_amount', 0), ('operation_kind__in', ('normal', 'DIGITAL_PRODUCT')), ('partner__isnull', False), ('payment_status', 'paid'), ('sale_type', 'wholesale'), ('total_amount__gt', 0))) name='sale_partner_debt_valid'>, <CheckConstraint: condition=(OR: (NOT (AND: ('payment_method', 'undefined'))), (AND: ('cash_received_amount__isnull', True), ('extra_cash_amount', 0))) name='sale_undefined_has_no_received'>, <CheckConstraint: condition=(OR: (AND: ('cancellation_comment', ''), ('cancelled_at__isnull', True), ('cancelled_by__isnull', True), ('refunded_amount', 0)), (AND: ('cancelled_at__isnull', False), ('cancelled_by__isnull', False), (NOT (AND: ('cancellation_comment', ''))))) name='sale_cancellation_fields_consistent'>]`; unique_together: `()`.

## `sales.SaleCDItem` — позиция CD в продаже

Историческая строка продажи диска: цена, скидка, комиссия, себестоимость и источник.

Таблица `sales_salecditem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `is_direct_delivery` | BooleanField; null=False; blank=False; editable=False | Товар прямой поставки |
| `trip_cost_row` | ForeignKey; null=True; blank=True; editable=False | trip cost row → orders.TripCostRow; on_delete=PROTECT |
| `trip_cost_slot` | PositiveSmallIntegerField; null=False; blank=False; editable=False | trip cost slot |
| `note` | TextField; null=False; blank=True; editable=True | Примечание к строке |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Цена единицы |
| `unit_discount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Скидка на единицу |
| `line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма строки |
| `avito_commission_enabled` | BooleanField; null=False; blank=False; editable=False | Учитывать комиссию Avito 0,5% |
| `avito_commission_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Комиссия Avito |
| `unit_cost_snapshot` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы на момент продажи |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=True; max_length=100 | Артикул |
| `sale` | ForeignKey; null=False; blank=False; editable=True | Продажа → sales.Sale; on_delete=PROTECT |
| `cd` | ForeignKey; null=False; blank=False; editable=True | CD → catalog.CD; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='sale_cd_quantity_positive'>, <CheckConstraint: condition=(AND: ('unit_price__gte', 0)) name='sale_cd_price_nonnegative'>, <CheckConstraint: condition=(AND: ('unit_discount__lte', F(unit_price))) name='sale_cd_discount_valid'>, <CheckConstraint: condition=(AND: ('line_total__gte', 0)) name='sale_cd_total_nonnegative'>, <CheckConstraint: condition=(OR: (AND: ('avito_commission_amount', 0), ('avito_commission_enabled', False)), (AND: ('avito_commission_amount__gte', 1), ('avito_commission_enabled', True))) name='sale_cd_avito_commission_consistent'>]`; unique_together: `()`.

## `sales.SaleTechItem` — позиция техники в продаже

Историческая строка продажи техники; текущая cost карточки её не пересчитывает.

Таблица `sales_saletechitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `is_direct_delivery` | BooleanField; null=False; blank=False; editable=False | Товар прямой поставки |
| `trip_cost_row` | ForeignKey; null=True; blank=True; editable=False | trip cost row → orders.TripCostRow; on_delete=PROTECT |
| `trip_cost_slot` | PositiveSmallIntegerField; null=False; blank=False; editable=False | trip cost slot |
| `note` | TextField; null=False; blank=True; editable=True | Примечание к строке |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Цена единицы |
| `unit_discount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Скидка на единицу |
| `line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма строки |
| `avito_commission_enabled` | BooleanField; null=False; blank=False; editable=False | Учитывать комиссию Avito 0,5% |
| `avito_commission_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Комиссия Avito |
| `unit_cost_snapshot` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы на момент продажи |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=True; max_length=100 | Артикул |
| `sale` | ForeignKey; null=False; blank=False; editable=True | Продажа → sales.Sale; on_delete=PROTECT |
| `tech` | ForeignKey; null=False; blank=False; editable=True | Техника → catalog.Tech; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='sale_tech_quantity_positive'>, <CheckConstraint: condition=(AND: ('unit_price__gte', 0)) name='sale_tech_price_nonnegative'>, <CheckConstraint: condition=(AND: ('unit_discount__lte', F(unit_price))) name='sale_tech_discount_valid'>, <CheckConstraint: condition=(AND: ('line_total__gte', 0)) name='sale_tech_total_nonnegative'>, <CheckConstraint: condition=(OR: (AND: ('avito_commission_amount', 0), ('avito_commission_enabled', False)), (AND: ('avito_commission_amount__gte', 1), ('avito_commission_enabled', True))) name='sale_tech_avito_commission_consistent'>]`; unique_together: `()`.

## `sales.SaleCustomItem` — произвольная позиция продажи

Историческая строка продажи без связи с номенклатурой и складом.

Таблица `sales_salecustomitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `is_direct_delivery` | BooleanField; null=False; blank=False; editable=False | Товар прямой поставки |
| `trip_cost_row` | ForeignKey; null=True; blank=True; editable=False | trip cost row → orders.TripCostRow; on_delete=PROTECT |
| `trip_cost_slot` | PositiveSmallIntegerField; null=False; blank=False; editable=False | trip cost slot |
| `note` | TextField; null=False; blank=True; editable=True | Примечание к строке |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Цена единицы |
| `unit_discount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Скидка на единицу |
| `line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма строки |
| `avito_commission_enabled` | BooleanField; null=False; blank=False; editable=False | Учитывать комиссию Avito 0,5% |
| `avito_commission_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Комиссия Avito |
| `unit_cost_snapshot` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы на момент продажи |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `sale` | ForeignKey; null=False; blank=False; editable=True | Продажа → sales.Sale; on_delete=PROTECT |
| `article_snapshot` | CharField; null=False; blank=True; editable=True; max_length=100 | Артикул |
| `system_product` | ForeignKey; null=True; blank=True; editable=False | system product → catalog.SystemProduct; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (NOT (AND: ('system_product_id', 'EXPENSE'))), (AND: ('avito_commission_amount', 0), ('avito_commission_enabled', False), ('line_total', 0), ('unit_discount', 0), ('unit_price', 0))) name='expense_item_no_revenue'>, <CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='sale_custom_quantity_positive'>, <CheckConstraint: condition=(AND: ('unit_price__gte', 0)) name='sale_custom_price_nonnegative'>, <CheckConstraint: condition=(AND: ('unit_discount__lte', F(unit_price))) name='sale_custom_discount_valid'>, <CheckConstraint: condition=(AND: ('line_total__gte', 0)) name='sale_custom_total_nonnegative'>, <CheckConstraint: condition=(OR: (AND: ('avito_commission_amount', 0), ('avito_commission_enabled', False)), (AND: ('avito_commission_amount__gte', 1), ('avito_commission_enabled', True))) name='sale_custom_avito_commission_consistent'>, <CheckConstraint: condition=(AND: ('unit_cost_snapshot__gte', 0), ('unit_cost_snapshot__isnull', False)) name='sale_custom_cost_nonnegative'>, <CheckConstraint: condition=(NOT (AND: ('product_name_snapshot', ''))) name='sale_custom_name_nonempty'>]`; unique_together: `()`.

## `sales.SaleConsignmentItem` — позиция реализации в продаже

Неизменяемый снимок партии реализации, проданной в составе обычной продажи.

Таблица `sales_saleconsignmentitem`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `sale` | ForeignKey; null=False; blank=False; editable=True | Продажа → sales.Sale; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=PROTECT |
| `platform` | ForeignKey; null=False; blank=False; editable=True | Площадка → partners.SalesPlatform; on_delete=PROTECT |
| `source_stock_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | ID партии реализации |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `unit_price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Вознаграждение за единицу |
| `line_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма строки |
| `unit_cost_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Себестоимость единицы на момент продажи |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=True; max_length=100 | Артикул |
| `platform_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Площадка |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='sale_consignment_exact_product'>, <CheckConstraint: condition=(AND: ('quantity__gt', 0)) name='sale_consignment_qty_positive'>, <CheckConstraint: condition=(AND: ('unit_price__gte', 0)) name='sale_consignment_price_nonnegative'>, <CheckConstraint: condition=(AND: ('unit_cost_snapshot__gte', 0)) name='sale_consignment_cost_nonnegative'>, <UniqueConstraint: fields=('sale', 'product_kind', 'source_stock_id') name='unique_sale_consignment_stock'>]`; unique_together: `()`.

## `sales.MarketPicking` — market picking

MarketPicking(id, order, required, scanned, completed_at, updated_at)

Таблица `sales_marketpicking`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | OneToOneField; null=False; blank=False; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `required` | JSONField; null=False; blank=False; editable=True | required |
| `scanned` | JSONField; null=False; blank=False; editable=True | scanned |
| `completed_at` | DateTimeField; null=True; blank=True; editable=True | completed at |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `sales.MarketScanEvent` — market scan event

MarketScanEvent(id, request_id, actor, barcode, order, result, created_at)

Таблица `sales_marketscanevent`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `request_id` | UUIDField; null=False; blank=False; editable=True; max_length=32 | request id |
| `actor` | ForeignKey; null=False; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `barcode` | CharField; null=False; blank=False; editable=True; max_length=100 | barcode |
| `order` | ForeignKey; null=True; blank=False; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `result` | JSONField; null=False; blank=False; editable=True | result |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `sales.MarketPrintJob` — market print job

MarketPrintJob(id, request_id, order, actor, ready_after_print, state, document, refresh_job, boxes_job, ready_job, printer_name, print_backend, agent, agent_claim, agent_claimed_at, document_digest, printer_job_id, spooled_at, printed_at, last_error, lease, leased_at, created_at, updated_at)

Таблица `sales_marketprintjob`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `request_id` | UUIDField; null=False; blank=False; editable=True; max_length=32 | request id |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `ready_after_print` | BooleanField; null=False; blank=False; editable=True | ready after print |
| `state` | CharField; null=False; blank=False; editable=True; max_length=24 | state |
| `document` | ForeignKey; null=True; blank=False; editable=True | document → yandex_market.LabelDocument; on_delete=PROTECT |
| `refresh_job` | ForeignKey; null=True; blank=False; editable=True | refresh job → yandex_market.SyncJob; on_delete=PROTECT |
| `boxes_job` | ForeignKey; null=True; blank=False; editable=True | boxes job → yandex_market.SyncJob; on_delete=PROTECT |
| `ready_job` | ForeignKey; null=True; blank=False; editable=True | ready job → yandex_market.SyncJob; on_delete=PROTECT |
| `printer_name` | CharField; null=False; blank=False; editable=True; max_length=200 | printer name |
| `print_backend` | CharField; null=False; blank=False; editable=True; max_length=12 | print backend |
| `agent` | ForeignKey; null=True; blank=False; editable=False | agent → sales.PrintAgent; on_delete=PROTECT |
| `agent_claim` | UUIDField; null=True; blank=False; editable=False; max_length=32 | agent claim |
| `agent_claimed_at` | DateTimeField; null=True; blank=False; editable=False | agent claimed at |
| `document_digest` | CharField; null=False; blank=True; editable=False; max_length=64 | document digest |
| `printer_job_id` | PositiveIntegerField; null=True; blank=False; editable=True | printer job id |
| `spooled_at` | DateTimeField; null=True; blank=False; editable=True | spooled at |
| `printed_at` | DateTimeField; null=True; blank=False; editable=True | printed at |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `lease` | UUIDField; null=True; blank=False; editable=True; max_length=32 | lease |
| `leased_at` | DateTimeField; null=True; blank=False; editable=True | leased at |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('order',) name='one_market_automatic_print_per_order' condition=(AND: ('ready_after_print', True))>]`; unique_together: `()`.

## `sales.MarketOrderAttention` — внутреннее подтверждение заказа Маркета

Внутренняя отметка сотрудника; присутствует только у новых импортированных продаж.

Таблица `sales_marketorderattention`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | OneToOneField; null=False; blank=False; editable=True | Заказ Маркета → yandex_market.OrderMetadata; on_delete=PROTECT |
| `notification_started_at` | DateTimeField; null=False; blank=False; editable=False | Начало оповещений |
| `acknowledged_at` | DateTimeField; null=True; blank=True; editable=False | Принят сотрудником |
| `acknowledged_by` | ForeignKey; null=True; blank=True; editable=False | acknowledged by → accounts.User; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('acknowledged_at__isnull', True), ('acknowledged_by__isnull', True)), (AND: ('acknowledged_at__isnull', False), ('acknowledged_by__isnull', False))) name='market_attention_ack_complete'>]`; unique_together: `()`.

## `sales.AvitoBrowserOrder` — avito browser order

AvitoBrowserOrder(id, external_id, titles, carrier, displayed_amount, sale, creation_key, created_by, created_at)

Таблица `sales_avitobrowserorder`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `external_id` | CharField; null=False; blank=False; editable=True; max_length=64 | external id |
| `titles` | JSONField; null=False; blank=False; editable=True | titles |
| `carrier` | CharField; null=False; blank=True; editable=True; max_length=100 | carrier |
| `displayed_amount` | DecimalField; null=True; blank=False; editable=True; max_digits=20; decimal_places=2 | displayed amount |
| `sale` | OneToOneField; null=True; blank=False; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `creation_key` | UUIDField; null=False; blank=False; editable=False; max_length=32 | creation key |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | created by → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `sales.AvitoShippingPrintJob` — avito shipping print job

AvitoShippingPrintJob(id, request_id, order, actor, file, document_digest, state, print_backend, printer_name, agent, agent_claim, agent_claimed_at, printer_job_id, spooled_at, printed_at, last_error, created_at, updated_at)

Таблица `sales_avitoshippingprintjob`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `request_id` | UUIDField; null=False; blank=False; editable=True; max_length=32 | request id |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → sales.AvitoBrowserOrder; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `file` | FileField; null=False; blank=False; editable=True; max_length=100 | file |
| `document_digest` | CharField; null=False; blank=False; editable=True; max_length=64 | document digest |
| `state` | CharField; null=False; blank=False; editable=True; max_length=24 | state |
| `print_backend` | CharField; null=False; blank=False; editable=True; max_length=12 | print backend |
| `printer_name` | CharField; null=False; blank=False; editable=True; max_length=200 | printer name |
| `agent` | ForeignKey; null=True; blank=False; editable=True | agent → sales.PrintAgent; on_delete=PROTECT |
| `agent_claim` | UUIDField; null=True; blank=False; editable=True; max_length=32 | agent claim |
| `agent_claimed_at` | DateTimeField; null=True; blank=False; editable=True | agent claimed at |
| `printer_job_id` | PositiveIntegerField; null=True; blank=False; editable=True | printer job id |
| `spooled_at` | DateTimeField; null=True; blank=False; editable=True | spooled at |
| `printed_at` | DateTimeField; null=True; blank=False; editable=True | printed at |
| `last_error` | CharField; null=False; blank=True; editable=True; max_length=200 | last error |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `cash.CashRegister` — касса

Наличная касса конкретного склада, сверяемая с журналом.

Таблица `cash_cashregister`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `warehouse` | OneToOneField; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `balance` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Остаток наличных |

Permissions: [('view_cash_register', 'Может просматривать остаток кассы'), ('view_cash_history', 'Может просматривать историю кассы'), ('deposit_cash', 'Может вносить наличные'), ('collect_cash', 'Может инкассировать наличные')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('balance__gte', 0)) name='cash_register_balance_nonnegative'>]`; unique_together: `()`.

## `cash.Safe` — сейф

Наличный сейф конкретного склада с отдельным балансом.

Таблица `cash_safe`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `warehouse` | OneToOneField; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `balance` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Остаток наличных |

Permissions: [('deposit_safe', 'Может вносить наличные в сейф'), ('collect_safe', 'Может инкассировать наличные из сейфа'), ('transfer_cash_to_safe', 'Может переводить наличные из кассы в сейф'), ('transfer_safe_to_cash', 'Может переводить наличные из сейфа в кассу')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('balance__gte', 0)) name='safe_balance_nonnegative'>]`; unique_together: `()`.

## `cash.CashTransaction` — кассовая операция

Журнальная проводка кассы/сейфа; банк и безденежный долг сюда не попадают.

Таблица `cash_cashtransaction`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `cash_register` | ForeignKey; null=False; blank=False; editable=True | Касса → cash.CashRegister; on_delete=PROTECT |
| `safe` | ForeignKey; null=True; blank=True; editable=False | Сейф → cash.Safe; on_delete=PROTECT |
| `operation_type` | CharField; null=False; blank=False; editable=True; max_length=24 | Операция; choices: deposit → Внесение наличных; collection → Инкассация; sale_payment → Оплата продажи; sale_refund → Возврат по отменённой продаже; safe_deposit → Внесение в сейф; safe_collection → Инкассация из сейфа; cash_to_safe → Перевод: касса → сейф; safe_to_cash → Перевод: сейф → касса; order_prepayment → Предоплата закупочного заказа; order_refund → Возврат по закупочному заказу; order_postpayment → Постоплата закупочного заказа; creditor_advance → Кредитор: увеличение задолженности; creditor_repayment → Кредитор: погашение задолженности |
| `amount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма |
| `comment` | TextField; null=False; blank=False; editable=True | Комментарий |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | Провёл → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Проведена |
| `sale` | ForeignKey; null=True; blank=True; editable=False | Продажа → sales.Sale; on_delete=PROTECT |
| `operation_key` | UUIDField; null=True; blank=True; editable=False; max_length=32 | Ключ операции |
| `customer_order` | ForeignKey; null=True; blank=True; editable=False | Закупочный заказ → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `order_adjustment` | OneToOneField; null=True; blank=True; editable=False | Корректировка заказа → orders.OrderAdjustment; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('amount__gt', 0)) name='cash_transaction_amount_positive'>, <CheckConstraint: condition=(OR: (AND: ('operation_type__in', ('deposit', 'collection', 'sale_payment', 'sale_refund')), ('safe__isnull', True)), (AND: ('operation_type__in', ('safe_deposit', 'safe_collection', 'cash_to_safe', 'safe_to_cash')), ('safe__isnull', False)), (AND: ('customer_order__isnull', False), ('operation_type__in', ('order_prepayment', 'order_refund', 'order_postpayment')), ('safe__isnull', True)), ('operation_type__in', ('creditor_advance', 'creditor_repayment'))) name='cash_transaction_safe_matches_type'>, <UniqueConstraint: fields=('customer_order',) name='unique_customer_order_prepayment' condition=(AND: ('operation_type', 'order_prepayment'))>, <UniqueConstraint: fields=('customer_order',) name='unique_customer_order_postpayment' condition=(AND: ('operation_type', 'order_postpayment'))>, <UniqueConstraint: fields=('sale', 'operation_type') name='unique_sale_cash_operation_type' condition=(AND: ('operation_type__in', ('sale_payment', 'sale_refund')), ('sale__isnull', False))>, <CheckConstraint: condition=(OR: (AND: ('operation_type__in', ('sale_payment', 'sale_refund')), ('sale__isnull', False)), (AND: (NOT (AND: ('operation_type__in', ('sale_payment', 'sale_refund')))), ('sale__isnull', True))) name='sale_cash_operation_has_sale'>, <CheckConstraint: condition=(OR: (AND: ('operation_type', 'order_refund'), ('order_adjustment__isnull', False)), (AND: (NOT (AND: ('operation_type', 'order_refund'))), ('order_adjustment__isnull', True))) name='order_refund_has_adjustment'>]`; unique_together: `()`.

## `creditors.Creditor` — кредитор

Финансовая карточка; у связанного Partner знак задаёт направление долга.

Таблица `creditors_creditor`; порядок `('name', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название |
| `current_debt` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Текущая задолженность |
| `description` | TextField; null=False; blank=True; editable=True | Описание |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |

Permissions: [('view_creditors', 'Может просматривать кредиторов'), ('change_debt', 'Может изменять задолженность кредиторов'), ('view_history', 'Может просматривать историю кредиторов')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `creditors.CreditorTransaction` — операция кредитора

История дельт задолженности и сторно, отделённая от кассовой проводки.

Таблица `creditors_creditortransaction`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `kind` | CharField; null=False; blank=False; editable=True; max_length=20 | Тип операции; choices: adjustment → Изменение задолженности; repayment → Погашение долга партнёра; offset → Взаимозачёт долга GameBAT; sale_debt → Продажа партнёру в долг; reversal → Отмена расчёта по продаже |
| `partner_name_snapshot` | CharField; null=False; blank=True; editable=True; max_length=255 | Партнёр на момент операции |
| `sale` | ForeignKey; null=True; blank=True; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `operation_key` | CharField; null=True; blank=True; editable=False; max_length=80 | operation key |
| `reversal_of` | OneToOneField; null=True; blank=True; editable=True | reversal of → creditors.CreditorTransaction; on_delete=PROTECT |
| `creditor` | ForeignKey; null=False; blank=False; editable=True | Кредитор → creditors.Creditor; on_delete=PROTECT |
| `old_debt` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Задолженность до |
| `new_debt` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Задолженность после |
| `delta` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Изменение задолженности |
| `warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад → warehouse.Warehouse; on_delete=PROTECT |
| `money_source_type` | CharField; null=False; blank=False; editable=True; max_length=8 | Денежное хранилище; choices: cash → Касса; safe → Сейф; bank → Банковский перевод; offset → Без движения денег |
| `amount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сумма операции |
| `cash_transaction` | OneToOneField; null=True; blank=True; editable=False | Запись денежного журнала → cash.CashTransaction; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | Провёл → accounts.User; on_delete=PROTECT |
| `comment` | TextField; null=False; blank=True; editable=True | Комментарий |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Проведена |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('amount__gt', 0)) name='creditor_tx_amount_positive'>, <CheckConstraint: condition=(NOT (AND: ('delta', 0))) name='creditor_tx_delta_nonzero'>, <CheckConstraint: condition=(AND: ('delta', Round(F(new_debt) - F(old_debt), Value(2)))) name='creditor_tx_delta_matches_balances'>, <CheckConstraint: condition=(OR: ('delta', F(amount)), ('delta', <CombinedExpression: F(amount) * Value(-1)>)) name='creditor_tx_amount_matches_delta'>, <CheckConstraint: condition=(OR: (AND: ('cash_transaction__isnull', True), ('money_source_type__in', ('bank', 'offset'))), (AND: ('cash_transaction__isnull', False), ('money_source_type__in', ('cash', 'safe')))) name='creditor_tx_money_source_consistent'>]`; unique_together: `()`.

## `price.PriceDocumentSettings` — настройки документов прайса

Настройки оформления выдаваемых прайсов, а не складской учёт.

Таблица `price_pricedocumentsettings`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `company_name` | CharField; null=False; blank=False; editable=True; max_length=255 | Название компании |
| `address` | CharField; null=False; blank=True; editable=True; max_length=500 | Адрес |
| `phone_1` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №1 |
| `phone_2` | CharField; null=False; blank=True; editable=True; max_length=40 | Телефон №2 |
| `email` | CharField; null=False; blank=True; editable=True; max_length=254 | Email |
| `website` | CharField; null=False; blank=True; editable=True; max_length=200 | Сайт |
| `telegram` | CharField; null=False; blank=True; editable=True; max_length=100 | Telegram |
| `logo` | FileField; null=False; blank=True; editable=True; max_length=100 | Логотип |
| `additional_text` | TextField; null=False; blank=True; editable=True | Дополнительный текст |

Permissions: [('view_price_page', 'Прайс: просмотр раздела'), ('change_document_settings', 'Прайс: изменение данных документов'), ('generate_retail_price', 'Прайс: создание розничного файла'), ('generate_wholesale_price', 'Прайс: создание оптового файла'), ('download_supplier_template', 'Прайс: скачивание шаблона поставщика'), ('upload_supplier_price', 'Прайс: загрузка цен поставщика'), ('view_supplier_prices', 'Прайс: просмотр цен поставщиков'), ('create_procurement_price_list', 'Прайс: создание закупочного прайса'), ('change_procurement_markup', 'Прайс: изменение наценки'), ('change_procurement_delivery', 'Прайс: изменение доставки'), ('export_procurement_price_list', 'Прайс: экспорт закупочного прайса')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `price.ProcurementPriceList` — закупочный прайс

Версия закупочного расчёта со снимками курсов/тарифов и предложений.

Таблица `price_procurementpricelist`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `is_trip_addition` | BooleanField; null=False; blank=False; editable=False | Расчёт дополнительной партии рейса |
| `supplier_offers_complete` | BooleanField; null=False; blank=False; editable=False | Сохранены все предложения поставщиков |
| `public_token` | UUIDField; null=False; blank=False; editable=False; max_length=32 | Публичный токен |
| `exchange_rate_usdt_aed` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=6 | Курс AED → USDT (AED за 1 USDT) |
| `exchange_rate_usdt_rub` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=6 | Курс USDT → RUB (RUB за 1 USDT) |
| `exchange_rate_aed_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Курс AED → RUB |
| `delivery_general_usdt_per_kg` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=6 | Прочая техника, USDT/кг |
| `delivery_devices_usdt_per_kg` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=6 | Консоли, мини-ПК и VR/AR, USDT/кг |
| `delivery_storage_usdt_per_kg` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=6 | Память и накопители, USDT/кг |
| `delivery_cd_rub` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Доставка одного диска, RUB |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | Создал → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `price.ProcurementPriceListItem` — позиция закупочного прайса

Снимок товара и его закупочных/покупательских условий внутри версии.

Таблица `price_procurementpricelistitem`; порядок `('product_name_snapshot', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `price_list` | ForeignKey; null=False; blank=False; editable=True | Прайс → price.ProcurementPriceList; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | CD → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | Техника → catalog.Tech; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=False; max_length=100 | Артикул |
| `selected_supplier` | ForeignKey; null=False; blank=False; editable=False | Выбранный поставщик → partners.Supplier; on_delete=PROTECT |
| `supplier_price_aed` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Цена поставщика, AED |
| `exchange_rate_aed_rub` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Курс AED → RUB |
| `base_price_rub` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | База, RUB |
| `markup_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Наценка, RUB |
| `original_markup_rub` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Наценка до округления, RUB |
| `prepayment_rounding_extra_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Округление предоплаты, RUB |
| `postpayment_rounding_extra_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Округление постоплаты, RUB |
| `delivery_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Доставка, RUB |
| `weight_grams_snapshot` | PositiveIntegerField; null=True; blank=True; editable=False | Вес при расчёте, г |
| `delivery_group_snapshot` | CharField; null=False; blank=True; editable=False; max_length=16 | Группа тарифа при расчёте; choices: general → Прочая техника; devices → Консоли, мини-ПК и VR/AR; storage → Память и накопители |
| `delivery_usdt_per_kg_snapshot` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=6 | Тариф при расчёте, USDT/кг |
| `prepayment_price_rub` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Цена предоплаты, RUB |
| `postpayment_price_rub` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Цена постоплаты, RUB |
| `postpayment_surcharge_rub` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Доплата за постоплату, RUB |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='procurement_price_item_exact_product'>, <UniqueConstraint: fields=('price_list', 'cd') name='unique_procurement_price_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('price_list', 'tech') name='unique_procurement_price_tech' condition=(AND: ('tech__isnull', False))>, <CheckConstraint: condition=(AND: ('base_price_rub__gte', 0)) name='proc_base_nonnegative'>, <CheckConstraint: condition=(AND: ('delivery_rub__gte', 0)) name='proc_delivery_nonnegative'>, <CheckConstraint: condition=(AND: ('prepayment_price_rub__gte', 0)) name='proc_prepayment_nonnegative'>, <CheckConstraint: condition=(AND: ('postpayment_price_rub__gte', 0)) name='proc_postpayment_nonnegative'>, <CheckConstraint: condition=(AND: ('postpayment_surcharge_rub__gte', 0)) name='proc_surcharge_nonnegative'>, <CheckConstraint: condition=(AND: ('prepayment_rounding_extra_rub__gte', 0), ('prepayment_rounding_extra_rub__lt', 10)) name='proc_prepayment_rounding_range'>, <CheckConstraint: condition=(AND: ('postpayment_rounding_extra_rub__gte', 0), ('postpayment_rounding_extra_rub__lt', 10)) name='proc_postpayment_rounding_range'>]`; unique_together: `()`.

## `price.ProcurementSupplierOffer` — procurement supplier offer

Цена поставщика на момент создания версии прайса, без последующего пересчёта.

Таблица `price_procurementsupplieroffer`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `price_list_item` | ForeignKey; null=False; blank=False; editable=True | price list item → price.ProcurementPriceListItem; on_delete=PROTECT |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | supplier → partners.Supplier; on_delete=PROTECT |
| `price_aed` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | price aed |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('price_list_item', 'supplier') name='unique_procurement_supplier_offer'>, <CheckConstraint: condition=(AND: ('price_aed__gt', 0)) name='procurement_supplier_offer_positive'>]`; unique_together: `()`.

## `price.ProcurementPricePreference` — сохранённая наценка закупочного прайса

Память пользовательской наценки/предпочтений товара для следующих версий.

Таблица `price_procurementpricepreference`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `cd` | OneToOneField; null=True; blank=True; editable=True | Диск → catalog.CD; on_delete=PROTECT |
| `tech` | OneToOneField; null=True; blank=True; editable=True | Техника → catalog.Tech; on_delete=PROTECT |
| `markup_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Сохранённая наценка, RUB |
| `postpayment_surcharge_rub` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Сохранённая доплата за постоплату, RUB |
| `source_item` | ForeignKey; null=True; blank=True; editable=True | Исходная строка прайса → price.ProcurementPriceListItem; on_delete=SET_NULL |
| `updated_by` | ForeignKey; null=False; blank=False; editable=True | Сохранил → accounts.User; on_delete=PROTECT |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Сохранена |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='proc_price_preference_exact_product'>, <CheckConstraint: condition=(AND: ('postpayment_surcharge_rub__gte', 0)) name='proc_pref_surcharge_nonnegative'>]`; unique_together: `()`.

## `orders.TripAdditionReceipt` — trip addition receipt

Идемпотентность добавления; финансовый учёт остаётся в штатных заказах.

Таблица `orders_tripadditionreceipt`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `key` | UUIDField; null=False; blank=False; editable=False; max_length=32 | key |
| `batch` | ForeignKey; null=False; blank=False; editable=True | batch → orders.SupplierOrderBatch; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `fingerprint` | CharField; null=False; blank=False; editable=True; max_length=64 | fingerprint |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `orders` | ManyToManyField; null=False; blank=False; editable=True | orders → orders.CustomerProcurementOrder |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `orders.TripOrderOperation` — trip order operation

История обычных операций заказа; курсы и расчёт фиксируются при создании.

Таблица `orders_triporderoperation`; порядок `('created_at', 'pk')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `sale` | OneToOneField; null=True; blank=True; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `supply` | OneToOneField; null=True; blank=True; editable=True | supply → supplies.Supply; on_delete=PROTECT |
| `active` | BooleanField; null=False; blank=False; editable=False | active |
| `usd_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Курс USD → RUB |
| `aed_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | Курс AED → RUB |
| `calculation` | JSONField; null=False; blank=False; editable=False | Снимок расчёта |
| `draft_key` | UUIDField; null=False; blank=False; editable=False; max_length=32 | draft key |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | created by → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('order',) name='one_active_trip_order_operation' condition=(AND: ('active', True))>, <CheckConstraint: condition=(OR: (AND: ('sale__isnull', False), ('supply__isnull', True)), (AND: ('sale__isnull', True), ('supply__isnull', False))) name='trip_operation_exactly_one_document'>, <CheckConstraint: condition=(AND: ('aed_rub__gt', 0), ('usd_rub__gt', 0)) name='trip_operation_positive_rates'>]`; unique_together: `()`.

## `orders.CustomerProcurementOrder` — клиентский закупочный заказ

Клиентский или складской закупочный заказ, который может входить в рейс.

Таблица `orders_customerprocurementorder`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `purpose` | CharField; null=False; blank=False; editable=False; max_length=12 | Назначение; choices: customer → Клиентский заказ; stock → Заказ на склад |
| `supply` | OneToOneField; null=True; blank=True; editable=False | Приход по заказу → supplies.Supply; on_delete=PROTECT |
| `trip` | ForeignKey; null=True; blank=True; editable=False | Рейс → orders.SupplierOrderBatch; on_delete=PROTECT |
| `recipient` | CharField; null=False; blank=False; editable=True; max_length=255 | Получатель |
| `partner` | ForeignKey; null=True; blank=True; editable=True | Заказчик → partners.Partner; on_delete=PROTECT |
| `partner_name_snapshot` | CharField; null=False; blank=True; editable=True; max_length=255 | Заказчик на момент заказа |
| `comment` | TextField; null=False; blank=True; editable=True | Комментарий |
| `price_list` | ForeignKey; null=False; blank=False; editable=False | Исходный закупочный прайс → price.ProcurementPriceList; on_delete=PROTECT |
| `status` | CharField; null=False; blank=False; editable=False; max_length=20 | Статус; choices: created → Создан; confirmed → Подтверждён; receiving → Принимается; completed → Выполнен |
| `payment_warehouse` | ForeignKey; null=True; blank=True; editable=False | Склад оплаты → warehouse.Warehouse; on_delete=PROTECT |
| `prepayment_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Предоплата |
| `postpayment_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Постоплата |
| `grand_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Итого |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | Создал → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |

Permissions: [('view_orders', 'Заказы: просмотр списка'), ('view_order_detail', 'Заказы: просмотр заказа'), ('create_order', 'Заказы: создание'), ('edit_created_order', 'Заказы: изменение созданного заказа'), ('confirm_order', 'Заказы: подтверждение и предоплата'), ('start_receiving', 'Заказы: начало приёмки'), ('edit_receiving_order', 'Заказы: корректировка при приёмке'), ('complete_order', 'Заказы: выполнение и постоплата'), ('view_order_adjustments', 'Заказы: просмотр корректировок')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('prepayment_total__gte', 0)) name='order_prepayment_nonnegative'>, <CheckConstraint: condition=(AND: ('postpayment_total__gte', 0)) name='order_postpayment_nonnegative'>, <CheckConstraint: condition=(AND: ('grand_total__gte', 0)) name='order_grand_total_nonnegative'>]`; unique_together: `()`.

## `orders.CustomerProcurementOrderItem` — позиция клиентского закупочного заказа

Количество и ценовые части товара в сохранённом заказе.

Таблица `orders_customerprocurementorderitem`; порядок `('product_name_snapshot', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | tech → catalog.Tech; on_delete=PROTECT |
| `order` | ForeignKey; null=False; blank=False; editable=True | Заказ → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `price_list_item` | ForeignKey; null=False; blank=False; editable=False | Позиция исходного прайса → price.ProcurementPriceListItem; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=False; max_length=100 | Артикул |
| `selected_supplier` | ForeignKey; null=False; blank=False; editable=False | Выбранный поставщик → partners.Supplier; on_delete=PROTECT |
| `supplier_price_aed_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Цена поставщика, AED |
| `prepayment_unit_price` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Цена предоплаты |
| `postpayment_unit_price` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Цена постоплаты |
| `prepayment_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество по предоплате |
| `postpayment_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество по постоплате |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='customer_order_item_exact_product'>, <UniqueConstraint: fields=('order', 'price_list_item') name='unique_order_price_list_item'>]`; unique_together: `()`.

## `orders.CustomerOrderStatusEvent` — смена статуса закупочного заказа

След перехода статуса закупочного заказа.

Таблица `orders_customerorderstatusevent`; порядок `('created_at', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | ForeignKey; null=False; blank=False; editable=True | Заказ → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | Пользователь → accounts.User; on_delete=PROTECT |
| `old_status` | CharField; null=False; blank=False; editable=True; max_length=20 | Предыдущий статус; choices: created → Создан; confirmed → Подтверждён; receiving → Принимается; completed → Выполнен |
| `new_status` | CharField; null=False; blank=False; editable=True; max_length=20 | Новый статус; choices: created → Создан; confirmed → Подтверждён; receiving → Принимается; completed → Выполнен |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `orders.OrderAdjustment` — корректировка закупочного заказа

Документ согласованной корректировки заказа и денежной разницы.

Таблица `orders_orderadjustment`; порядок `('created_at', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | ForeignKey; null=False; blank=False; editable=True | Заказ → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | Пользователь → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата |
| `comment` | TextField; null=False; blank=False; editable=True | Комментарий |
| `refund_amount` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | Сумма возврата |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `orders.OrderAdjustmentChange` — изменение в корректировке заказа

Снимок изменения одной позиции корректировки заказа.

Таблица `orders_orderadjustmentchange`; порядок `('id',)`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `adjustment` | ForeignKey; null=False; blank=False; editable=True | Корректировка → orders.OrderAdjustment; on_delete=PROTECT |
| `product_kind` | CharField; null=False; blank=False; editable=True; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `product_id_snapshot` | PositiveBigIntegerField; null=False; blank=False; editable=True | ID товара |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=True; max_length=255 | Название товара |
| `field_name` | CharField; null=False; blank=False; editable=True; max_length=40 | Поле |
| `old_value` | PositiveIntegerField; null=False; blank=False; editable=True | Было |
| `new_value` | PositiveIntegerField; null=False; blank=False; editable=True | Стало |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `orders.SupplierOrderBatch` — подборка заказов поставщикам

Рейс или историческая подборка поставщикам; различать через is_trip/trips().

Таблица `orders_supplierorderbatch`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `price_list` | ForeignKey; null=True; blank=True; editable=False | Общий прайс → price.ProcurementPriceList; on_delete=PROTECT |
| `name` | CharField; null=False; blank=True; editable=True; max_length=255 | Название рейса |
| `revision` | PositiveIntegerField; null=False; blank=False; editable=False | Версия изменений |
| `creation_key` | UUIDField; null=True; blank=True; editable=False; max_length=32 | creation key |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | Создал → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `source_orders` | ManyToManyField; null=False; blank=False; editable=True | Исходные заказы → orders.CustomerProcurementOrder |

Permissions: [('generate_supplier_orders', 'Заказы: формирование заказов поставщикам')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `orders.SupplierTripInvoice` — отметка инвойса в рейсе

Сохранённая отметка интерфейса рейса, без влияния на учётные сервисы.

Таблица `orders_suppliertripinvoice`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `batch` | ForeignKey; null=False; blank=False; editable=True | batch → orders.SupplierOrderBatch; on_delete=CASCADE |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | supplier → partners.Supplier; on_delete=CASCADE |
| `accepted` | BooleanField; null=False; blank=False; editable=True | Инвойс принят |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |
| `updated_by` | ForeignKey; null=True; blank=False; editable=False | updated by → accounts.User; on_delete=SET_NULL |

Permissions: []. Стандартные: ().

Ограничения: `[<UniqueConstraint: fields=('batch', 'supplier') name='unique_trip_supplier_invoice'>]`; unique_together: `()`.

## `orders.SupplierOrderBatchLine` — строка заказа поставщику

Закупочная ценовая партия поставщика внутри рейса.

Таблица `orders_supplierorderbatchline`; порядок `('supplier__name', 'product_name_snapshot', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | tech → catalog.Tech; on_delete=PROTECT |
| `supplier_price_updated_at` | DateTimeField; null=True; blank=True; editable=False | Закупочная цена скорректирована |
| `price_list_item` | ForeignKey; null=True; blank=True; editable=False | price list item → price.ProcurementPriceListItem; on_delete=PROTECT |
| `price_supplier` | ForeignKey; null=True; blank=True; editable=False | Источник цены → partners.Supplier; on_delete=PROTECT |
| `batch` | ForeignKey; null=False; blank=False; editable=True | Подборка → orders.SupplierOrderBatch; on_delete=PROTECT |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | Поставщик → partners.Supplier; on_delete=PROTECT |
| `product_name_snapshot` | CharField; null=False; blank=False; editable=False; max_length=255 | Название товара |
| `article_snapshot` | CharField; null=False; blank=False; editable=False; max_length=100 | Артикул |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | Количество |
| `supplier_price_aed_snapshot` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=6 | Цена поставщика, AED |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('product_kind', 'cd'), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('product_kind', 'tech'), ('tech__isnull', False))) name='supplier_batch_line_exact_product'>, <CheckConstraint: condition=(AND: ('quantity__gte', 0)) name='supplier_batch_quantity_nonnegative'>, <UniqueConstraint: fields=('batch', 'supplier', 'price_list_item', 'price_supplier') name='unique_trip_supplier_product_price'>]`; unique_together: `()`.

## `orders.SupplierTripAllocation` — supplier trip allocation

Распределение строки поставщика между клиентскими позициями рейса.

Таблица `orders_suppliertripallocation`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `line` | ForeignKey; null=False; blank=False; editable=True | line → orders.SupplierOrderBatchLine; on_delete=PROTECT |
| `order_item` | ForeignKey; null=False; blank=False; editable=True | order item → orders.CustomerProcurementOrderItem; on_delete=PROTECT |
| `prepayment_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | prepayment quantity |
| `postpayment_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | postpayment quantity |
| `prepayment_cap` | PositiveIntegerField; null=False; blank=False; editable=True | prepayment cap |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('line', 'order_item') name='unique_trip_line_customer_item'>]`; unique_together: `()`.

## `orders.SupplierTripChange` — supplier trip change

Аудит изменения состава/назначений/условий рейса.

Таблица `orders_suppliertripchange`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `batch` | ForeignKey; null=False; blank=False; editable=True | batch → orders.SupplierOrderBatch; on_delete=PROTECT |
| `actor` | ForeignKey; null=False; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `revision` | PositiveIntegerField; null=False; blank=False; editable=True | revision |
| `description` | CharField; null=False; blank=False; editable=True; max_length=500 | description |
| `details` | JSONField; null=False; blank=False; editable=True | details |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `orders.TripArrival` — trip arrival

TripArrival(id, trip, usdt_aed, usdt_rub, actual_delivery, arrived_at, arrived_by, revision, reviewed_orders, purchase_total, control_total, finalized_at, finalized_by, proposed_prices, applied_prices)

Таблица `orders_triparrival`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `trip` | OneToOneField; null=False; blank=False; editable=True | trip → orders.SupplierOrderBatch; on_delete=PROTECT |
| `usdt_aed` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | AED за 1 USDT |
| `usdt_rub` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | RUB за 1 USDT |
| `actual_delivery` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Фактическая доставка, RUB |
| `arrived_at` | DateTimeField; null=True; blank=True; editable=False | arrived at |
| `arrived_by` | ForeignKey; null=False; blank=False; editable=True | arrived by → accounts.User; on_delete=PROTECT |
| `revision` | PositiveIntegerField; null=False; blank=False; editable=False | revision |
| `reviewed_orders` | JSONField; null=False; blank=False; editable=False | reviewed orders |
| `purchase_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | purchase total |
| `control_total` | DecimalField; null=False; blank=False; editable=False; max_digits=20; decimal_places=2 | control total |
| `finalized_at` | DateTimeField; null=True; blank=True; editable=False | finalized at |
| `finalized_by` | ForeignKey; null=True; blank=False; editable=True | finalized by → accounts.User; on_delete=PROTECT |
| `proposed_prices` | JSONField; null=False; blank=False; editable=False | proposed prices |
| `applied_prices` | JSONField; null=False; blank=False; editable=False | applied prices |

Permissions: []. Стандартные: ().

Ограничения: `[<CheckConstraint: condition=(AND: ('actual_delivery__gte', 0), ('usdt_aed__gt', 0), ('usdt_rub__gt', 0)) name='trip_arrival_positive_parameters'>]`; unique_together: `()`.

## `orders.TripCostRow` — trip cost row

TripCostRow(id, product_kind, cd, tech, arrival, order, order_item, allocation, supplier, portion, original_quantity, actual_quantity, price_aed, weight_grams_snapshot, preliminary_delivery, tariff_snapshot, purchase_unit_cost, delivery_total, final_total, customer_price, unit_discount, line_note)

Таблица `orders_tripcostrow`; порядок `('order_id', 'supplier_id', 'pk')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `product_kind` | CharField; null=False; blank=False; editable=False; max_length=8 | Тип товара; choices: cd → CD; tech → Tech |
| `cd` | ForeignKey; null=True; blank=True; editable=False | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=False | tech → catalog.Tech; on_delete=PROTECT |
| `arrival` | ForeignKey; null=False; blank=False; editable=True | arrival → orders.TripArrival; on_delete=PROTECT |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → orders.CustomerProcurementOrder; on_delete=PROTECT |
| `order_item` | ForeignKey; null=False; blank=False; editable=True | order item → orders.CustomerProcurementOrderItem; on_delete=PROTECT |
| `allocation` | ForeignKey; null=False; blank=False; editable=True | allocation → orders.SupplierTripAllocation; on_delete=PROTECT |
| `supplier` | ForeignKey; null=False; blank=False; editable=True | supplier → partners.Supplier; on_delete=PROTECT |
| `portion` | CharField; null=False; blank=False; editable=True; max_length=16 | portion |
| `original_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | original quantity |
| `actual_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | actual quantity |
| `price_aed` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=6 | price aed |
| `weight_grams_snapshot` | PositiveIntegerField; null=False; blank=False; editable=True | weight grams snapshot |
| `preliminary_delivery` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | preliminary delivery |
| `tariff_snapshot` | JSONField; null=False; blank=False; editable=True | tariff snapshot |
| `purchase_unit_cost` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | purchase unit cost |
| `delivery_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | delivery total |
| `final_total` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | final total |
| `customer_price` | DecimalField; null=True; blank=False; editable=True; max_digits=20; decimal_places=2 | customer price |
| `unit_discount` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | unit discount |
| `line_note` | TextField; null=False; blank=True; editable=True | line note |

Permissions: []. Стандартные: ().

Ограничения: `[<UniqueConstraint: fields=('arrival', 'allocation', 'portion') name='unique_arrival_allocation_portion'>, <CheckConstraint: condition=(AND: ('actual_quantity__lte', F(original_quantity)), ('original_quantity__gt', 0)) name='trip_actual_not_above_ordered'>, <CheckConstraint: condition=(AND: ('delivery_total__gte', 0), ('final_total__gte', 0), ('preliminary_delivery__gte', 0), ('purchase_unit_cost__gte', 0)) name='trip_cost_amounts_nonnegative'>]`; unique_together: `()`.

## `integrations.WorkerController` — worker controller

WorkerController(id, mode, instance, heartbeat_at, incident, incident_started_at, error)

Таблица `integrations_workercontroller`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | PositiveSmallIntegerField; null=False; blank=False; editable=False | id |
| `mode` | CharField; null=False; blank=False; editable=True; max_length=16 | mode; choices: site_only → Только сайт; managed → Контроль включён |
| `instance` | UUIDField; null=True; blank=True; editable=True; max_length=32 | instance |
| `heartbeat_at` | DateTimeField; null=True; blank=True; editable=True | heartbeat at |
| `incident` | UUIDField; null=False; blank=False; editable=True; max_length=32 | incident |
| `incident_started_at` | DateTimeField; null=True; blank=True; editable=True | incident started at |
| `error` | CharField; null=False; blank=True; editable=True; max_length=40 | error |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('id', 1)) name='single_worker_controller'>]`; unique_together: `()`.

## `integrations.WorkerProcess` — worker process

WorkerProcess(instance, pid, birth, services, heartbeat_at, ready, action, started_at)

Таблица `integrations_workerprocess`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `instance` | UUIDField; null=False; blank=False; editable=False; max_length=32 | instance |
| `pid` | PositiveIntegerField; null=False; blank=False; editable=True | pid |
| `birth` | CharField; null=False; blank=False; editable=True; max_length=80 | birth |
| `services` | JSONField; null=False; blank=False; editable=True | services |
| `heartbeat_at` | DateTimeField; null=False; blank=False; editable=True | heartbeat at |
| `ready` | BooleanField; null=False; blank=False; editable=True | ready |
| `action` | CharField; null=False; blank=True; editable=True; max_length=32 | action |
| `started_at` | DateTimeField; null=False; blank=True; editable=False | started at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `integrations.WorkerService` — worker service

WorkerService(code, expected, status, heartbeat_at, last_started_at, observed_at, incident, incident_started_at, failures, auto_paused, launch_instance, launch_started_at, stable_since, stable_instance, next_attempt_at, error)

Таблица `integrations_workerservice`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `code` | CharField; null=False; blank=False; editable=True; max_length=20 | code; choices: avito → Avito; yandex → Яндекс Маркет; google → Google Sheets; print → Печать этикеток; telegram_staff → Telegram — сотрудники |
| `expected` | CharField; null=False; blank=False; editable=True; max_length=20 | expected |
| `status` | CharField; null=False; blank=False; editable=True; max_length=20 | status |
| `heartbeat_at` | DateTimeField; null=True; blank=True; editable=True | heartbeat at |
| `last_started_at` | DateTimeField; null=True; blank=True; editable=True | last started at |
| `observed_at` | DateTimeField; null=True; blank=True; editable=True | observed at |
| `incident` | UUIDField; null=True; blank=True; editable=True; max_length=32 | incident |
| `incident_started_at` | DateTimeField; null=True; blank=True; editable=True | incident started at |
| `failures` | PositiveSmallIntegerField; null=False; blank=False; editable=True | failures |
| `auto_paused` | BooleanField; null=False; blank=False; editable=True | auto paused |
| `launch_instance` | UUIDField; null=True; blank=True; editable=True; max_length=32 | launch instance |
| `launch_started_at` | DateTimeField; null=True; blank=True; editable=True | launch started at |
| `stable_since` | DateTimeField; null=True; blank=True; editable=True | stable since |
| `stable_instance` | UUIDField; null=True; blank=True; editable=True; max_length=32 | stable instance |
| `next_attempt_at` | DateTimeField; null=True; blank=True; editable=True | next attempt at |
| `error` | CharField; null=False; blank=True; editable=True; max_length=40 | error |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `integrations.WorkerCommand` — worker command

WorkerCommand(id, request_id, service, actor, state, result, created_at, finished_at)

Таблица `integrations_workercommand`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | UUIDField; null=False; blank=False; editable=False; max_length=32 | id |
| `request_id` | UUIDField; null=False; blank=False; editable=True; max_length=32 | request id |
| `service` | CharField; null=False; blank=False; editable=True; max_length=20 | service; choices: avito → Avito; yandex → Яндекс Маркет; google → Google Sheets; print → Печать этикеток; telegram_staff → Telegram — сотрудники |
| `actor` | ForeignKey; null=True; blank=False; editable=True | actor → accounts.User; on_delete=SET_NULL |
| `state` | CharField; null=False; blank=False; editable=True; max_length=16 | state |
| `result` | CharField; null=False; blank=True; editable=True; max_length=40 | result |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `finished_at` | DateTimeField; null=True; blank=True; editable=True | finished at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('request_id', 'service') name='worker_request_service'>, <UniqueConstraint: fields=('service',) name='worker_one_active_command' condition=(AND: ('state__in', ['queued', 'running']))>]`; unique_together: `()`.

## `integrations.WorkerEvent` — worker event

WorkerEvent(id, service, kind, result, incident, command, actor, created_at)

Таблица `integrations_workerevent`; порядок `['-id']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `service` | CharField; null=False; blank=True; editable=True; max_length=16 | service |
| `kind` | CharField; null=False; blank=False; editable=True; max_length=40 | kind |
| `result` | CharField; null=False; blank=True; editable=True; max_length=40 | result |
| `incident` | UUIDField; null=True; blank=True; editable=True; max_length=32 | incident |
| `command` | ForeignKey; null=True; blank=False; editable=True | command → integrations.WorkerCommand; on_delete=SET_NULL |
| `actor` | ForeignKey; null=True; blank=False; editable=True | actor → accounts.User; on_delete=SET_NULL |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.IntegrationCredential` — параметры интеграции

Защищённые реквизиты провайдера; ключ шифрования хранится вне Git.

Таблица `integrations_integrationcredential`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `provider` | CharField; null=False; blank=False; editable=True; max_length=32 | Интеграция; choices: avito → Avito |
| `encrypted_client_id` | TextField; null=False; blank=True; editable=False | Client ID (зашифрован) |
| `encrypted_client_secret` | TextField; null=False; blank=True; editable=False | Client secret (зашифрован) |
| `account_id` | CharField; null=False; blank=True; editable=False; max_length=64 | ID аккаунта |
| `account_name` | CharField; null=False; blank=True; editable=False; max_length=255 | Название аккаунта |
| `status` | CharField; null=False; blank=False; editable=False; max_length=24 | Состояние; choices: not_configured → Не настроено; connected → Подключено; error → Ошибка подключения |
| `last_checked_at` | DateTimeField; null=True; blank=True; editable=False | Последняя проверка |
| `last_success_at` | DateTimeField; null=True; blank=True; editable=False | Последнее успешное подключение |
| `last_error` | TextField; null=False; blank=True; editable=False | Последняя ошибка |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: [('view_integrations', 'Интеграции: просмотр'), ('manage_integration_credentials', 'Интеграции: изменение API-ключей'), ('view_avito_integration', 'Avito: просмотр'), ('manage_avito_product', 'Avito: изменение профиля товара'), ('bind_avito_listing', 'Avito: привязка объявления'), ('rebind_avito_listing', 'Avito: перепривязка объявления'), ('manual_avito_sync', 'Avito: ручная синхронизация')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.ReefApiCredential` — ключ ReefAPI

ReefApiCredential(id, encrypted_api_key, last_checked_at, last_error, updated_at)

Таблица `integrations_reefapicredential`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `encrypted_api_key` | TextField; null=False; blank=True; editable=False | API key (зашифрован) |
| `last_checked_at` | DateTimeField; null=True; blank=True; editable=False | Последняя проверка |
| `last_error` | CharField; null=False; blank=True; editable=False; max_length=255 | Ошибка подключения |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoPriceCheckResult` — результат Avito Check

AvitoPriceCheckResult(id, profile, checked_at, offers, metadata)

Таблица `integrations_avitopricecheckresult`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `profile` | OneToOneField; null=False; blank=False; editable=True | Профиль товара → integrations.AvitoProductProfile; on_delete=CASCADE |
| `checked_at` | DateTimeField; null=False; blank=False; editable=True | Время проверки |
| `offers` | JSONField; null=False; blank=False; editable=True | Подходящие объявления |
| `metadata` | JSONField; null=False; blank=True; editable=True | Параметры проверки |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoCheckListingCache` — кеш объявления Avito Check

AvitoCheckListingCache(id, ad_id, checked_at, data)

Таблица `integrations_avitochecklistingcache`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `ad_id` | CharField; null=False; blank=False; editable=True; max_length=32 | ID объявления |
| `checked_at` | DateTimeField; null=False; blank=False; editable=True | Время получения |
| `data` | JSONField; null=False; blank=False; editable=True | Карточка ReefAPI |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoManualPrice` — найденная цена Avito

AvitoManualPrice(id, profile, price, recorded_at, recorded_by)

Таблица `integrations_avitomanualprice`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `profile` | OneToOneField; null=False; blank=False; editable=True | profile → integrations.AvitoProductProfile; on_delete=CASCADE |
| `price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | Найденная минимальная цена |
| `recorded_at` | DateTimeField; null=False; blank=False; editable=True | Дата добавления |
| `recorded_by` | ForeignKey; null=True; blank=False; editable=True | recorded by → accounts.User; on_delete=SET_NULL |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(AND: ('price__gt', 0)) name='avito_manual_price_positive'>]`; unique_together: `()`.

## `integrations.AvitoProductProfile` — Avito-профиль товара

Локальная целевая карточка синхронизации Avito.

Таблица `integrations_avitoproductprofile`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `cd` | OneToOneField; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=CASCADE |
| `tech` | OneToOneField; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=CASCADE |
| `sell_on_avito` | BooleanField; null=False; blank=False; editable=True | Продаётся на Avito |
| `listing_title` | CharField; null=False; blank=True; editable=True; max_length=255 | Заголовок Avito |
| `listing_description` | TextField; null=False; blank=True; editable=True | Описание Avito |
| `category_slug` | CharField; null=False; blank=True; editable=True; max_length=255 | Категория Avito |
| `category_name` | CharField; null=False; blank=True; editable=True; max_length=255 | Название категории |
| `attributes` | JSONField; null=False; blank=True; editable=True | Поля Avito |
| `schema_snapshot` | JSONField; null=False; blank=True; editable=False | Схема полей Avito |
| `sync_status` | CharField; null=False; blank=False; editable=False; max_length=16 | Состояние синхронизации; choices: idle → Ожидает; queued → В очереди; syncing → Синхронизация; ok → OK; error → Ошибка |
| `last_error` | TextField; null=False; blank=True; editable=False | Последняя ошибка |
| `last_successful_sync_at` | DateTimeField; null=True; blank=True; editable=False | Последняя успешная синхронизация |
| `desired_state_hash` | CharField; null=False; blank=True; editable=False; max_length=64 | Хэш состояния |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='avito_profile_exact_product'>]`; unique_together: `()`.

## `integrations.AvitoProductPhoto` — Avito-фотография

AvitoProductPhoto(id, profile, image, sort_order, source, remote_url, created_at)

Таблица `integrations_avitoproductphoto`; порядок `('sort_order', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `profile` | ForeignKey; null=False; blank=False; editable=True | Avito-профиль → integrations.AvitoProductProfile; on_delete=CASCADE |
| `image` | FileField; null=False; blank=False; editable=True; max_length=100 | Фотография |
| `sort_order` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Порядок |
| `source` | CharField; null=False; blank=False; editable=True; max_length=16 | Источник; choices: user → Загружено пользователем; avito → Импортировано из Avito |
| `remote_url` | CharField; null=False; blank=True; editable=False; max_length=1000 | Исходный URL Avito |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создано |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('profile', 'sort_order') name='unique_avito_photo_order'>]`; unique_together: `()`.

## `integrations.AvitoRemoteListing` — объявление Avito

Последний полученный снимок удалённого объявления, который может устареть.

Таблица `integrations_avitoremotelisting`; порядок `('-last_seen_at', '-avito_item_id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `avito_item_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | Avito ID |
| `title` | CharField; null=False; blank=True; editable=True; max_length=500 | Название |
| `category_name` | CharField; null=False; blank=True; editable=True; max_length=255 | Категория |
| `status` | CharField; null=False; blank=True; editable=True; max_length=64 | Статус |
| `remote_price` | DecimalField; null=True; blank=True; editable=False; max_digits=20; decimal_places=2 | Текущая цена Avito |
| `url` | CharField; null=False; blank=True; editable=True; max_length=1000 | Ссылка |
| `snapshot` | JSONField; null=False; blank=True; editable=False | Безопасный snapshot |
| `last_seen_at` | DateTimeField; null=True; blank=True; editable=False | Последний раз получено |
| `missing_since` | DateTimeField; null=True; blank=True; editable=False | Не найдено с |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoListingConnection` — привязка объявления Avito

Явная связь удалённого объявления и локального профиля товара.

Таблица `integrations_avitolistingconnection`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `profile` | OneToOneField; null=False; blank=False; editable=True | Профиль товара → integrations.AvitoProductProfile; on_delete=CASCADE |
| `remote_listing` | OneToOneField; null=False; blank=False; editable=True | Объявление Avito → integrations.AvitoRemoteListing; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Привязано |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoSyncJob` — задача синхронизации Avito

Задание очереди Avito с ключом дедупликации и состоянием выполнения.

Таблица `integrations_avitosyncjob`; порядок `('run_after', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `dedupe_key` | CharField; null=False; blank=False; editable=True; max_length=100 | Ключ объединения |
| `job_type` | CharField; null=False; blank=False; editable=True; max_length=16 | Тип; choices: product → Товар; reconcile → Контрольная сверка; refresh → Обновление объявлений; manual → Ручная сверка; status_refresh → Обновление статусов объявлений |
| `profile` | ForeignKey; null=True; blank=True; editable=True | profile → integrations.AvitoProductProfile; on_delete=CASCADE |
| `status` | CharField; null=False; blank=False; editable=True; max_length=16 | Статус; choices: pending → Ожидает; running → Выполняется; done → Выполнено; error → Ошибка |
| `run_after` | DateTimeField; null=False; blank=False; editable=True | Выполнить после |
| `attempts` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Попытки |
| `last_error` | TextField; null=False; blank=True; editable=True | Последняя ошибка |
| `total_count` | PositiveIntegerField; null=False; blank=False; editable=True | Объявлений к проверке |
| `checked_count` | PositiveIntegerField; null=False; blank=False; editable=True | Проверено |
| `changed_count` | PositiveIntegerField; null=False; blank=False; editable=True | Изменено и подтверждено |
| `stock_changed_count` | PositiveIntegerField; null=False; blank=False; editable=True | Исправлено остатков |
| `price_changed_count` | PositiveIntegerField; null=False; blank=False; editable=True | Исправлено цен |
| `failed_count` | PositiveIntegerField; null=False; blank=False; editable=True | Не удалось синхронизировать |
| `skipped_count` | PositiveIntegerField; null=False; blank=False; editable=True | Неактивных или вне списка |
| `details` | JSONField; null=False; blank=True; editable=True | Итог сверки |
| `phase` | CharField; null=False; blank=True; editable=True; max_length=120 | Этап сверки |
| `current_item` | CharField; null=False; blank=True; editable=True; max_length=255 | Текущий товар |
| `started_at` | DateTimeField; null=True; blank=True; editable=True | Начало сверки |
| `finished_at` | DateTimeField; null=True; blank=True; editable=True | Завершение сверки |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создана |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлена |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.AvitoSyncLog` — запись синхронизации Avito

История попытки/фазы обмена Avito без раскрытия рабочих секретов.

Таблица `integrations_avitosynclog`; порядок `('-started_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `profile` | ForeignKey; null=True; blank=True; editable=True | profile → integrations.AvitoProductProfile; on_delete=SET_NULL |
| `remote_listing` | ForeignKey; null=True; blank=True; editable=True | remote listing → integrations.AvitoRemoteListing; on_delete=SET_NULL |
| `operation` | CharField; null=False; blank=False; editable=True; max_length=64 | Операция |
| `result` | CharField; null=False; blank=False; editable=True; max_length=16 | Результат; choices: success → Успешно; error → Ошибка; skipped → Пропущено |
| `http_status` | PositiveSmallIntegerField; null=True; blank=True; editable=True | HTTP-статус |
| `error_category` | CharField; null=False; blank=True; editable=True; max_length=32 | Категория ошибки |
| `message` | TextField; null=False; blank=True; editable=True | Сообщение |
| `retry_number` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Номер попытки |
| `started_at` | DateTimeField; null=False; blank=False; editable=True | Начало |
| `finished_at` | DateTimeField; null=False; blank=True; editable=False | Завершение |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.IntegrationAuditEvent` — событие интеграции

IntegrationAuditEvent(id, actor, action, product_kind, product_id, details, created_at)

Таблица `integrations_integrationauditevent`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `actor` | ForeignKey; null=True; blank=True; editable=True | actor → accounts.User; on_delete=SET_NULL |
| `action` | CharField; null=False; blank=False; editable=True; max_length=64 | Действие |
| `product_kind` | CharField; null=False; blank=True; editable=True; max_length=8 | Тип товара |
| `product_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | ID товара |
| `details` | JSONField; null=False; blank=True; editable=True | Детали без секретов |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Дата и время |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.GoogleSheetsIntegration` — интеграция Google Sheets

Настройка односторонней выгрузки CRM в Google Sheets.

Таблица `integrations_googlesheetsintegration`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `spreadsheet_url` | CharField; null=False; blank=False; editable=True; max_length=1000 | Ссылка на таблицу |
| `spreadsheet_id` | CharField; null=False; blank=False; editable=False; max_length=255 | ID таблицы |
| `sheet_name` | CharField; null=False; blank=False; editable=True; max_length=100 | Лист CRM |
| `enabled` | BooleanField; null=False; blank=False; editable=True | Автоматическая синхронизация |
| `status` | CharField; null=False; blank=False; editable=True; max_length=24 | Состояние; choices: not_configured → Не настроено; idle → Ожидает; queued → В очереди; syncing → Синхронизация; ok → Синхронизировано; error → Ошибка |
| `last_attempt_at` | DateTimeField; null=True; blank=True; editable=False | Последняя попытка |
| `last_success_at` | DateTimeField; null=True; blank=True; editable=False | Последняя успешная синхронизация |
| `last_error` | TextField; null=False; blank=True; editable=False | Последняя ошибка |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: [('manual_google_sheets_sync', 'Google Sheets: ручная синхронизация')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `integrations.GoogleSheetsSyncJob` — google sheets sync job

Дедуплицированное задание Sheets с ошибкой и временем следующей попытки.

Таблица `integrations_googlesheetssyncjob`; порядок `('run_after', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `dedupe_key` | CharField; null=False; blank=False; editable=True; max_length=100 | Ключ объединения |
| `status` | CharField; null=False; blank=False; editable=True; max_length=16 | Статус; choices: pending → Ожидает; running → Выполняется; done → Выполнено; error → Ошибка |
| `run_after` | DateTimeField; null=False; blank=False; editable=True | Выполнить после |
| `attempts` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Попытки |
| `requested_by` | ForeignKey; null=True; blank=True; editable=True | requested by → accounts.User; on_delete=SET_NULL |
| `last_error` | TextField; null=False; blank=True; editable=True | Последняя ошибка |
| `started_at` | DateTimeField; null=True; blank=True; editable=True | Начато |
| `finished_at` | DateTimeField; null=True; blank=True; editable=True | Завершено |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создано |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлено |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `telegram_bots.StaffBot` — бот сотрудников

StaffBot(id, code, name, username, enabled, cooldown_seconds, next_update_id, last_poll_at, last_success_at, error_category, lease_owner, lease_until)

Таблица `telegram_bots_staffbot`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `code` | CharField; null=False; blank=False; editable=False; max_length=32 | code |
| `name` | CharField; null=False; blank=False; editable=True; max_length=100 | name |
| `username` | CharField; null=False; blank=True; editable=True; max_length=32 | username |
| `enabled` | BooleanField; null=False; blank=False; editable=True | enabled |
| `cooldown_seconds` | PositiveIntegerField; null=False; blank=False; editable=True | cooldown seconds |
| `next_update_id` | BigIntegerField; null=False; blank=False; editable=True | next update id |
| `last_poll_at` | DateTimeField; null=True; blank=True; editable=True | last poll at |
| `last_success_at` | DateTimeField; null=True; blank=True; editable=True | last success at |
| `error_category` | CharField; null=False; blank=True; editable=True; max_length=40 | error category |
| `lease_owner` | UUIDField; null=True; blank=True; editable=True; max_length=32 | lease owner |
| `lease_until` | DateTimeField; null=True; blank=True; editable=True | lease until |

Permissions: [('use_staff_bot', 'Может пользоваться Telegram-ботом сотрудников')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `telegram_bots.StaffBotAccess` — staff bot access

StaffBotAccess(id, bot, user, allowed, telegram_user_id, username, linked_at, revoked_at)

Таблица `telegram_bots_staffbotaccess`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `bot` | ForeignKey; null=False; blank=False; editable=True | bot → telegram_bots.StaffBot; on_delete=CASCADE |
| `user` | ForeignKey; null=False; blank=False; editable=True | user → accounts.User; on_delete=CASCADE |
| `allowed` | BooleanField; null=False; blank=False; editable=True | allowed |
| `telegram_user_id` | BigIntegerField; null=True; blank=True; editable=True | telegram user id |
| `username` | CharField; null=False; blank=True; editable=True; max_length=64 | username |
| `linked_at` | DateTimeField; null=True; blank=True; editable=True | linked at |
| `revoked_at` | DateTimeField; null=True; blank=True; editable=True | revoked at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('bot', 'user') name='telegram_bot_employee'>, <UniqueConstraint: fields=('bot', 'telegram_user_id') name='telegram_bot_identity'>]`; unique_together: `()`.

## `telegram_bots.StaffBotLink` — staff bot link

StaffBotLink(id, access, token_hash, expires_at, used_at, created_at)

Таблица `telegram_bots_staffbotlink`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `access` | ForeignKey; null=False; blank=False; editable=True | access → telegram_bots.StaffBotAccess; on_delete=CASCADE |
| `token_hash` | CharField; null=False; blank=False; editable=True; max_length=64 | token hash |
| `expires_at` | DateTimeField; null=False; blank=False; editable=True | expires at |
| `used_at` | DateTimeField; null=True; blank=True; editable=True | used at |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `telegram_bots.StaffBotUpdate` — staff bot update

StaffBotUpdate(id, bot, update_id, created_at, result)

Таблица `telegram_bots_staffbotupdate`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `bot` | ForeignKey; null=False; blank=False; editable=True | bot → telegram_bots.StaffBot; on_delete=CASCADE |
| `update_id` | BigIntegerField; null=False; blank=False; editable=True | update id |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `result` | CharField; null=False; blank=True; editable=True; max_length=40 | result |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('bot', 'update_id') name='telegram_bot_update'>]`; unique_together: `()`.

## `telegram_bots.StaffBotJob` — staff bot job

StaffBotJob(id, bot, access, warehouse, update, chat_id, state, created_at, started_at, finished_at, error_category, telegram_message_id)

Таблица `telegram_bots_staffbotjob`; порядок `['created_at']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | UUIDField; null=False; blank=False; editable=False; max_length=32 | id |
| `bot` | ForeignKey; null=False; blank=False; editable=True | bot → telegram_bots.StaffBot; on_delete=CASCADE |
| `access` | ForeignKey; null=False; blank=False; editable=True | access → telegram_bots.StaffBotAccess; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=True; blank=False; editable=True | warehouse → warehouse.Warehouse; on_delete=SET_NULL |
| `update` | OneToOneField; null=False; blank=False; editable=True | update → telegram_bots.StaffBotUpdate; on_delete=PROTECT |
| `chat_id` | BigIntegerField; null=False; blank=False; editable=True | chat id |
| `state` | CharField; null=False; blank=False; editable=True; max_length=16 | state; choices: queued → В очереди; generating → Формируется; sending → Отправляется; done → Отправлен; error → Ошибка; uncertain → Результат отправки неизвестен |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `started_at` | DateTimeField; null=True; blank=True; editable=True | started at |
| `finished_at` | DateTimeField; null=True; blank=True; editable=True | finished at |
| `error_category` | CharField; null=False; blank=True; editable=True; max_length=40 | error category |
| `telegram_message_id` | BigIntegerField; null=True; blank=True; editable=True | telegram message id |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('access',) name='telegram_one_active_price' condition=(AND: ('state__in', ['queued', 'generating', 'sending']))>]`; unique_together: `()`.

## `yandex_market.Integration` — integration

Integration(id, name, business_id, campaign_id, partner_warehouse_id, stock_api, price_scope, fulfillment_warehouse, operator, enabled, import_orders_from, checked_at, last_sync_at, last_error, configuration, created_at)

Таблица `yandex_market_integration`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `name` | CharField; null=False; blank=False; editable=True; max_length=200 | Название |
| `business_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | businessId |
| `campaign_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | campaignId |
| `partner_warehouse_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | Склад Маркета |
| `stock_api` | CharField; null=False; blank=False; editable=True; max_length=20 | API остатков; choices: partner → Склад кабинета (v3); group → Группа складов (v2) |
| `price_scope` | CharField; null=False; blank=False; editable=True; max_length=20 | Область цены; choices: business → Весь кабинет; campaign → Этот магазин |
| `fulfillment_warehouse` | ForeignKey; null=False; blank=False; editable=True | Склад выполнения заказов → warehouse.Warehouse; on_delete=PROTECT |
| `operator` | ForeignKey; null=False; blank=False; editable=True | Ответственный за автоматические операции → accounts.User; on_delete=PROTECT |
| `enabled` | BooleanField; null=False; blank=False; editable=True | Фоновый обмен включён |
| `import_orders_from` | DateTimeField; null=False; blank=False; editable=True | Начало импорта заказов |
| `checked_at` | DateTimeField; null=True; blank=True; editable=True | checked at |
| `last_sync_at` | DateTimeField; null=True; blank=True; editable=True | last sync at |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `configuration` | JSONField; null=False; blank=True; editable=True | configuration |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: [('manage_settings', 'Яндекс Маркет: настройки'), ('edit_content', 'Яндекс Маркет: контент товаров'), ('bind_offer', 'Яндекс Маркет: привязка товаров'), ('rebind_offer', 'Яндекс Маркет: перепривязка и отвязка'), ('retry_sync', 'Яндекс Маркет: синхронизация'), ('manage_orders', 'Яндекс Маркет: обработка заказов'), ('print_labels', 'Яндекс Маркет: печать ярлыков'), ('accept_return', 'Яндекс Маркет: приём возврата')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `yandex_market.RemoteOffer` — remote offer

RemoteOffer(id, integration, offer_id, name, market_sku, category_id, category_name, card_status, content_rating, snapshot, card, remote_price, remote_stock, archived, fetched_at, stock_checked_at, price_checked_at, last_error)

Таблица `yandex_market_remoteoffer`; порядок `['name', 'id']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `offer_id` | CharField; null=False; blank=False; editable=True; max_length=255 | offer id |
| `name` | CharField; null=False; blank=True; editable=True; max_length=512 | name |
| `market_sku` | PositiveBigIntegerField; null=True; blank=True; editable=True | market sku |
| `category_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | category id |
| `category_name` | CharField; null=False; blank=True; editable=True; max_length=512 | category name |
| `card_status` | CharField; null=False; blank=True; editable=True; max_length=80 | card status |
| `content_rating` | IntegerField; null=True; blank=True; editable=True | content rating |
| `snapshot` | JSONField; null=False; blank=False; editable=True | snapshot |
| `card` | JSONField; null=False; blank=False; editable=True | card |
| `remote_price` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | remote price |
| `remote_stock` | PositiveIntegerField; null=True; blank=True; editable=True | remote stock |
| `archived` | BooleanField; null=False; blank=False; editable=True | archived |
| `fetched_at` | DateTimeField; null=False; blank=False; editable=True | fetched at |
| `stock_checked_at` | DateTimeField; null=True; blank=True; editable=True | stock checked at |
| `price_checked_at` | DateTimeField; null=True; blank=True; editable=True | price checked at |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('integration', 'offer_id') name='ym_unique_remote_offer'>]`; unique_together: `()`.

## `yandex_market.OfferConnection` — offer connection

OfferConnection(id, integration, remote_offer, cd, tech, active, managed, sell_on_yandex, resume_display_pending, is_new, content, dirty_fields, delete_fields, parameters, category_id, state, revision, last_sync_at, last_success_at, last_error, last_sent_hash, last_sent_state, created_at)

Таблица `yandex_market_offerconnection`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `remote_offer` | ForeignKey; null=False; blank=False; editable=True | remote offer → yandex_market.RemoteOffer; on_delete=PROTECT |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=PROTECT |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=PROTECT |
| `active` | BooleanField; null=False; blank=False; editable=True | active |
| `managed` | BooleanField; null=False; blank=False; editable=True | Управление подтверждено |
| `sell_on_yandex` | BooleanField; null=False; blank=False; editable=True | Продаётся на Яндекс Маркете |
| `resume_display_pending` | BooleanField; null=False; blank=False; editable=True | Ожидает снятия скрытия после первой привязки |
| `is_new` | BooleanField; null=False; blank=False; editable=True | is new |
| `content` | JSONField; null=False; blank=True; editable=True | content |
| `dirty_fields` | JSONField; null=False; blank=True; editable=True | dirty fields |
| `delete_fields` | JSONField; null=False; blank=True; editable=True | delete fields |
| `parameters` | JSONField; null=False; blank=True; editable=True | parameters |
| `category_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | category id |
| `state` | CharField; null=False; blank=False; editable=True; max_length=20 | state; choices: linked → Ожидает включения управления; queued → В очереди; syncing → Синхронизация; synced → Синхронизирован; error → Ошибка; attention → Требуется внимание |
| `revision` | PositiveIntegerField; null=False; blank=False; editable=True | revision |
| `last_sync_at` | DateTimeField; null=True; blank=True; editable=True | last sync at |
| `last_success_at` | DateTimeField; null=True; blank=True; editable=True | last success at |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `last_sent_hash` | CharField; null=False; blank=True; editable=True; max_length=64 | last sent hash |
| `last_sent_state` | JSONField; null=False; blank=True; editable=True | last sent state |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='ym_exactly_one_product'>, <UniqueConstraint: fields=('remote_offer',) name='ym_one_active_offer' condition=(AND: ('active', True))>, <UniqueConstraint: fields=('integration', 'cd') name='ym_one_active_cd' condition=(AND: ('active', True), ('cd__isnull', False))>, <UniqueConstraint: fields=('integration', 'tech') name='ym_one_active_tech' condition=(AND: ('active', True), ('tech__isnull', False))>]`; unique_together: `()`.

## `yandex_market.CategorySchema` — category schema

CategorySchema(id, category_id, name, placement_rate, schema, fetched_at)

Таблица `yandex_market_categoryschema`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `category_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | category id |
| `name` | CharField; null=False; blank=True; editable=True; max_length=512 | Категория Яндекс Маркета |
| `placement_rate` | DecimalField; null=True; blank=True; editable=True; max_digits=5; decimal_places=2 | Тариф размещения, % |
| `schema` | JSONField; null=False; blank=False; editable=True | schema |
| `fetched_at` | DateTimeField; null=False; blank=False; editable=True | fetched at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `yandex_market.Media` — media

Media(id, connection, public_id, image, position, active, created_at)

Таблица `yandex_market_media`; порядок `['position', 'id']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `connection` | ForeignKey; null=False; blank=False; editable=True | connection → yandex_market.OfferConnection; on_delete=PROTECT |
| `public_id` | UUIDField; null=False; blank=False; editable=False; max_length=32 | public id |
| `image` | FileField; null=False; blank=False; editable=True; max_length=100 | image |
| `position` | PositiveIntegerField; null=False; blank=False; editable=True | position |
| `active` | BooleanField; null=False; blank=False; editable=True | active |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `yandex_market.OrderMetadata` — order metadata

OrderMetadata(id, integration, order_id, sale, status, substatus, created_remote_at, updated_remote_at, payment, delivery, items, prices, boxes, fake, stock_deducted, shipped_once, last_error, last_sync_at, created_at)

Таблица `yandex_market_ordermetadata`; порядок `['-order_id']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `order_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | order id |
| `sale` | OneToOneField; null=True; blank=True; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `status` | CharField; null=False; blank=True; editable=True; max_length=64 | status |
| `substatus` | CharField; null=False; blank=True; editable=True; max_length=100 | substatus |
| `created_remote_at` | DateTimeField; null=True; blank=True; editable=True | created remote at |
| `updated_remote_at` | DateTimeField; null=True; blank=True; editable=True | updated remote at |
| `payment` | JSONField; null=False; blank=False; editable=True | payment |
| `delivery` | JSONField; null=False; blank=False; editable=True | delivery |
| `items` | JSONField; null=False; blank=False; editable=True | items |
| `prices` | JSONField; null=False; blank=False; editable=True | prices |
| `boxes` | JSONField; null=False; blank=False; editable=True | boxes |
| `fake` | BooleanField; null=False; blank=False; editable=True | fake |
| `stock_deducted` | BooleanField; null=False; blank=False; editable=True | stock deducted |
| `shipped_once` | BooleanField; null=False; blank=False; editable=True | shipped once |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `last_sync_at` | DateTimeField; null=True; blank=True; editable=True | last sync at |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('integration', 'order_id') name='ym_unique_order'>]`; unique_together: `()`.

## `yandex_market.OrderLine` — order line

OrderLine(id, order, remote_item_id, connection, quantity, returned_quantity, unit_price)

Таблица `yandex_market_orderline`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `remote_item_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | remote item id |
| `connection` | ForeignKey; null=False; blank=False; editable=True | connection → yandex_market.OfferConnection; on_delete=PROTECT |
| `quantity` | PositiveIntegerField; null=False; blank=False; editable=True | quantity |
| `returned_quantity` | PositiveIntegerField; null=False; blank=False; editable=True | returned quantity |
| `unit_price` | DecimalField; null=False; blank=False; editable=True; max_digits=20; decimal_places=2 | unit price |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('order', 'remote_item_id') name='ym_unique_order_item'>, <CheckConstraint: condition=(AND: ('returned_quantity__lte', F(quantity))) name='ym_return_not_above_sold'>]`; unique_together: `()`.

## `yandex_market.ReturnMetadata` — return metadata

ReturnMetadata(id, order, return_id, status, kind, snapshot, accepted_at, accepted_by, warehouse, last_error)

Таблица `yandex_market_returnmetadata`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `order` | ForeignKey; null=False; blank=False; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `return_id` | PositiveBigIntegerField; null=False; blank=False; editable=True | return id |
| `status` | CharField; null=False; blank=True; editable=True; max_length=100 | status |
| `kind` | CharField; null=False; blank=True; editable=True; max_length=100 | kind |
| `snapshot` | JSONField; null=False; blank=False; editable=True | snapshot |
| `accepted_at` | DateTimeField; null=True; blank=True; editable=True | accepted at |
| `accepted_by` | ForeignKey; null=True; blank=True; editable=True | accepted by → accounts.User; on_delete=PROTECT |
| `warehouse` | ForeignKey; null=True; blank=True; editable=True | warehouse → warehouse.Warehouse; on_delete=PROTECT |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('order', 'return_id') name='ym_unique_return'>]`; unique_together: `()`.

## `yandex_market.WebhookEvent` — webhook event

WebhookEvent(id, integration, key, event_type, order_id, return_id, received_at, processed_at, state, attempts, last_error)

Таблица `yandex_market_webhookevent`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `key` | CharField; null=False; blank=False; editable=True; max_length=64 | key |
| `event_type` | CharField; null=False; blank=False; editable=True; max_length=100 | event type |
| `order_id` | PositiveBigIntegerField; null=True; blank=False; editable=True | order id |
| `return_id` | PositiveBigIntegerField; null=True; blank=False; editable=True | return id |
| `received_at` | DateTimeField; null=False; blank=True; editable=False | received at |
| `processed_at` | DateTimeField; null=True; blank=False; editable=True | processed at |
| `state` | CharField; null=False; blank=False; editable=True; max_length=20 | state |
| `attempts` | PositiveIntegerField; null=False; blank=False; editable=True | attempts |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('integration', 'key') name='ym_unique_event'>]`; unique_together: `()`.

## `yandex_market.SyncJob` — sync job

SyncJob(id, integration, key, kind, payload, state, generation, claimed_generation, lease, attempts, run_after, updated_at, last_error, actor)

Таблица `yandex_market_syncjob`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `key` | CharField; null=False; blank=False; editable=True; max_length=200 | key |
| `kind` | CharField; null=False; blank=False; editable=True; max_length=30 | kind |
| `payload` | JSONField; null=False; blank=False; editable=True | payload |
| `state` | CharField; null=False; blank=False; editable=True; max_length=20 | state |
| `generation` | PositiveIntegerField; null=False; blank=False; editable=True | generation |
| `claimed_generation` | PositiveIntegerField; null=False; blank=False; editable=True | claimed generation |
| `lease` | UUIDField; null=True; blank=True; editable=True; max_length=32 | lease |
| `attempts` | PositiveIntegerField; null=False; blank=False; editable=True | attempts |
| `run_after` | DateTimeField; null=False; blank=False; editable=True | run after |
| `updated_at` | DateTimeField; null=False; blank=False; editable=True | updated at |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `actor` | ForeignKey; null=True; blank=True; editable=True | actor → accounts.User; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `yandex_market.ApiLog` — api log

ApiLog(id, integration, created_at, operation, direction, entity_id, method, endpoint, http_status, result, error_code, message, request_id, duration_ms, attempt, job, actor)

Таблица `yandex_market_apilog`; порядок `['-id']`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=True; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `operation` | CharField; null=False; blank=False; editable=True; max_length=100 | operation |
| `direction` | CharField; null=False; blank=False; editable=True; max_length=10 | direction |
| `entity_id` | CharField; null=False; blank=True; editable=True; max_length=255 | entity id |
| `method` | CharField; null=False; blank=False; editable=True; max_length=10 | method |
| `endpoint` | CharField; null=False; blank=False; editable=True; max_length=500 | endpoint |
| `http_status` | PositiveIntegerField; null=True; blank=False; editable=True | http status |
| `result` | CharField; null=False; blank=False; editable=True; max_length=20 | result |
| `error_code` | CharField; null=False; blank=True; editable=True; max_length=100 | error code |
| `message` | TextField; null=False; blank=True; editable=True | message |
| `request_id` | CharField; null=False; blank=True; editable=True; max_length=200 | request id |
| `duration_ms` | PositiveIntegerField; null=False; blank=False; editable=True | duration ms |
| `attempt` | PositiveIntegerField; null=False; blank=False; editable=True | attempt |
| `job` | ForeignKey; null=True; blank=False; editable=True | job → yandex_market.SyncJob; on_delete=PROTECT |
| `actor` | ForeignKey; null=True; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `yandex_market.ApiBudget` — api budget

Общий счётчик лимита для всех процессов данного кабинета.

Таблица `yandex_market_apibudget`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `key` | CharField; null=False; blank=False; editable=True; max_length=200 | key |
| `window_start` | DateTimeField; null=False; blank=False; editable=True | window start |
| `used` | PositiveBigIntegerField; null=False; blank=False; editable=True | used |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `yandex_market.AuditEvent` — audit event

AuditEvent(id, integration, actor, action, entity_id, details, created_at)

Таблица `yandex_market_auditevent`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `actor` | ForeignKey; null=True; blank=False; editable=True | actor → accounts.User; on_delete=PROTECT |
| `action` | CharField; null=False; blank=False; editable=True; max_length=80 | action |
| `entity_id` | CharField; null=False; blank=False; editable=True; max_length=255 | entity id |
| `details` | JSONField; null=False; blank=False; editable=True | details |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `yandex_market.LabelDocument` — label document

LabelDocument(id, integration, order, order_ids, report_id, shipment_id, box_id, format, cache_signature, state, file, last_error, created_by, created_at)

Таблица `yandex_market_labeldocument`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `integration` | ForeignKey; null=False; blank=False; editable=True | integration → yandex_market.Integration; on_delete=PROTECT |
| `order` | ForeignKey; null=True; blank=True; editable=True | order → yandex_market.OrderMetadata; on_delete=PROTECT |
| `order_ids` | JSONField; null=False; blank=False; editable=True | order ids |
| `report_id` | CharField; null=False; blank=True; editable=True; max_length=100 | report id |
| `shipment_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | shipment id |
| `box_id` | PositiveBigIntegerField; null=True; blank=True; editable=True | box id |
| `format` | CharField; null=False; blank=False; editable=True; max_length=50 | format |
| `cache_signature` | CharField; null=False; blank=True; editable=False; max_length=64 | cache signature |
| `state` | CharField; null=False; blank=False; editable=True; max_length=30 | state |
| `file` | FileField; null=False; blank=True; editable=True; max_length=100 | file |
| `last_error` | TextField; null=False; blank=True; editable=True | last error |
| `created_by` | ForeignKey; null=False; blank=False; editable=True | created by → accounts.User; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `resource_storefront.WholesaleContact` — оптовый контакт

WholesaleContact(id, partner, name, phone, address, is_archived, created_at, updated_at)

Таблица `resource_storefront_wholesalecontact`; порядок `('name', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `partner` | ForeignKey; null=True; blank=True; editable=True | Партнёр → partners.Partner; on_delete=PROTECT |
| `name` | CharField; null=False; blank=False; editable=True; max_length=160 | Контактное имя |
| `phone` | CharField; null=False; blank=False; editable=True; max_length=40 | Основной номер телефона |
| `address` | TextField; null=False; blank=True; editable=True | Адрес |
| `is_archived` | BooleanField; null=False; blank=False; editable=True | Архивирован |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | Создан |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | Обновлён |

Permissions: [('manage_wholesale_contacts', 'Управление контактами оптовой витрины')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `resource_storefront.WholesaleAccessLink` — ссылка оптового доступа

WholesaleAccessLink(id, contact, token_digest, encrypted_token, is_active, created_at, created_by, revoked_at)

Таблица `resource_storefront_wholesaleaccesslink`; порядок `('-created_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `contact` | ForeignKey; null=False; blank=False; editable=True | contact → resource_storefront.WholesaleContact; on_delete=PROTECT |
| `token_digest` | CharField; null=False; blank=False; editable=False; max_length=64 | token digest |
| `encrypted_token` | TextField; null=False; blank=False; editable=False | encrypted token |
| `is_active` | BooleanField; null=False; blank=False; editable=True | is active |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `created_by` | ForeignKey; null=True; blank=False; editable=True | created by → accounts.User; on_delete=SET_NULL |
| `revoked_at` | DateTimeField; null=True; blank=True; editable=True | revoked at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('contact',) name='resource_one_active_link_per_contact' condition=(AND: ('is_active', True))>]`; unique_together: `()`.

## `resource_storefront.StorefrontSettings` — настройки оптовой витрины

StorefrontSettings(id, warehouse, minimum_order_amount, hero_title, hero_description, hero_button_label, hero_button_url, hero_image_desktop, hero_image_mobile, about_text, wholesale_terms, public_contacts, updated_at)

Таблица `resource_storefront_storefrontsettings`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | PositiveSmallIntegerField; null=False; blank=False; editable=False | id |
| `warehouse` | ForeignKey; null=True; blank=True; editable=True | Склад витрины → warehouse.Warehouse; on_delete=PROTECT |
| `minimum_order_amount` | DecimalField; null=True; blank=True; editable=True; max_digits=20; decimal_places=2 | Минимальная сумма заказа |
| `hero_title` | CharField; null=False; blank=True; editable=True; max_length=220 | Заголовок главной |
| `hero_description` | TextField; null=False; blank=True; editable=True | Описание главной |
| `hero_button_label` | CharField; null=False; blank=True; editable=True; max_length=80 | Текст кнопки |
| `hero_button_url` | CharField; null=False; blank=True; editable=True; max_length=300 | Адрес кнопки |
| `hero_image_desktop` | FileField; null=False; blank=True; editable=True; max_length=100 | hero image desktop |
| `hero_image_mobile` | FileField; null=False; blank=True; editable=True; max_length=100 | hero image mobile |
| `about_text` | TextField; null=False; blank=True; editable=True | О бренде |
| `wholesale_terms` | TextField; null=False; blank=True; editable=True | Условия оптовой работы |
| `public_contacts` | TextField; null=False; blank=True; editable=True | Контакты |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: [('manage_storefront', 'Управление содержимым оптовой витрины')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `resource_storefront.StorefrontProduct` — storefront product

StorefrontProduct(id, placement, cd, tech, sort_order, created_at)

Таблица `resource_storefront_storefrontproduct`; порядок `('sort_order', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `placement` | CharField; null=False; blank=False; editable=True; max_length=8 | placement; choices: new → Новинки; home → Главная подборка |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=CASCADE |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=CASCADE |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | sort order |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='resource_slot_exact_product'>, <UniqueConstraint: fields=('placement', 'cd') name='resource_slot_unique_cd' condition=(AND: ('cd__isnull', False))>, <UniqueConstraint: fields=('placement', 'tech') name='resource_slot_unique_tech' condition=(AND: ('tech__isnull', False))>]`; unique_together: `()`.

## `resource_storefront.ProductCollection` — подборка витрины

ProductCollection(id, title, slug, is_visible, sort_order, created_at)

Таблица `resource_storefront_productcollection`; порядок `('sort_order', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `title` | CharField; null=False; blank=False; editable=True; max_length=160 | title |
| `slug` | SlugField; null=False; blank=False; editable=True; max_length=180 | slug |
| `is_visible` | BooleanField; null=False; blank=False; editable=True | is visible |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | sort order |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `resource_storefront.CollectionProduct` — collection product

CollectionProduct(id, collection, cd, tech, sort_order)

Таблица `resource_storefront_collectionproduct`; порядок `('sort_order', 'id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `collection` | ForeignKey; null=False; blank=False; editable=True | collection → resource_storefront.ProductCollection; on_delete=CASCADE |
| `cd` | ForeignKey; null=True; blank=True; editable=True | cd → catalog.CD; on_delete=CASCADE |
| `tech` | ForeignKey; null=True; blank=True; editable=True | tech → catalog.Tech; on_delete=CASCADE |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | sort order |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='resource_collection_exact_product'>]`; unique_together: `()`.

## `resource_storefront.StorefrontNews` — новость витрины

StorefrontNews(id, title, slug, cover, excerpt, body, status, published_at, created_at, updated_at)

Таблица `resource_storefront_storefrontnews`; порядок `('-published_at', '-id')`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `title` | CharField; null=False; blank=False; editable=True; max_length=220 | title |
| `slug` | SlugField; null=False; blank=False; editable=True; max_length=240 | slug |
| `cover` | FileField; null=False; blank=True; editable=True; max_length=100 | cover |
| `excerpt` | TextField; null=False; blank=True; editable=True | excerpt |
| `body` | TextField; null=False; blank=True; editable=True | body |
| `status` | CharField; null=False; blank=False; editable=True; max_length=12 | status; choices: draft → Черновик; published → Опубликовано |
| `published_at` | DateTimeField; null=True; blank=True; editable=True | published at |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |
| `products` | ManyToManyField; null=False; blank=True; editable=True | products → catalog.CD |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `resource_storefront.NewsCDProduct` — news cd product

NewsCDProduct(id, news, cd, sort_order)

Таблица `resource_storefront_newscdproduct`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `news` | ForeignKey; null=False; blank=False; editable=True | news → resource_storefront.StorefrontNews; on_delete=CASCADE |
| `cd` | ForeignKey; null=False; blank=False; editable=True | cd → catalog.CD; on_delete=CASCADE |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | sort order |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `resource_storefront.NewsTechProduct` — news tech product

NewsTechProduct(id, news, tech, sort_order)

Таблица `resource_storefront_newstechproduct`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `news` | ForeignKey; null=False; blank=False; editable=True | news → resource_storefront.StorefrontNews; on_delete=CASCADE |
| `tech` | ForeignKey; null=False; blank=False; editable=True | tech → catalog.Tech; on_delete=CASCADE |
| `sort_order` | PositiveIntegerField; null=False; blank=False; editable=True | sort order |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `[]`.

## `resource_storefront.StorefrontSubmission` — storefront submission

StorefrontSubmission(id, contact, idempotency_key, cart_digest, sale, created_at)

Таблица `resource_storefront_storefrontsubmission`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `contact` | ForeignKey; null=False; blank=False; editable=True | contact → resource_storefront.WholesaleContact; on_delete=PROTECT |
| `idempotency_key` | CharField; null=False; blank=False; editable=True; max_length=64 | idempotency key |
| `cart_digest` | CharField; null=False; blank=False; editable=True; max_length=64 | cart digest |
| `sale` | OneToOneField; null=True; blank=True; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('contact', 'idempotency_key') name='resource_submission_once_per_contact'>]`; unique_together: `()`.

## `resource_storefront.CatalogImageCrop` — кадрирование фото каталога

CatalogImageCrop(id, cd, tech, source_image, position_x, position_y, zoom)

Таблица `resource_storefront_catalogimagecrop`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `cd` | OneToOneField; null=True; blank=True; editable=True | Диск → catalog.CD; on_delete=CASCADE |
| `tech` | OneToOneField; null=True; blank=True; editable=True | Техника → catalog.Tech; on_delete=CASCADE |
| `source_image` | CharField; null=False; blank=False; editable=False; max_length=300 | source image |
| `position_x` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Фокус по горизонтали, % |
| `position_y` | PositiveSmallIntegerField; null=False; blank=False; editable=True | Фокус по вертикали, % |
| `zoom` | DecimalField; null=False; blank=False; editable=True; max_digits=3; decimal_places=2 | Масштаб |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<CheckConstraint: condition=(OR: (AND: ('cd__isnull', False), ('tech__isnull', True)), (AND: ('cd__isnull', True), ('tech__isnull', False))) name='resource_crop_exact_product'>, <CheckConstraint: condition=(AND: ('position_x__lte', 100), ('position_y__lte', 100), ('zoom__gte', 1), ('zoom__lte', 3)) name='resource_crop_bounds'>]`; unique_together: `()`.

## `resource_storefront.RetailSettings` — настройки розничной витрины

RetailSettings(id, warehouse, price_source, generation, token_digest, encrypted_token, updated_at)

Таблица `resource_storefront_retailsettings`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | PositiveSmallIntegerField; null=False; blank=False; editable=False | id |
| `warehouse` | ForeignKey; null=True; blank=True; editable=True | Склад розничного сайта → warehouse.Warehouse; on_delete=PROTECT |
| `price_source` | CharField; null=False; blank=False; editable=True; max_length=24 | Источник цены; choices: avito_price → Цена Avito |
| `generation` | UUIDField; null=False; blank=False; editable=False; max_length=32 | generation |
| `token_digest` | CharField; null=False; blank=True; editable=False; max_length=64 | token digest |
| `encrypted_token` | TextField; null=False; blank=True; editable=False | encrypted token |
| `updated_at` | DateTimeField; null=False; blank=True; editable=False | updated at |

Permissions: [('manage_retail_storefront', 'Управление розничной витриной и общей ссылкой')]. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[]`; unique_together: `()`.

## `resource_storefront.RetailSubmission` — retail submission

RetailSubmission(id, visitor_id, idempotency_key, cart_digest, sale, created_at)

Таблица `resource_storefront_retailsubmission`; порядок `[]`.

| Поле | Тип/параметры | Назначение/связь |
| --- | --- | --- |
| `id` | BigAutoField; null=False; blank=True; editable=True | ID |
| `visitor_id` | UUIDField; null=False; blank=False; editable=True; max_length=32 | visitor id |
| `idempotency_key` | UUIDField; null=False; blank=False; editable=True; max_length=32 | idempotency key |
| `cart_digest` | CharField; null=False; blank=False; editable=True; max_length=64 | cart digest |
| `sale` | OneToOneField; null=True; blank=True; editable=True | sale → sales.Sale; on_delete=PROTECT |
| `created_at` | DateTimeField; null=False; blank=True; editable=False | created at |

Permissions: []. Стандартные: ('add', 'change', 'delete', 'view').

Ограничения: `[<UniqueConstraint: fields=('visitor_id', 'idempotency_key') name='resource_retail_submission_once'>]`; unique_together: `()`.
