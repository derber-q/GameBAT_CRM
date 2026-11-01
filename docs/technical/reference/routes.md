# Маршруты, обработчики и HTTP-проверки

<!-- Сгенерировано scripts/build_technical_reference.py; не редактировать вручную. -->

Справочник исходников и метаданных схемы, без рабочих записей/ключей. Перегенерация: `.venv/Scripts/python.exe scripts/build_technical_reference.py`.

Записей URL: **295**.

Admin свёрнут в один вход. URL включает HTML, JSON, команды и файлы; не каждый маршрут является страницей. Проверки внутри сервиса/формы дополняют показанные декораторы.

## `/crm/print-agent/heartbeat/`

Имя: ``.

Обработчик: `sales.print_agent_views.heartbeat`.

Исходник: `sales/print_agent_views.py:74`.

Декораторы: `agent_api('POST')`.

## `/crm/print-agent/claim/`

Имя: ``.

Обработчик: `sales.print_agent_views.claim`.

Исходник: `sales/print_agent_views.py:79`.

Декораторы: `agent_api('POST')`.

## `/crm/print-agent/jobs/<uuid:request_id>/document/`

Имя: ``.

Обработчик: `sales.print_agent_views.document`.

Исходник: `sales/print_agent_views.py:93`.

Декораторы: `agent_api('GET')`.

## `/crm/print-agent/jobs/<uuid:request_id>/result/`

Имя: ``.

Обработчик: `sales.print_agent_views.result`.

Исходник: `sales/print_agent_views.py:84`.

Декораторы: `agent_api('POST')`.

## `/`

Имя: `root`.

Обработчик: `GameBAT_CRM.urls.crm_entry`.

Исходник: `GameBAT_CRM/urls.py:26`.

Декораторы: `require_GET`.

## `/integrations/yandex/notifications/`

Имя: `yandex_market_public_notification`.

Обработчик: `yandex_market.webhooks.notification`.

Исходник: `yandex_market/webhooks.py:35`.

Декораторы: `csrf_exempt`; `require_POST`.

## `/integrations/yandex/media/<uuid:public_id>/`

Имя: `yandex_market_public_media`.

Обработчик: `yandex_market.views.public_media`.

Исходник: `yandex_market/views.py:453`.

## `/crm/admin/`

Имя: `admin:index`.

Встроенное дерево Django Admin; вход дополнительно защищён `core.access_admin_panel`/superuser.

## `/crm/accounts/login/`

Имя: `accounts:login`.

Обработчик: `django.contrib.auth.views.LoginView.dispatch`.

## `/crm/accounts/logout/`

Имя: `accounts:logout`.

Обработчик: `django.contrib.auth.views.LogoutView.dispatch`.

## `/crm/accounts/password/change/`

Имя: `accounts:password_change`.

Обработчик: `accounts.views.password_change`.

Исходник: `accounts/views.py:97`.

Декораторы: `login_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/stuf/`

Имя: `accounts:staff_by_group`.

Обработчик: `accounts.views.staff_by_group`.

Исходник: `accounts/views.py:40`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/staff_by_group.html`.

## `/crm/accounts/users/`

Имя: `accounts:user_list`.

Обработчик: `accounts.views.user_list`.

Исходник: `accounts/views.py:35`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/user_list.html`.

## `/crm/accounts/users/new/`

Имя: `accounts:user_create`.

Обработчик: `accounts.views.user_create`.

Исходник: `accounts/views.py:62`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/users/<int:pk>/`

Имя: `accounts:user_detail`.

Обработчик: `accounts.views.user_detail`.

Исходник: `accounts/views.py:56`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/user_detail.html`.

## `/crm/accounts/users/<int:pk>/edit/`

Имя: `accounts:user_update`.

Обработчик: `accounts.views.user_update`.

Исходник: `accounts/views.py:73`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/users/<int:pk>/reset-password/`

Имя: `accounts:password_reset`.

Обработчик: `accounts.views.admin_password_reset`.

Исходник: `accounts/views.py:85`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/users/<int:pk>/document/`

Имя: `accounts:verification_document`.

Обработчик: `accounts.views.verification_document`.

Исходник: `accounts/views.py:108`.

Декораторы: `login_required`.

## `/crm/accounts/permission-sets/`

Имя: `accounts:permission_sets`.

Обработчик: `accounts.views.permission_set_list`.

Исходник: `accounts/views.py:124`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/permission_set_list.html`.

## `/crm/accounts/permission-sets/new/`

Имя: `accounts:permission_set_create`.

Обработчик: `accounts.views.permission_set_edit`.

Исходник: `accounts/views.py:129`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/permission-sets/<int:pk>/edit/`

Имя: `accounts:permission_set_edit`.

Обработчик: `accounts.views.permission_set_edit`.

Исходник: `accounts/views.py:129`.

Декораторы: `superuser_required`.

Прямые шаблоны: `accounts/form.html`.

## `/crm/accounts/permission-sets/<int:pk>/delete/`

Имя: `accounts:permission_set_delete`.

Обработчик: `accounts.views.permission_set_delete`.

Исходник: `accounts/views.py:141`.

Декораторы: `require_POST`; `superuser_required`.

## `/crm/warehouse/`

Имя: `catalog:warehouse`.

Обработчик: `catalog.views.warehouse`.

Исходник: `catalog/views.py:7`.

## `/crm/warehouse/<int:pk>/revision/`

Имя: `warehouse:revision`.

Обработчик: `warehouse.revision_views.revision_page`.

Исходник: `warehouse/revision_views.py:16`.

Декораторы: `require_GET`; `permission_required_any(*ACCESS)`.

Прямые шаблоны: `warehouse/revision.html`.

## `/crm/warehouse/<int:pk>/revision/start/`

Имя: `warehouse:revision_start`.

Обработчик: `warehouse.revision_views.revision_start`.

Исходник: `warehouse/revision_views.py:32`.

Декораторы: `require_POST`; `permission_required_any('warehouse.view_warehouse_stock')`.

## `/crm/warehouse/<int:pk>/revision/check/`

Имя: `warehouse:revision_check`.

Обработчик: `warehouse.revision_views.revision_check`.

Исходник: `warehouse/revision_views.py:48`.

Декораторы: `require_POST`; `permission_required_any(*ACCESS)`.

## `/crm/warehouse/global/`

Имя: `warehouse:global_stock`.

Обработчик: `warehouse.views.global_stock`.

Исходник: `warehouse/views.py:218`.

Декораторы: `permission_required_any('warehouse.view_global_stock', 'catalog.view_cd', 'catalog.view_tech')`.

Прямые шаблоны: `warehouse/global_stock.html`.

## `/crm/warehouse/transfers/`

Имя: `warehouse:transfer_list`.

Обработчик: `warehouse.views.transfer_list`.

Исходник: `warehouse/views.py:387`.

Декораторы: `permission_required_any('warehouse.view_transfers')`.

Прямые шаблоны: `warehouse/transfer_list.html`.

## `/crm/warehouse/transfers/new/`

Имя: `warehouse:transfer_start`.

Обработчик: `warehouse.views.transfer_start`.

Исходник: `warehouse/views.py:406`.

Декораторы: `permission_required_any('warehouse.create_transfer')`.

Прямые шаблоны: `warehouse/transfer_start.html`.

## `/crm/warehouse/transfers/<int:pk>/`

Имя: `warehouse:transfer_detail`.

Обработчик: `warehouse.views.transfer_detail`.

Исходник: `warehouse/views.py:427`.

Декораторы: `permission_required_any('warehouse.view_transfers')`.

Прямые шаблоны: `warehouse/transfer_detail.html`.

## `/crm/warehouse/transfers/<int:pk>/advance/`

Имя: `warehouse:transfer_advance`.

Обработчик: `warehouse.views.transfer_advance`.

Исходник: `warehouse/views.py:508`.

Декораторы: `require_POST`; `permission_required_any('warehouse.mark_transfer_assembled', 'warehouse.mark_transfer_shipped', 'warehouse.mark_transfer_accepted')`.

## `/crm/warehouse/<int:source_pk>/transfers/new/`

Имя: `warehouse:transfer_create`.

Обработчик: `warehouse.views.transfer_create`.

Исходник: `warehouse/views.py:468`.

Декораторы: `permission_required_any('warehouse.create_transfer')`.

Прямые шаблоны: `warehouse/transfer_create.html`.

## `/crm/warehouse/<int:pk>/storage-locations/autocomplete/`

Имя: `warehouse:storage_location_autocomplete`.

Обработчик: `warehouse.views.storage_location_autocomplete`.

Исходник: `warehouse/views.py:283`.

Декораторы: `require_GET`; `permission_required_any('warehouse.view_warehouse_stock', 'catalog.view_cd', 'catalog.view_tech', 'catalog.view_nomenclature')`.

## `/crm/warehouse/<int:pk>/storage-locations/<str:product_type>/<int:product_id>/`

Имя: `warehouse:storage_location_update`.

Обработчик: `warehouse.views.storage_location_update`.

Исходник: `warehouse/views.py:302`.

Декораторы: `require_POST`; `permission_required_any('warehouse.change_storage_location')`.

## `/crm/warehouse/<int:pk>/`

Имя: `warehouse:detail`.

Обработчик: `warehouse.views.warehouse_detail`.

Исходник: `warehouse/views.py:237`.

Декораторы: `permission_required_any('warehouse.view_warehouse_stock', 'catalog.view_cd', 'catalog.view_tech')`.

Прямые шаблоны: `warehouse/detail.html`.

## `/crm/suppliers/partners/`

Имя: `partners:partner_list`.

Обработчик: `partners.partner_views.partner_list`.

Исходник: `partners/partner_views.py:15`.

Декораторы: `permission_required('partners.view_partner', raise_exception=True)`.

Прямые шаблоны: `partners/partner_list.html`.

## `/crm/suppliers/partners/new/`

Имя: `partners:partner_create`.

Обработчик: `partners.partner_views.partner_create`.

Исходник: `partners/partner_views.py:28`.

Декораторы: `permission_required('partners.add_partner', raise_exception=True)`; `permission_required('partners.view_partner_contacts', raise_exception=True)`.

## `/crm/suppliers/partners/<int:pk>/`

Имя: `partners:partner_detail`.

Обработчик: `partners.partner_views.partner_detail`.

Исходник: `partners/partner_views.py:21`.

Декораторы: `permission_required('partners.view_partner', raise_exception=True)`.

Прямые шаблоны: `partners/partner_detail.html`.

## `/crm/suppliers/partners/<int:pk>/edit/`

Имя: `partners:partner_edit`.

Обработчик: `partners.partner_views.partner_edit`.

Исходник: `partners/partner_views.py:34`.

Декораторы: `permission_required('partners.change_partner', raise_exception=True)`; `permission_required('partners.view_partner_contacts', raise_exception=True)`.

## `/crm/suppliers/`

Имя: `partners:list`.

Обработчик: `partners.views.supplier_list`.

Исходник: `partners/views.py:15`.

Декораторы: `permission_required('partners.view_supplier', raise_exception=True)`.

Прямые шаблоны: `partners/supplier_list.html`.

## `/crm/suppliers/new/`

Имя: `partners:create`.

Обработчик: `partners.views.supplier_create`.

Исходник: `partners/views.py:28`.

Декораторы: `permission_required('partners.add_supplier', raise_exception=True)`.

Прямые шаблоны: `partners/supplier_form.html`.

## `/crm/suppliers/<int:pk>/edit/`

Имя: `partners:update`.

Обработчик: `partners.views.supplier_update`.

Исходник: `partners/views.py:42`.

Декораторы: `permission_required('partners.change_supplier', raise_exception=True)`; `permission_required('partners.view_supplier_details', raise_exception=True)`.

Прямые шаблоны: `partners/supplier_form.html`.

## `/crm/supplies/`

Имя: `supplies:list`.

Обработчик: `supplies.views.supply_list`.

Исходник: `supplies/views.py:41`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/list.html`.

## `/crm/supplies/new/`

Имя: `supplies:create`.

Обработчик: `supplies.views.supply_create`.

Исходник: `supplies/views.py:183`.

Декораторы: `permission_required('supplies.add_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/create.html`.

## `/crm/supplies/autocomplete/`

Имя: `supplies:autocomplete`.

Обработчик: `supplies.views.product_autocomplete`.

Исходник: `supplies/views.py:545`.

Декораторы: `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply', 'consignment.transfer_stock', 'consignment.return_stock', 'warehouse.create_transfer', 'sales.create_sale', 'sales.edit_unpaid_postpay_sale')`.

## `/crm/supplies/product-weight/`

Имя: `supplies:product_weight`.

Обработчик: `supplies.views.supply_product_weight`.

Исходник: `supplies/views.py:744`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

## `/crm/supplies/product-codes/`

Имя: `supplies:product_codes`.

Обработчик: `supplies.views.supply_product_codes`.

Исходник: `supplies/views.py:733`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

## `/crm/supplies/product-barcode/`

Имя: `supplies:product_barcode`.

Обработчик: `supplies.views.supply_product_barcode`.

Исходник: `supplies/views.py:768`.

Декораторы: `require_POST`; `permission_required('supplies.add_supply', raise_exception=True)`.

## `/crm/supplies/<int:pk>/cancel/`

Имя: `supplies:cancel`.

Обработчик: `supplies.views.supply_cancel`.

Исходник: `supplies/views.py:525`.

Декораторы: `require_POST`; `permission_required('supplies.cancel_supply', raise_exception=True)`.

## `/crm/supplies/<int:pk>/edit/`

Имя: `supplies:edit`.

Обработчик: `supplies.views.supply_edit`.

Исходник: `supplies/views.py:225`.

Декораторы: `permission_required_any('supplies.add_supply', 'supplies.edit_accepted_supply')`.

Прямые шаблоны: `supplies/create.html`.

## `/crm/supplies/<int:pk>/price-review/`

Имя: `supplies:price_review`.

Обработчик: `supplies.views.supply_price_review`.

Исходник: `supplies/views.py:357`.

Декораторы: `permission_required('supplies.add_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/price_review.html`.

## `/crm/supplies/<int:pk>/finalization/`

Имя: `supplies:finalization`.

Обработчик: `supplies.views.supply_finalization`.

Исходник: `supplies/views.py:425`.

Декораторы: `permission_required('supplies.finalize_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/finalization.html`.

## `/crm/supplies/<int:pk>/finalization/auto/`

Имя: `supplies:finalization_auto`.

Обработчик: `supplies.views.supply_finalization_auto`.

Исходник: `supplies/views.py:461`.

Декораторы: `require_POST`; `permission_required('supplies.finalize_supply', raise_exception=True)`.

## `/crm/supplies/<int:pk>/revisions/<int:revision_number>/`

Имя: `supplies:revision_detail`.

Обработчик: `supplies.views.supply_revision_detail`.

Исходник: `supplies/views.py:495`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/revision_detail.html`.

## `/crm/supplies/<int:pk>/`

Имя: `supplies:detail`.

Обработчик: `supplies.views.supply_detail`.

Исходник: `supplies/views.py:290`.

Декораторы: `permission_required('supplies.view_supply', raise_exception=True)`.

Прямые шаблоны: `supplies/detail.html`.

## `/crm/consignment/platform/<int:pk>/report/`

Имя: `consignment:report_import`.

Обработчик: `consignment.report_views.report_import`.

Исходник: `consignment/report_views.py:18`.

Декораторы: `permission_required_all('sales.create_sale')`.

Прямые шаблоны: `consignment/report_import.html`.

## `/crm/consignment/sales/<int:pk>/partner-payment/`

Имя: `consignment:report_partner_payment`.

Обработчик: `consignment.report_views.report_partner_payment`.

Исходник: `consignment/report_views.py:55`.

Декораторы: `permission_required_all('sales.mark_sale_paid', 'partners.add_partner', 'partners.view_partner_contacts', 'creditors.change_debt')`.

Прямые шаблоны: `consignment/report_partner_payment.html`.

## `/crm/consignment/`

Имя: `consignment:list`.

Обработчик: `consignment.views.consignment_list`.

Исходник: `consignment/views.py:171`.

Декораторы: `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Прямые шаблоны: `consignment/list.html`.

## `/crm/consignment/platform/new/`

Имя: `consignment:platform_create`.

Обработчик: `partners.platform_views.platform_create`.

Исходник: `partners/platform_views.py:12`.

Декораторы: `permission_required('partners.add_salesplatform', raise_exception=True)`.

Прямые шаблоны: `partners/platform_form.html`.

## `/crm/consignment/platform/<int:pk>/`

Имя: `consignment:platform`.

Обработчик: `consignment.views.consignment_platform`.

Исходник: `consignment/views.py:179`.

Декораторы: `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Прямые шаблоны: `consignment/list.html`.

## `/crm/consignment/platform/<int:pk>/export/`

Имя: `consignment:platform_export`.

Обработчик: `consignment.views.platform_export`.

Исходник: `consignment/views.py:190`.

Декораторы: `never_cache`; `require_GET`; `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

## `/crm/consignment/transfer/`

Имя: `consignment:transfer`.

Обработчик: `consignment.views.transfer`.

Исходник: `consignment/views.py:237`.

Декораторы: `permission_required_any('consignment.transfer_stock')`.

Прямые шаблоны: `consignment/transfer.html`.

## `/crm/consignment/return/`

Имя: `consignment:return`.

Обработчик: `consignment.views.return_stock`.

Исходник: `consignment/views.py:262`.

Декораторы: `require_GET`; `permission_required_any('consignment.return_stock')`.

## `/crm/consignment/stocks/<str:product_kind>/<int:pk>/reward/`

Имя: `consignment:reward_update`.

Обработчик: `consignment.views.reward_update`.

Исходник: `consignment/views.py:204`.

Декораторы: `require_POST`; `permission_required_any('consignment.change_consignment_reward')`.

## `/crm/consignment/stocks/<str:product_kind>/<int:pk>/sold/`

Имя: `consignment:sale`.

Обработчик: `consignment.views.consignment_sale`.

Исходник: `consignment/views.py:268`.

Декораторы: `require_GET`; `permission_required_any('sales.create_sale')`.

## `/crm/consignment/stocks/<str:product_kind>/<int:pk>/action/`

Имя: `consignment:row_action`.

Обработчик: `consignment.views.row_action`.

Исходник: `consignment/views.py:294`.

Декораторы: `require_POST`; `permission_required_any('consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

## `/crm/consignment/movements/<int:pk>/`

Имя: `consignment:movement_detail`.

Обработчик: `consignment.views.movement_detail`.

Исходник: `consignment/views.py:323`.

Декораторы: `permission_required_any('catalog.view_nomenclature', 'consignment.view_cdconsignmentstock', 'consignment.view_techconsignmentstock')`.

Прямые шаблоны: `consignment/movement_detail.html`.

## `/crm/pricing/`

Имя: `pricing:list`.

Обработчик: `pricing.views.pricing_list`.

Исходник: `pricing/views.py:89`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/list.html`.

## `/crm/pricing/cd/`

Имя: `pricing:cd_list`.

Обработчик: `pricing.views.pricing_list`.

Исходник: `pricing/views.py:89`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/list.html`.

## `/crm/pricing/tech/`

Имя: `pricing:tech_list`.

Обработчик: `pricing.views.pricing_list`.

Исходник: `pricing/views.py:89`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/list.html`.

## `/crm/pricing/fbs/<str:kind>/<int:pk>/`

Имя: `pricing:fbs_detail`.

Обработчик: `pricing.fbs_views.detail`.

Исходник: `pricing/fbs_views.py:24`.

Декораторы: `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/_fbs_form.html`, `pricing/fbs_detail.html`.

## `/crm/pricing/fbs/<str:kind>/<int:pk>/preview/`

Имя: `pricing:fbs_preview`.

Обработчик: `pricing.fbs_views.preview`.

Исходник: `pricing/fbs_views.py:34`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

## `/crm/pricing/fbs/<str:kind>/<int:pk>/save/`

Имя: `pricing:fbs_save`.

Обработчик: `pricing.fbs_views.save`.

Исходник: `pricing/fbs_views.py:54`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

## `/crm/pricing/avito-check/`

Имя: `pricing:avito_check`.

Обработчик: `pricing.avito_check_views.page`.

Исходник: `pricing/avito_check_views.py:52`.

Декораторы: `require_GET`; `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/avito_check_list.html`.

## `/crm/pricing/avito-check/automatic/`

Имя: `pricing:avito_check_automatic`.

Обработчик: `pricing.avito_check_views.automatic_page`.

Исходник: `pricing/avito_check_views.py:140`.

Декораторы: `require_GET`; `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/avito_check.html`, `pricing/avito_check_complete.html`.

## `/crm/pricing/avito-check/found-price/`

Имя: `pricing:avito_check_found_price`.

Обработчик: `pricing.avito_check_views.save_found_price`.

Исходник: `pricing/avito_check_views.py:97`.

Декораторы: `require_POST`; `permission_required_all('pricing.view_pricing', 'pricing.change_retail_price')`.

## `/crm/pricing/avito-check/manual-context/`

Имя: `pricing:avito_check_manual_context`.

Обработчик: `pricing.avito_check_views.manual_context`.

Исходник: `pricing/avito_check_views.py:77`.

Декораторы: `require_GET`; `never_cache`; `permission_required_all('pricing.view_pricing', 'pricing.change_retail_price')`.

## `/crm/pricing/avito-check/next/`

Имя: `pricing:avito_check_next`.

Обработчик: `pricing.avito_check_views.next_product`.

Исходник: `pricing/avito_check_views.py:167`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/avito_check.html`.

## `/crm/pricing/avito-check/check/`

Имя: `pricing:avito_check_run`.

Обработчик: `pricing.avito_check_views.check_product`.

Исходник: `pricing/avito_check_views.py:198`.

Декораторы: `require_POST`; `permission_required_any('pricing.view_pricing')`.

Прямые шаблоны: `pricing/_avito_check_results.html`.

## `/crm/pricing/product/update/`

Имя: `pricing:product_update`.

Обработчик: `pricing.views.product_prices_update`.

Исходник: `pricing/views.py:163`.

Декораторы: `require_POST`; `permission_required_any('pricing.change_retail_price', 'pricing.change_wholesale_price', 'pricing.change_yandex_market_price')`.

## `/crm/pricing/supplier/update/`

Имя: `pricing:supplier_update`.

Обработчик: `pricing.views.supplier_price_update`.

Исходник: `pricing/views.py:241`.

Декораторы: `require_POST`; `permission_required_any('pricing.change_supplier_prices')`.

## `/crm/price/`

Имя: `price:index`.

Обработчик: `price.views.price_page`.

Исходник: `price/views.py:66`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Прямые шаблоны: `price/index.html`.

## `/crm/price/sites/`

Имя: `price:site_links`.

Обработчик: `price.views.site_links`.

Исходник: `price/views.py:110`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Прямые шаблоны: `price/site_links.html`.

## `/crm/price/imports/`

Имя: `price:imports`.

Обработчик: `price.views.import_prices`.

Исходник: `price/views.py:81`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Прямые шаблоны: `price/imports.html`.

## `/crm/price/settings/`

Имя: `price:settings_update`.

Обработчик: `price.views.document_settings_update`.

Исходник: `price/views.py:131`.

Декораторы: `require_POST`; `permission_required_any('price.change_document_settings')`.

## `/crm/price/retail.xlsx`

Имя: `price:retail_export`.

Обработчик: `price.views.retail_export`.

Исходник: `price/views.py:144`.

Декораторы: `require_POST`; `permission_required_any('price.generate_retail_price')`.

## `/crm/price/wholesale.xlsx`

Имя: `price:wholesale_export`.

Обработчик: `price.views.wholesale_export`.

Исходник: `price/views.py:159`.

Декораторы: `require_POST`; `permission_required_any('price.generate_wholesale_price')`.

## `/crm/price/supplier-template.xlsx`

Имя: `price:supplier_template`.

Обработчик: `price.views.supplier_template_export`.

Исходник: `price/views.py:176`.

Декораторы: `require_GET`; `permission_required_any('price.download_supplier_template')`.

## `/crm/price/supplier-template/<str:product_kind>.xlsx`

Имя: `price:supplier_template_kind`.

Обработчик: `price.views.supplier_template_export`.

Исходник: `price/views.py:176`.

Декораторы: `require_GET`; `permission_required_any('price.download_supplier_template')`.

## `/crm/price/supplier/<int:supplier_id>/template/<str:product_kind>.xlsx`

Имя: `price:supplier_template_prefilled`.

Обработчик: `price.views.supplier_template_prefilled_export`.

Исходник: `price/views.py:189`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all('price.download_supplier_template', 'price.view_supplier_prices')`.

## `/crm/price/supplier/upload/`

Имя: `price:supplier_upload`.

Обработчик: `price.views.supplier_price_upload`.

Исходник: `price/views.py:204`.

Декораторы: `require_POST`; `permission_required_any('price.upload_supplier_price')`.

## `/crm/price/procurement/create/`

Имя: `price:procurement_create`.

Обработчик: `price.views.procurement_create`.

Исходник: `price/views.py:229`.

Декораторы: `require_POST`; `permission_required_any('price.create_procurement_price_list')`.

Прямые шаблоны: `price/procurement_prepare.html`.

## `/crm/price/procurement/<int:pk>/`

Имя: `price:procurement_detail`.

Обработчик: `price.views.procurement_detail`.

Исходник: `price/views.py:283`.

Декораторы: `require_GET`; `permission_required_any('price.view_price_page')`.

Прямые шаблоны: `price/procurement_detail.html`.

## `/crm/price/procurement/<int:pk>/stock.xlsx`

Имя: `price:procurement_stock_export`.

Обработчик: `price.views.procurement_stock_export`.

Исходник: `price/views.py:378`.

Декораторы: `require_GET`; `permission_required_all('price.export_procurement_price_list', 'price.view_supplier_prices')`.

## `/crm/price/procurement/<int:pk>/update/`

Имя: `price:procurement_update`.

Обработчик: `price.views.procurement_update`.

Исходник: `price/views.py:315`.

Декораторы: `require_POST`; `permission_required_any('price.change_procurement_markup', 'price.change_procurement_delivery')`.

Прямые шаблоны: `price/procurement_confirm.html`.

## `/crm/price/procurement/<int:pk>/customer.xlsx`

Имя: `price:procurement_export`.

Обработчик: `price.views.procurement_export`.

Исходник: `price/views.py:367`.

Декораторы: `require_GET`; `permission_required_any('price.export_procurement_price_list')`.

## `/crm/price/procurement/<int:pk>/customer/<str:product_kind>.xlsx`

Имя: `price:procurement_export_kind`.

Обработчик: `price.views.procurement_export`.

Исходник: `price/views.py:367`.

Декораторы: `require_GET`; `permission_required_any('price.export_procurement_price_list')`.

## `/crm/sales/avito-extension/`

Имя: `sales:avito_bridge`.

Обработчик: `sales.avito_order_views.bridge`.

Исходник: `sales/avito_order_views.py:19`.

Декораторы: `never_cache`; `permission_required_any('sales.create_sale')`; `require_http_methods(['GET', 'POST'])`.

Прямые шаблоны: `sales/avito_bridge.html`.

## `/crm/sales/avito-orders/<int:pk>/create/`

Имя: `sales:avito_create`.

Обработчик: `sales.avito_order_views.create`.

Исходник: `sales/avito_order_views.py:69`.

Декораторы: `permission_required_any('sales.create_sale')`.

Прямые шаблоны: `sales/create.html`.

## `/crm/sales/partner-settlement/preview/`

Имя: `sales:settlement_preview`.

Обработчик: `sales.partner_views.settlement_preview`.

Исходник: `sales/partner_views.py:15`.

Декораторы: `never_cache`; `require_POST`; `permission_required_any('sales.create_sale', 'sales.mark_sale_paid')`.

## `/crm/sales/`

Имя: `sales:list`.

Обработчик: `sales.views.sale_list`.

Исходник: `sales/views.py:165`.

Декораторы: `permission_required_any('sales.view_sales')`.

## `/crm/sales/incomplete/`

Имя: `sales:incomplete`.

Обработчик: `sales.views.sale_list`.

Исходник: `sales/views.py:165`.

Декораторы: `permission_required_any('sales.view_sales')`.

## `/crm/sales/completed/`

Имя: `sales:completed`.

Обработчик: `sales.views.sale_completed_list`.

Исходник: `sales/views.py:177`.

Декораторы: `permission_required_all('sales.view_sales', 'sales.view_completed_sales')`.

## `/crm/sales/cancelled/`

Имя: `sales:cancelled`.

Обработчик: `sales.views.sale_cancelled_list`.

Исходник: `sales/views.py:182`.

Декораторы: `permission_required_any('sales.view_sales')`.

## `/crm/sales/market-pending/`

Имя: `sales:market_pending`.

Обработчик: `sales.notification_views.pending_orders`.

Исходник: `sales/notification_views.py:17`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales')`.

Прямые шаблоны: `sales/market_pending.html`.

## `/crm/sales/market-notifications/`

Имя: `sales:market_notifications`.

Обработчик: `sales.notification_views.notification_status`.

Исходник: `sales/notification_views.py:26`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales')`.

## `/crm/sales/market-notifications/<int:attention_id>/acknowledge/`

Имя: `sales:market_acknowledge`.

Обработчик: `sales.notification_views.acknowledge`.

Исходник: `sales/notification_views.py:37`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all('sales.view_sales', 'yandex_market.manage_orders')`.

## `/crm/sales/<int:pk>/status/`

Имя: `sales:inline_status`.

Обработчик: `sales.views.sale_inline_status`.

Исходник: `sales/views.py:202`.

Декораторы: `require_POST`; `permission_required_any('sales.view_sales')`.

## `/crm/sales/<int:pk>/market-action/`

Имя: `sales:market_action`.

Обработчик: `sales.market_views.sale_market_action`.

Исходник: `sales/market_views.py:33`.

Декораторы: `require_POST`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.manage_orders')`.

## `/crm/sales/market-scan/`

Имя: `sales:market_scan`.

Обработчик: `sales.market_views.sale_market_scan`.

Исходник: `sales/market_views.py:114`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales')`; `permission_required_any('yandex_market.print_labels')`; `permission_required_any('yandex_market.manage_orders')`.

## `/crm/sales/<int:pk>/market-print/`

Имя: `sales:market_print`.

Обработчик: `sales.market_views.sale_market_print`.

Исходник: `sales/market_views.py:131`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

## `/crm/sales/market-print/<uuid:request_id>/`

Имя: `sales:market_print_status`.

Обработчик: `sales.market_views.sale_market_print_status`.

Исходник: `sales/market_views.py:146`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

## `/crm/sales/market-print/<uuid:request_id>/resolve/`

Имя: `sales:print_resolve`.

Обработчик: `sales.market_views.print_resolve`.

Исходник: `sales/market_views.py:155`.

Декораторы: `require_POST`; `permission_required_any('yandex_market.print_labels')`.

## `/crm/sales/<int:pk>/market-label/`

Имя: `sales:market_label`.

Обработчик: `sales.market_views.sale_market_label`.

Исходник: `sales/market_views.py:58`.

Декораторы: `require_POST`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

## `/crm/sales/<int:pk>/market-label/<int:document_id>/`

Имя: `sales:market_label_status`.

Обработчик: `sales.market_views.sale_market_label_status`.

Исходник: `sales/market_views.py:86`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('sales.view_sales', 'sales.view_sale_detail')`; `permission_required_any('yandex_market.print_labels')`.

## `/crm/sales/new/`

Имя: `sales:create`.

Обработчик: `sales.views.sale_create`.

Исходник: `sales/views.py:242`.

Декораторы: `permission_required_any('sales.create_sale')`.

Прямые шаблоны: `sales/create.html`.

## `/crm/sales/new/import-wholesale/`

Имя: `sales:import_wholesale`.

Обработчик: `sales.views.sale_wholesale_import`.

Исходник: `sales/views.py:315`.

Декораторы: `permission_required_all('sales.create_sale', 'sales.import_wholesale_price')`.

Прямые шаблоны: `sales/import_wholesale.html`.

## `/crm/sales/<int:pk>/`

Имя: `sales:detail`.

Обработчик: `sales.views.sale_detail`.

Исходник: `sales/views.py:347`.

Декораторы: `permission_required_any('sales.view_sale_detail')`.

Прямые шаблоны: `sales/detail.html`.

## `/crm/sales/<int:pk>/invoice/`

Имя: `sales:invoice`.

Обработчик: `sales.views.sale_invoice`.

Исходник: `sales/views.py:426`.

Декораторы: `require_GET`; `permission_required_any('sales.view_sale_detail')`.

## `/crm/sales/<int:pk>/edit/`

Имя: `sales:edit`.

Обработчик: `sales.views.sale_edit`.

Исходник: `sales/views.py:465`.

Декораторы: `permission_required_any('sales.edit_unpaid_postpay_sale')`.

Прямые шаблоны: `sales/edit.html`.

## `/crm/sales/<int:pk>/advance/`

Имя: `sales:advance`.

Обработчик: `sales.views.sale_advance`.

Исходник: `sales/views.py:520`.

Декораторы: `require_POST`; `permission_required_any('sales.advance_order_status')`.

## `/crm/sales/<int:pk>/payment-method/`

Имя: `sales:payment_method`.

Обработчик: `sales.views.sale_payment_method`.

Исходник: `sales/views.py:533`.

Декораторы: `require_POST`; `permission_required_any('sales.mark_sale_paid')`.

## `/crm/sales/<int:pk>/mark-paid/`

Имя: `sales:mark_paid`.

Обработчик: `sales.views.sale_mark_paid`.

Исходник: `sales/views.py:546`.

Декораторы: `require_POST`; `permission_required_any('sales.mark_sale_paid')`.

## `/crm/sales/<int:pk>/note/`

Имя: `sales:note_update`.

Обработчик: `sales.views.sale_note_update`.

Исходник: `sales/views.py:572`.

Декораторы: `require_POST`; `permission_required_any('sales.change_sale')`.

## `/crm/sales/<int:pk>/cancel/`

Имя: `sales:cancel`.

Обработчик: `sales.views.sale_cancel`.

Исходник: `sales/views.py:587`.

Декораторы: `require_POST`; `permission_required_any('sales.cancel_sale')`.

## `/crm/statistics/`

Имя: `statistics:index`.

Обработчик: `sales.statistics_views.statistics_index`.

Исходник: `sales/statistics_views.py:27`.

Декораторы: `permission_required_any('sales.view_sales_statistics')`.

Прямые шаблоны: `sales/statistics.html`.

## `/crm/statistics/export/`

Имя: `statistics:export`.

Обработчик: `sales.statistics_views.statistics_export`.

Исходник: `sales/statistics_views.py:49`.

Декораторы: `permission_required_all('sales.view_sales_statistics', 'sales.export_sales_statistics')`.

## `/crm/orders/trips/new/`

Имя: `orders:trip_empty_create`.

Обработчик: `orders.trip_views.trip_empty_create`.

Исходник: `orders/trip_views.py:34`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Прямые шаблоны: `orders/trip_empty_create.html`.

## `/crm/orders/trips/<int:pk>/orders/add/`

Имя: `orders:trip_add_orders`.

Обработчик: `orders.trip_views.trip_add_orders`.

Исходник: `orders/trip_views.py:49`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Прямые шаблоны: `orders/trip_add_orders.html`.

## `/crm/orders/trips/<int:pk>/arrival/`

Имя: `orders:trip_arrival`.

Обработчик: `orders.arrival_views.update_arrival`.

Исходник: `orders/arrival_views.py:44`.

Декораторы: `require_POST`; `permission_required_any('orders.generate_supplier_orders')`.

## `/crm/orders/trips/<int:pk>/finalization/`

Имя: `orders:arrival_finalization`.

Обработчик: `orders.arrival_views.finalization`.

Исходник: `orders/arrival_views.py:210`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('supplies.finalize_supply')`.

Прямые шаблоны: `orders/arrival_finalization.html`.

## `/crm/orders/trips/<int:pk>/finalization/auto/`

Имя: `orders:arrival_finalization_auto`.

Обработчик: `orders.arrival_views.finalization_auto`.

Исходник: `orders/arrival_views.py:235`.

Декораторы: `require_POST`; `permission_required_any('supplies.finalize_supply')`.

## `/crm/orders/trip-supplies/<int:pk>/post/`

Имя: `orders:arrival_supply_post`.

Обработчик: `orders.arrival_views.post_supply`.

Исходник: `orders/arrival_views.py:254`.

Декораторы: `require_POST`; `permission_required_any('supplies.add_supply')`.

## `/crm/orders/<int:pk>/receipt/`

Имя: `orders:arrival_receipt`.

Обработчик: `orders.arrival_views.receipt`.

Исходник: `orders/arrival_views.py:103`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('orders.view_order_detail')`.

Прямые шаблоны: `orders/arrival_receipt.html`.

## `/crm/orders/<int:pk>/operation/`

Имя: `orders:operation_prepare`.

Обработчик: `orders.fulfillment_views.prepare`.

Исходник: `orders/fulfillment_views.py:58`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_any('orders.view_order_detail')`.

## `/crm/orders/trips/<int:pk>/additional/`

Имя: `orders:trip_addition`.

Обработчик: `orders.trip_addition_views.addition`.

Исходник: `orders/trip_addition_views.py:92`.

Декораторы: `never_cache`; `permission_required_all(*PERMISSIONS)`.

Прямые шаблоны: `orders/trip_addition.html`.

## `/crm/orders/trips/<int:pk>/additional/search/`

Имя: `orders:trip_addition_search`.

Обработчик: `orders.trip_addition_views.product_search`.

Исходник: `orders/trip_addition_views.py:76`.

Декораторы: `never_cache`; `permission_required_all(*PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/additional/calculation/`

Имя: `orders:trip_addition_calculation`.

Обработчик: `orders.trip_addition_views.calculation`.

Исходник: `orders/trip_addition_views.py:53`.

Декораторы: `never_cache`; `require_POST`; `permission_required_all(*PERMISSIONS)`.

## `/crm/orders/`

Имя: `orders:list`.

Обработчик: `orders.views.order_list`.

Исходник: `orders/views.py:71`.

Декораторы: `require_GET`; `permission_required_any('orders.view_orders')`.

Прямые шаблоны: `orders/list.html`.

## `/crm/orders/new/`

Имя: `orders:upload`.

Обработчик: `orders.views.order_upload`.

Исходник: `orders/views.py:105`.

Декораторы: `permission_required_any('orders.create_order')`.

Прямые шаблоны: `orders/upload.html`.

## `/crm/orders/new/stock/`

Имя: `orders:stock_create`.

Обработчик: `orders.stock_order_views.stock_order_create`.

Исходник: `orders/stock_order_views.py:15`.

Декораторы: `never_cache`; `require_http_methods(['GET', 'POST'])`; `permission_required_all('orders.create_order', 'price.view_supplier_prices')`.

Прямые шаблоны: `orders/stock_create.html`.

## `/crm/orders/new/preview/`

Имя: `orders:preview`.

Обработчик: `orders.views.order_preview`.

Исходник: `orders/views.py:177`.

Декораторы: `permission_required_any('orders.create_order')`.

Прямые шаблоны: `orders/preview.html`.

## `/crm/orders/<int:pk>/`

Имя: `orders:detail`.

Обработчик: `orders.views.order_detail`.

Исходник: `orders/views.py:218`.

Декораторы: `require_GET`; `permission_required_any('orders.view_order_detail')`.

Прямые шаблоны: `orders/detail.html`.

## `/crm/orders/<int:pk>/export/`

Имя: `orders:export`.

Обработчик: `orders.views.order_export`.

Исходник: `orders/views.py:130`.

Декораторы: `never_cache`; `require_GET`; `permission_required_any('orders.view_order_detail')`.

## `/crm/orders/<int:pk>/export/suppliers/`

Имя: `orders:export_suppliers`.

Обработчик: `orders.views.order_suppliers_export`.

Исходник: `orders/views.py:147`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all('orders.view_order_detail', 'price.view_supplier_prices')`.

## `/crm/orders/<int:pk>/edit/`

Имя: `orders:edit`.

Обработчик: `orders.views.order_edit`.

Исходник: `orders/views.py:281`.

Декораторы: `permission_required_any('orders.edit_created_order')`.

Прямые шаблоны: `orders/edit.html`.

## `/crm/orders/<int:pk>/trip/`

Имя: `orders:assign_trip`.

Обработчик: `orders.trip_views.order_trip_assign`.

Исходник: `orders/trip_views.py:89`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `permission_required_all(*MANAGE_PERMISSIONS)`.

Прямые шаблоны: `orders/trip_assign.html`.

## `/crm/orders/<int:pk>/confirm/`

Имя: `orders:confirm`.

Обработчик: `orders.views.order_confirm`.

Исходник: `orders/views.py:316`.

Декораторы: `require_POST`; `permission_required_any('orders.confirm_order')`.

## `/crm/orders/<int:pk>/receiving/`

Имя: `orders:start_receiving`.

Обработчик: `orders.views.order_start_receiving`.

Исходник: `orders/views.py:338`.

Декораторы: `require_POST`; `permission_required_any('orders.start_receiving')`.

## `/crm/orders/<int:pk>/adjust/`

Имя: `orders:adjust`.

Обработчик: `orders.views.order_adjust`.

Исходник: `orders/views.py:354`.

Декораторы: `permission_required_any('orders.edit_receiving_order')`.

Прямые шаблоны: `orders/adjust.html`.

## `/crm/orders/<int:pk>/complete/`

Имя: `orders:complete`.

Обработчик: `orders.views.order_complete`.

Исходник: `orders/views.py:378`.

Декораторы: `require_POST`; `permission_required_any('orders.complete_order')`.

## `/crm/orders/supplier-batches/create/`

Имя: `orders:supplier_batch_create`.

Обработчик: `orders.views.supplier_batch_create`.

Исходник: `orders/views.py:404`.

Декораторы: `require_POST`; `permission_required_all('orders.generate_supplier_orders', 'partners.view_supplier_details', 'orders.edit_created_order', 'price.view_supplier_prices')`.

## `/crm/orders/supplier-batches/<int:pk>/`

Имя: `orders:supplier_batch_detail`.

Обработчик: `orders.views.supplier_batch_detail`.

Исходник: `orders/views.py:411`.

Декораторы: `require_GET`; `permission_required_all('orders.generate_supplier_orders', 'partners.view_supplier_details')`.

Прямые шаблоны: `orders/supplier_batch_detail.html`.

## `/crm/orders/trips/create/`

Имя: `orders:trip_create`.

Обработчик: `orders.trip_views.trip_create`.

Исходник: `orders/trip_views.py:76`.

Декораторы: `require_POST`; `permission_required_all(*MANAGE_PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/`

Имя: `orders:trip_detail`.

Обработчик: `orders.trip_views.trip_detail`.

Исходник: `orders/trip_views.py:116`.

Декораторы: `require_GET`; `permission_required_all(*VIEW_PERMISSIONS)`.

Прямые шаблоны: `orders/trip_detail.html`.

## `/crm/orders/trips/<int:pk>/suppliers/<int:supplier_pk>/invoice/`

Имя: `orders:trip_invoice_update`.

Обработчик: `orders.trip_invoice_views.invoice_update`.

Исходник: `orders/trip_invoice_views.py:13`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/export/`

Имя: `orders:trip_full_export`.

Обработчик: `orders.trip_views.trip_full_export`.

Исходник: `orders/trip_views.py:213`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all(*VIEW_PERMISSIONS, 'price.view_supplier_prices')`.

## `/crm/orders/trips/<int:pk>/lines/<int:line_pk>/`

Имя: `orders:trip_line_update`.

Обработчик: `orders.trip_views.trip_line_update`.

Исходник: `orders/trip_views.py:191`.

Декораторы: `require_POST`; `permission_required_all(*MANAGE_PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/lines/<int:line_pk>/price/preview/`

Имя: `orders:trip_price_preview`.

Обработчик: `orders.trip_price_views.preview`.

Исходник: `orders/trip_price_views.py:35`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/lines/<int:line_pk>/price/`

Имя: `orders:trip_price_update`.

Обработчик: `orders.trip_price_views.update`.

Исходник: `orders/trip_price_views.py:42`.

Декораторы: `require_POST`; `never_cache`; `permission_required_all(*MANAGE_PERMISSIONS)`.

## `/crm/orders/trips/<int:pk>/suppliers/<int:supplier_pk>/export/`

Имя: `orders:trip_export`.

Обработчик: `orders.trip_views.trip_export`.

Исходник: `orders/trip_views.py:229`.

Декораторы: `never_cache`; `require_GET`; `permission_required_all(*VIEW_PERMISSIONS)`.

## `/crm/cash/<int:warehouse_pk>/`

Имя: `cash:register`.

Обработчик: `cash.views.register_detail`.

Исходник: `cash/views.py:42`.

Декораторы: `permission_required_any('cash.view_cash_register', 'cash.view_cash_history', 'cash.view_safe')`.

Прямые шаблоны: `cash/register.html`.

## `/crm/cash/<int:warehouse_pk>/deposit/`

Имя: `cash:deposit`.

Обработчик: `cash.views.deposit`.

Исходник: `cash/views.py:116`.

Декораторы: `permission_required_any('cash.deposit_cash')`.

## `/crm/cash/<int:warehouse_pk>/collect/`

Имя: `cash:collect`.

Обработчик: `cash.views.collect`.

Исходник: `cash/views.py:123`.

Декораторы: `permission_required_any('cash.collect_cash')`.

## `/crm/cash/<int:warehouse_pk>/safe/deposit/`

Имя: `cash:safe_deposit`.

Обработчик: `cash.views.safe_deposit`.

Исходник: `cash/views.py:130`.

Декораторы: `permission_required_any('cash.deposit_safe')`.

## `/crm/cash/<int:warehouse_pk>/safe/collect/`

Имя: `cash:safe_collect`.

Обработчик: `cash.views.safe_collect`.

Исходник: `cash/views.py:139`.

Декораторы: `permission_required_any('cash.collect_safe')`.

## `/crm/cash/<int:warehouse_pk>/transfer/cash-to-safe/`

Имя: `cash:cash_to_safe`.

Обработчик: `cash.views.cash_to_safe`.

Исходник: `cash/views.py:148`.

Декораторы: `permission_required_any('cash.transfer_cash_to_safe')`.

## `/crm/cash/<int:warehouse_pk>/transfer/safe-to-cash/`

Имя: `cash:safe_to_cash`.

Обработчик: `cash.views.safe_to_cash`.

Исходник: `cash/views.py:157`.

Декораторы: `permission_required_any('cash.transfer_safe_to_cash')`.

## `/crm/creditors/`

Имя: `creditors:list`.

Обработчик: `creditors.views.creditor_list`.

Исходник: `creditors/views.py:20`.

Декораторы: `permission_required_any('creditors.view_creditors')`.

Прямые шаблоны: `creditors/list.html`.

## `/crm/creditors/new/`

Имя: `creditors:create`.

Обработчик: `creditors.views.creditor_create`.

Исходник: `creditors/views.py:36`.

Декораторы: `permission_required_any('creditors.add_creditor')`.

Прямые шаблоны: `creditors/form.html`.

## `/crm/creditors/<int:pk>/`

Имя: `creditors:detail`.

Обработчик: `creditors.views.creditor_detail`.

Исходник: `creditors/views.py:47`.

Декораторы: `permission_required_any('creditors.view_creditors')`.

Прямые шаблоны: `creditors/detail.html`.

## `/crm/creditors/<int:pk>/edit/`

Имя: `creditors:edit`.

Обработчик: `creditors.views.creditor_edit`.

Исходник: `creditors/views.py:60`.

Декораторы: `permission_required_any('creditors.change_creditor')`.

Прямые шаблоны: `creditors/form.html`.

## `/crm/creditors/<int:pk>/debt/`

Имя: `creditors:debt`.

Обработчик: `creditors.views.creditor_debt`.

Исходник: `creditors/views.py:78`.

Декораторы: `permission_required_any('creditors.change_debt')`.

Прямые шаблоны: `creditors/debt.html`.

## `/crm/nomenclature/`

Имя: `nomenclature:list`.

Обработчик: `catalog.nomenclature_views.nomenclature_list`.

Исходник: `catalog/nomenclature_views.py:46`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Прямые шаблоны: `nomenclature/list.html`.

## `/crm/nomenclature/cd/`

Имя: `nomenclature:cd_list`.

Обработчик: `catalog.nomenclature_views.nomenclature_list`.

Исходник: `catalog/nomenclature_views.py:46`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Прямые шаблоны: `nomenclature/list.html`.

## `/crm/nomenclature/tech/`

Имя: `nomenclature:tech_list`.

Обработчик: `catalog.nomenclature_views.nomenclature_list`.

Исходник: `catalog/nomenclature_views.py:46`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

Прямые шаблоны: `nomenclature/list.html`.

## `/crm/nomenclature/new/`

Имя: `nomenclature:create`.

Обработчик: `catalog.nomenclature_views.product_create`.

Исходник: `catalog/nomenclature_views.py:160`.

Декораторы: `permission_required_any('catalog.add_cd', 'catalog.add_tech')`.

Прямые шаблоны: `nomenclature/create.html`.

## `/crm/nomenclature/bulk-delete/`

Имя: `nomenclature:bulk_delete`.

Обработчик: `catalog.nomenclature_views.product_bulk_delete`.

Исходник: `catalog/nomenclature_views.py:126`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`; `permission_required_any('catalog.delete_cd', 'catalog.delete_tech')`.

## `/crm/nomenclature/cd/<int:pk>/`

Имя: `nomenclature:cd_detail`.

Обработчик: `catalog.nomenclature_views.cd_detail`.

Исходник: `catalog/nomenclature_views.py:377`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/tech/<int:pk>/`

Имя: `nomenclature:tech_detail`.

Обработчик: `catalog.nomenclature_views.tech_detail`.

Исходник: `catalog/nomenclature_views.py:382`.

Декораторы: `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/title/`

Имя: `nomenclature:product_title_image`.

Обработчик: `catalog.nomenclature_views.product_title_image`.

Исходник: `catalog/nomenclature_views.py:421`.

Декораторы: `require_GET`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/title/upload/`

Имя: `nomenclature:product_title_upload`.

Обработчик: `catalog.nomenclature_views.product_title_upload`.

Исходник: `catalog/nomenclature_views.py:453`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/title/delete/`

Имя: `nomenclature:product_title_delete`.

Обработчик: `catalog.nomenclature_views.product_title_delete`.

Исходник: `catalog/nomenclature_views.py:473`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/images/upload/`

Имя: `nomenclature:product_gallery_upload`.

Обработчик: `catalog.nomenclature_views.product_gallery_upload`.

Исходник: `catalog/nomenclature_views.py:490`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/images/<int:image_id>/`

Имя: `nomenclature:product_gallery_image`.

Обработчик: `catalog.nomenclature_views.product_gallery_image`.

Исходник: `catalog/nomenclature_views.py:435`.

Декораторы: `require_GET`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/media/images/<int:image_id>/delete/`

Имя: `nomenclature:product_gallery_delete`.

Обработчик: `catalog.nomenclature_views.product_gallery_delete`.

Исходник: `catalog/nomenclature_views.py:511`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/delete/`

Имя: `nomenclature:product_delete`.

Обработчик: `catalog.nomenclature_views.product_delete`.

Исходник: `catalog/nomenclature_views.py:531`.

Декораторы: `require_POST`; `permission_required_any('catalog.view_nomenclature')`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/barcode/generate/`

Имя: `nomenclature:barcode_generate`.

Обработчик: `catalog.nomenclature_views.barcode_generate`.

Исходник: `catalog/nomenclature_views.py:556`.

Декораторы: `require_POST`; `permission_required_any('catalog.change_cd_barcode', 'catalog.change_tech_barcode')`.

## `/crm/nomenclature/barcode/<int:barcode_id>/print/`

Имя: `nomenclature:barcode_print`.

Обработчик: `catalog.nomenclature_views.barcode_print`.

Исходник: `catalog/nomenclature_views.py:575`.

Декораторы: `require_GET`; `permission_required_any('catalog.view_nomenclature')`.

Прямые шаблоны: `nomenclature/barcode_print.html`.

## `/crm/nomenclature/<str:product_kind>/<int:pk>/barcode/print/`

Имя: `nomenclature:barcode_print`.

Обработчик: `catalog.nomenclature_views.barcode_print_legacy`.

Исходник: `catalog/nomenclature_views.py:588`.

Декораторы: `require_GET`; `permission_required_any('catalog.view_nomenclature')`.

Прямые шаблоны: `nomenclature/barcode_print.html`.

## `/crm/integrations/yandex/`

Имя: `yandex_market:dashboard`.

Обработчик: `yandex_market.views.dashboard`.

Исходник: `yandex_market/views.py:65`.

Декораторы: `access()`.

Прямые шаблоны: `yandex_market/dashboard.html`.

## `/crm/integrations/yandex/settings/new/`

Имя: `yandex_market:settings_new`.

Обработчик: `yandex_market.views.settings_view`.

Исходник: `yandex_market/views.py:129`.

Декораторы: `access('manage_settings')`; `sensitive_post_parameters('new_api_key')`.

Прямые шаблоны: `yandex_market/settings.html`.

## `/crm/integrations/yandex/settings/<int:pk>/`

Имя: `yandex_market:settings`.

Обработчик: `yandex_market.views.settings_view`.

Исходник: `yandex_market/views.py:129`.

Декораторы: `access('manage_settings')`; `sensitive_post_parameters('new_api_key')`.

Прямые шаблоны: `yandex_market/settings.html`.

## `/crm/integrations/yandex/settings/<int:pk>/pricing/`

Имя: `yandex_market:pricing_settings`.

Обработчик: `yandex_market.pricing_views.settings_view`.

Исходник: `yandex_market/pricing_views.py:13`.

Декораторы: `access('manage_settings')`.

Прямые шаблоны: `yandex_market/pricing_settings.html`.

## `/crm/integrations/yandex/settings/<int:pk>/check/`

Имя: `yandex_market:check`.

Обработчик: `yandex_market.views.check`.

Исходник: `yandex_market/views.py:173`.

Декораторы: `access('manage_settings', post=True)`.

## `/crm/integrations/yandex/sync/<int:pk>/`

Имя: `yandex_market:sync`.

Обработчик: `yandex_market.views.synchronize`.

Исходник: `yandex_market/views.py:182`.

Декораторы: `access('retry_sync', post=True)`.

## `/crm/integrations/yandex/offers/<int:pk>/bind/`

Имя: `yandex_market:bind`.

Обработчик: `yandex_market.views.bind`.

Исходник: `yandex_market/views.py:195`.

Декораторы: `access('bind_offer')`.

Прямые шаблоны: `yandex_market/bind.html`.

## `/crm/integrations/yandex/offers/new/`

Имя: `yandex_market:new_offer`.

Обработчик: `yandex_market.views.new_offer`.

Исходник: `yandex_market/views.py:239`.

Декораторы: `access('bind_offer', post=True)`.

## `/crm/integrations/yandex/products/<int:pk>/`

Имя: `yandex_market:connection`.

Обработчик: `yandex_market.views.connection_detail`.

Исходник: `yandex_market/views.py:260`.

Декораторы: `access()`.

Прямые шаблоны: `yandex_market/connection.html`.

## `/crm/integrations/yandex/products/<int:pk>/categories/`

Имя: `yandex_market:categories`.

Обработчик: `yandex_market.views.categories`.

Исходник: `yandex_market/views.py:150`.

Декораторы: `access('edit_content')`.

Прямые шаблоны: `yandex_market/categories.html`.

## `/crm/integrations/yandex/products/<int:pk>/action/`

Имя: `yandex_market:content_action`.

Обработчик: `yandex_market.views.content_action`.

Исходник: `yandex_market/views.py:299`.

Декораторы: `access('edit_content', post=True)`.

## `/crm/integrations/yandex/products/<int:pk>/unlink/`

Имя: `yandex_market:unlink`.

Обработчик: `yandex_market.views.unlink`.

Исходник: `yandex_market/views.py:380`.

Декораторы: `access('rebind_offer', post=True)`.

## `/crm/integrations/yandex/orders/<int:pk>/`

Имя: `yandex_market:order`.

Обработчик: `yandex_market.views.order_detail`.

Исходник: `yandex_market/views.py:388`.

Декораторы: `access()`.

Прямые шаблоны: `yandex_market/order.html`.

## `/crm/integrations/yandex/orders/<int:pk>/action/`

Имя: `yandex_market:order_action`.

Обработчик: `yandex_market.views.order_action`.

Исходник: `yandex_market/views.py:395`.

Декораторы: `access('manage_orders', post=True)`.

## `/crm/integrations/yandex/returns/<int:pk>/accept/`

Имя: `yandex_market:return_accept`.

Обработчик: `yandex_market.views.return_accept`.

Исходник: `yandex_market/views.py:411`.

Декораторы: `access('accept_return', post=True)`.

## `/crm/integrations/yandex/labels/request/`

Имя: `yandex_market:label_request`.

Обработчик: `yandex_market.views.label_request`.

Исходник: `yandex_market/views.py:421`.

Декораторы: `access('print_labels', post=True)`.

## `/crm/integrations/yandex/labels/<int:pk>/`

Имя: `yandex_market:label`.

Обработчик: `yandex_market.views.label_detail`.

Исходник: `yandex_market/views.py:437`.

Декораторы: `access('print_labels')`.

Прямые шаблоны: `yandex_market/label.html`.

## `/crm/integrations/yandex/labels/<int:pk>/file/`

Имя: `yandex_market:label_file`.

Обработчик: `yandex_market.views.label_file`.

Исходник: `yandex_market/views.py:442`.

Декораторы: `access('print_labels')`.

## `/crm/integrations/yandex/jobs/<int:pk>/retry/`

Имя: `yandex_market:retry`.

Обработчик: `yandex_market.views.retry`.

Исходник: `yandex_market/views.py:461`.

Декораторы: `access('retry_sync', post=True)`.

## `/crm/integrations/yandex/media/<uuid:public_id>/`

Имя: `yandex_market:media`.

Обработчик: `yandex_market.views.public_media`.

Исходник: `yandex_market/views.py:453`.

## `/crm/integrations/yandex/notifications/`

Имя: `yandex_market:notifications`.

Обработчик: `yandex_market.webhooks.notification`.

Исходник: `yandex_market/webhooks.py:35`.

Декораторы: `csrf_exempt`; `require_POST`.

## `/crm/integrations/updates/`

Имя: `integrations:updates`.

Обработчик: `core.update_views.updates`.

Исходник: `core/update_views.py:46`.

Декораторы: `require_http_methods(['GET', 'POST'])`; `never_cache`; `login_required`.

Прямые шаблоны: `core/updates.html`.

## `/crm/integrations/workers/`

Имя: `integrations:workers`.

Обработчик: `integrations.worker_views.workers`.

Исходник: `integrations/worker_views.py:20`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

Прямые шаблоны: `integrations/workers.html`.

## `/crm/integrations/workers/status/`

Имя: `integrations:worker_status`.

Обработчик: `integrations.worker_views.worker_status`.

Исходник: `integrations/worker_views.py:35`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

## `/crm/integrations/workers/restore/`

Имя: `integrations:worker_restore`.

Обработчик: `integrations.worker_views.worker_start`.

Исходник: `integrations/worker_views.py:52`.

Декораторы: `login_required`; `require_POST`.

## `/crm/integrations/workers/<str:service>/start/`

Имя: `integrations:worker_start`.

Обработчик: `integrations.worker_views.worker_start`.

Исходник: `integrations/worker_views.py:52`.

Декораторы: `login_required`; `require_POST`.

## `/crm/integrations/workers/commands/<uuid:pk>/`

Имя: `integrations:worker_command`.

Обработчик: `integrations.worker_views.worker_command`.

Исходник: `integrations/worker_views.py:71`.

Декораторы: `login_required`; `never_cache`; `require_GET`.

## `/crm/integrations/`

Имя: `integrations:api_keys`.

Обработчик: `integrations.views.api_keys`.

Исходник: `integrations/views.py:65`.

Декораторы: `permission_required_any('integrations.view_integrations')`.

Прямые шаблоны: `integrations/api_keys.html`.

## `/crm/integrations/reef/key/`

Имя: `integrations:reef_key_save`.

Обработчик: `integrations.views.reef_key_save`.

Исходник: `integrations/views.py:80`.

Декораторы: `require_POST`; `sensitive_post_parameters('api_key')`; `permission_required_any('integrations.manage_integration_credentials')`.

## `/crm/integrations/reef/check/`

Имя: `integrations:reef_check`.

Обработчик: `integrations.views.reef_connection_check`.

Исходник: `integrations/views.py:93`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

## `/crm/integrations/credentials/save/`

Имя: `integrations:credentials_save`.

Обработчик: `integrations.views.credentials_save`.

Исходник: `integrations/views.py:139`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

## `/crm/integrations/credentials/check/`

Имя: `integrations:credentials_check`.

Обработчик: `integrations.views.credentials_check`.

Исходник: `integrations/views.py:155`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

## `/crm/integrations/google-sheets/settings/`

Имя: `integrations:google_sheets_settings`.

Обработчик: `integrations.views.google_sheets_settings_save`.

Исходник: `integrations/views.py:105`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_integration_credentials')`.

## `/crm/integrations/google-sheets/sync/`

Имя: `integrations:google_sheets_sync`.

Обработчик: `integrations.views.google_sheets_sync`.

Исходник: `integrations/views.py:121`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_google_sheets_sync')`.

## `/crm/integrations/avito/`

Имя: `integrations:avito`.

Обработчик: `integrations.views.avito_dashboard`.

Исходник: `integrations/views.py:167`.

Декораторы: `permission_required_any('integrations.view_avito_integration')`.

Прямые шаблоны: `integrations/avito_dashboard.html`.

## `/crm/integrations/avito/actions/refresh/`

Имя: `integrations:required_actions_refresh`.

Обработчик: `integrations.views.required_actions_refresh`.

Исходник: `integrations/views.py:211`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

## `/crm/integrations/avito/actions/count/`

Имя: `integrations:required_actions_count`.

Обработчик: `integrations.views.required_actions_count`.

Исходник: `integrations/views.py:198`.

Декораторы: `require_GET`; `never_cache`; `permission_required_any('integrations.view_avito_integration')`.

## `/crm/integrations/avito/actions/<int:pk>/status/`

Имя: `integrations:required_actions_status`.

Обработчик: `integrations.views.required_actions_status`.

Исходник: `integrations/views.py:235`.

Декораторы: `require_GET`; `permission_required_any('integrations.view_avito_integration')`.

## `/crm/integrations/avito/sync/`

Имя: `integrations:manual_sync`.

Обработчик: `integrations.views.manual_sync`.

Исходник: `integrations/views.py:248`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

## `/crm/integrations/avito/sync/<int:pk>/status/`

Имя: `integrations:manual_sync_status`.

Обработчик: `integrations.views.manual_sync_status`.

Исходник: `integrations/views.py:269`.

Декораторы: `require_GET`; `permission_required_any('integrations.view_avito_integration')`.

## `/crm/integrations/avito/connections/`

Имя: `integrations:connections`.

Обработчик: `integrations.views.connections`.

Исходник: `integrations/views.py:291`.

Декораторы: `permission_required_any('integrations.view_avito_integration')`.

Прямые шаблоны: `integrations/connections.html`.

## `/crm/integrations/avito/connections/refresh/`

Имя: `integrations:listings_refresh`.

Обработчик: `integrations.views.listings_refresh`.

Исходник: `integrations/views.py:317`.

Декораторы: `require_POST`; `permission_required_any('integrations.manual_avito_sync')`.

## `/crm/integrations/avito/listings/<int:pk>/bind/`

Имя: `integrations:bind`.

Обработчик: `integrations.views.listing_bind`.

Исходник: `integrations/views.py:325`.

Декораторы: `permission_required_any('integrations.bind_avito_listing')`.

Прямые шаблоны: `integrations/bind.html`.

## `/crm/integrations/avito/connections/<int:pk>/rebind/`

Имя: `integrations:rebind`.

Обработчик: `integrations.views.listing_rebind`.

Исходник: `integrations/views.py:343`.

Декораторы: `permission_required_any('integrations.rebind_avito_listing')`.

Прямые шаблоны: `integrations/rebind.html`.

## `/crm/integrations/avito/connections/<int:pk>/unbind/`

Имя: `integrations:unbind`.

Обработчик: `integrations.views.listing_unbind`.

Исходник: `integrations/views.py:362`.

Декораторы: `permission_required_any('integrations.rebind_avito_listing')`; `require_POST`.

## `/crm/integrations/avito/products/<str:product_kind>/<int:pk>/`

Имя: `integrations:product_save`.

Обработчик: `integrations.views.product_profile_save`.

Исходник: `integrations/views.py:395`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

## `/crm/integrations/avito/products/<str:product_kind>/<int:pk>/photos/`

Имя: `integrations:photo_add`.

Обработчик: `integrations.views.product_photo_add`.

Исходник: `integrations/views.py:412`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

## `/crm/integrations/avito/products/<str:product_kind>/<int:pk>/photos/<int:photo_id>/delete/`

Имя: `integrations:photo_delete`.

Обработчик: `integrations.views.product_photo_delete`.

Исходник: `integrations/views.py:430`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

## `/crm/integrations/avito/products/<str:product_kind>/<int:pk>/photos/<int:photo_id>/move/`

Имя: `integrations:photo_move`.

Обработчик: `integrations.views.product_photo_move`.

Исходник: `integrations/views.py:444`.

Декораторы: `require_POST`; `permission_required_any('integrations.manage_avito_product')`.

## `/crm/update-health/`

Имя: `core:update_health`.

Обработчик: `core.update_health.update_health`.

Исходник: `core/update_health.py:11`.

Декораторы: `require_GET`; `never_cache`.

## `/crm/api/exchange-rates/`

Имя: `core:exchange_rates`.

Обработчик: `core.views.exchange_rates`.

Исходник: `core/views.py:15`.

Декораторы: `login_required`; `require_GET`.

## `/crm/`

Имя: `core:home`.

Обработчик: `core.views.home`.

Исходник: `core/views.py:42`.

Декораторы: `login_required`.

Прямые шаблоны: `core/no_access.html`.

## `/crm/integrations/retailer/regenerate/`

Имя: `resource_storefront:retail_regenerate`.

Обработчик: `resource_storefront.retail_views.regenerate`.

Исходник: `resource_storefront/retail_views.py:40`.

Декораторы: `require_POST`; `permission_required_any('resource_storefront.manage_retail_storefront')`.

## `/opt/`

Имя: `resource_storefront:home`.

Обработчик: `resource_storefront.views.home`.

Исходник: `resource_storefront/views.py:123`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/home.html`.

## `/opt/unavailable/`

Имя: `resource_storefront:denied`.

Обработчик: `resource_storefront.views.denied`.

Исходник: `resource_storefront/views.py:88`.

Декораторы: `require_GET`; `never_cache`.

Прямые шаблоны: `resource_storefront/unavailable.html`.

## `/opt/catalog/`

Имя: `resource_storefront:catalogue`.

Обработчик: `resource_storefront.views.catalogue`.

Исходник: `resource_storefront/views.py:152`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/catalogue.html`.

## `/opt/new/`

Имя: `resource_storefront:new`.

Обработчик: `resource_storefront.views.catalogue`.

Исходник: `resource_storefront/views.py:152`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/catalogue.html`.

## `/opt/product/<str:kind>/<int:pk>/`

Имя: `resource_storefront:product`.

Обработчик: `resource_storefront.views.product_detail`.

Исходник: `resource_storefront/views.py:193`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/product.html`, `resource_storefront/unavailable.html`.

## `/opt/product-photo/<str:kind>/<int:pk>/<int:image_id>/`

Имя: `resource_storefront:product_photo`.

Обработчик: `resource_storefront.views.product_photo`.

Исходник: `resource_storefront/views.py:513`.

Декораторы: `buyer_required`; `require_GET`.

## `/opt/content/<str:kind>/<int:pk>/`

Имя: `resource_storefront:content_asset`.

Обработчик: `resource_storefront.views.content_asset`.

Исходник: `resource_storefront/views.py:549`.

Декораторы: `buyer_required`; `require_GET`.

## `/opt/news/`

Имя: `resource_storefront:news_list`.

Обработчик: `resource_storefront.views.news_list`.

Исходник: `resource_storefront/views.py:208`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/news_list.html`.

## `/opt/news/<slug:slug>/`

Имя: `resource_storefront:news_detail`.

Обработчик: `resource_storefront.views.news_detail`.

Исходник: `resource_storefront/views.py:215`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/news_detail.html`.

## `/opt/cart/`

Имя: `resource_storefront:cart`.

Обработчик: `resource_storefront.views.cart_view`.

Исходник: `resource_storefront/views.py:263`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/cart.html`.

## `/opt/cart/add/`

Имя: `resource_storefront:cart_add`.

Обработчик: `resource_storefront.views.cart_add`.

Исходник: `resource_storefront/views.py:294`.

Декораторы: `buyer_required`; `require_POST`.

## `/opt/cart/update/<str:key>/`

Имя: `resource_storefront:cart_update`.

Обработчик: `resource_storefront.views.cart_update`.

Исходник: `resource_storefront/views.py:332`.

Декораторы: `buyer_required`; `require_POST`.

## `/opt/cart/remove/<str:key>/`

Имя: `resource_storefront:cart_remove`.

Обработчик: `resource_storefront.views.cart_remove`.

Исходник: `resource_storefront/views.py:351`.

Декораторы: `buyer_required`; `require_POST`.

## `/opt/cart/refresh/`

Имя: `resource_storefront:cart_refresh`.

Обработчик: `resource_storefront.views.cart_refresh`.

Исходник: `resource_storefront/views.py:361`.

Декораторы: `buyer_required`; `require_POST`.

## `/opt/checkout/`

Имя: `resource_storefront:checkout`.

Обработчик: `resource_storefront.views.checkout`.

Исходник: `resource_storefront/views.py:378`.

Декораторы: `buyer_required`; `require_POST`.

Прямые шаблоны: `resource_storefront/cart.html`.

## `/opt/checkout/status/`

Имя: `resource_storefront:checkout_status`.

Обработчик: `resource_storefront.views.checkout_status`.

Исходник: `resource_storefront/views.py:478`.

Декораторы: `buyer_required`; `require_GET`.

## `/opt/order/<int:sale_id>/`

Имя: `resource_storefront:success`.

Обработчик: `resource_storefront.views.order_success`.

Исходник: `resource_storefront/views.py:493`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/success.html`.

## `/opt/<str:token>/`

Имя: `resource_storefront:access`.

Обработчик: `resource_storefront.views.access`.

Исходник: `resource_storefront/views.py:94`.

Декораторы: `require_GET`; `never_cache`.

Прямые шаблоны: `resource_storefront/unavailable.html`.

## `/crm/wholesale-contacts/`

Имя: `resource_storefront:contacts`.

Обработчик: `resource_storefront.views.contacts`.

Исходник: `resource_storefront/views.py:565`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_GET`.

Прямые шаблоны: `resource_storefront/contacts.html`.

## `/crm/wholesale-contacts/new/`

Имя: `resource_storefront:contact_new`.

Обработчик: `resource_storefront.views.contact_save`.

Исходник: `resource_storefront/views.py:580`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

## `/crm/wholesale-contacts/<int:pk>/edit/`

Имя: `resource_storefront:contact_edit`.

Обработчик: `resource_storefront.views.contact_save`.

Исходник: `resource_storefront/views.py:580`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

## `/crm/wholesale-contacts/<int:pk>/link/`

Имя: `resource_storefront:link_issue`.

Обработчик: `resource_storefront.views.link_issue`.

Исходник: `resource_storefront/views.py:612`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

## `/crm/wholesale-links/<int:pk>/revoke/`

Имя: `resource_storefront:link_revoke`.

Обработчик: `resource_storefront.views.link_revoke`.

Исходник: `resource_storefront/views.py:630`.

Декораторы: `permission_required_any('resource_storefront.manage_wholesale_contacts')`; `require_POST`.

## `/crm/integrations/storefront/`

Имя: `resource_storefront:manage`.

Обработчик: `resource_storefront.views.manage`.

Исходник: `resource_storefront/views.py:641`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_GET`.

Прямые шаблоны: `resource_storefront/manage.html`.

## `/crm/integrations/storefront/preview/`

Имя: `resource_storefront:preview_start`.

Обработчик: `resource_storefront.views.preview_start`.

Исходник: `resource_storefront/views.py:665`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_GET`.

## `/crm/integrations/storefront/settings/`

Имя: `resource_storefront:settings_save`.

Обработчик: `resource_storefront.views.settings_save`.

Исходник: `resource_storefront/views.py:672`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/slots/add/`

Имя: `resource_storefront:slot_add`.

Обработчик: `resource_storefront.views.slot_add`.

Исходник: `resource_storefront/views.py:708`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/products/<str:kind>/<int:pk>/publication/`

Имя: `resource_storefront:product_publication`.

Обработчик: `resource_storefront.views.product_publication`.

Исходник: `resource_storefront/views.py:729`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/slots/<int:pk>/remove/`

Имя: `resource_storefront:slot_remove`.

Обработчик: `resource_storefront.views.slot_remove`.

Исходник: `resource_storefront/views.py:760`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/news/new/`

Имя: `resource_storefront:news_new`.

Обработчик: `resource_storefront.views.news_save`.

Исходник: `resource_storefront/views.py:767`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/news/<int:pk>/edit/`

Имя: `resource_storefront:news_edit`.

Обработчик: `resource_storefront.views.news_save`.

Исходник: `resource_storefront/views.py:767`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/news/<int:pk>/unpublish/`

Имя: `resource_storefront:news_unpublish`.

Обработчик: `resource_storefront.views.news_unpublish`.

Исходник: `resource_storefront/views.py:797`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/collections/new/`

Имя: `resource_storefront:collection_new`.

Обработчик: `resource_storefront.views.collection_save`.

Исходник: `resource_storefront/views.py:807`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/collections/<int:pk>/edit/`

Имя: `resource_storefront:collection_edit`.

Обработчик: `resource_storefront.views.collection_save`.

Исходник: `resource_storefront/views.py:807`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/collections/<int:pk>/items/add/`

Имя: `resource_storefront:collection_product_add`.

Обработчик: `resource_storefront.views.collection_product_add`.

Исходник: `resource_storefront/views.py:826`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/collection-items/<int:pk>/remove/`

Имя: `resource_storefront:collection_product_remove`.

Обработчик: `resource_storefront.views.collection_product_remove`.

Исходник: `resource_storefront/views.py:843`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/news/<int:pk>/products/add/`

Имя: `resource_storefront:news_product_add`.

Обработчик: `resource_storefront.views.news_product_add`.

Исходник: `resource_storefront/views.py:850`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/crm/integrations/storefront/news-products/<str:kind>/<int:pk>/remove/`

Имя: `resource_storefront:news_product_remove`.

Обработчик: `resource_storefront.views.news_product_remove`.

Исходник: `resource_storefront/views.py:868`.

Декораторы: `permission_required_any('resource_storefront.manage_storefront')`; `require_POST`.

## `/retailer/`

Имя: `retailer:home`.

Обработчик: `resource_storefront.views.catalogue`.

Исходник: `resource_storefront/views.py:152`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/catalogue.html`.

## `/retailer/catalog/`

Имя: `retailer:catalogue`.

Обработчик: `resource_storefront.views.catalogue`.

Исходник: `resource_storefront/views.py:152`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/catalogue.html`.

## `/retailer/product/<str:kind>/<int:pk>/`

Имя: `retailer:product`.

Обработчик: `resource_storefront.views.product_detail`.

Исходник: `resource_storefront/views.py:193`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/product.html`, `resource_storefront/unavailable.html`.

## `/retailer/product-photo/<str:kind>/<int:pk>/<int:image_id>/`

Имя: `retailer:product_photo`.

Обработчик: `resource_storefront.views.product_photo`.

Исходник: `resource_storefront/views.py:513`.

Декораторы: `buyer_required`; `require_GET`.

## `/retailer/cart/`

Имя: `retailer:cart`.

Обработчик: `resource_storefront.views.cart_view`.

Исходник: `resource_storefront/views.py:263`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/cart.html`.

## `/retailer/cart/add/`

Имя: `retailer:cart_add`.

Обработчик: `resource_storefront.views.cart_add`.

Исходник: `resource_storefront/views.py:294`.

Декораторы: `buyer_required`; `require_POST`.

## `/retailer/cart/update/<str:key>/`

Имя: `retailer:cart_update`.

Обработчик: `resource_storefront.views.cart_update`.

Исходник: `resource_storefront/views.py:332`.

Декораторы: `buyer_required`; `require_POST`.

## `/retailer/cart/remove/<str:key>/`

Имя: `retailer:cart_remove`.

Обработчик: `resource_storefront.views.cart_remove`.

Исходник: `resource_storefront/views.py:351`.

Декораторы: `buyer_required`; `require_POST`.

## `/retailer/cart/refresh/`

Имя: `retailer:cart_refresh`.

Обработчик: `resource_storefront.views.cart_refresh`.

Исходник: `resource_storefront/views.py:361`.

Декораторы: `buyer_required`; `require_POST`.

## `/retailer/checkout/`

Имя: `retailer:checkout`.

Обработчик: `resource_storefront.views.checkout`.

Исходник: `resource_storefront/views.py:378`.

Декораторы: `buyer_required`; `require_POST`.

Прямые шаблоны: `resource_storefront/cart.html`.

## `/retailer/checkout/status/`

Имя: `retailer:checkout_status`.

Обработчик: `resource_storefront.views.checkout_status`.

Исходник: `resource_storefront/views.py:478`.

Декораторы: `buyer_required`; `require_GET`.

## `/retailer/order/<int:sale_id>/`

Имя: `retailer:success`.

Обработчик: `resource_storefront.views.order_success`.

Исходник: `resource_storefront/views.py:493`.

Декораторы: `buyer_required`; `require_GET`.

Прямые шаблоны: `resource_storefront/success.html`.

## `/retailer/<str:token>/`

Имя: `retailer:access`.

Обработчик: `resource_storefront.retail_views.access`.

Исходник: `resource_storefront/retail_views.py:21`.

Декораторы: `require_GET`; `sensitive_variables('token')`.

Прямые шаблоны: `resource_storefront/unavailable.html`.

## `/^static/(?P<path>.*)$`

Имя: ``.

Обработчик: `django.views.static.serve`.
