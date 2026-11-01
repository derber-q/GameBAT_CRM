# Шаблоны, клиентские модули, миграции и проверки

<!-- Сгенерировано scripts/build_technical_reference.py; не редактировать вручную. -->

Справочник исходников и метаданных схемы, без рабочих записей/ключей. Перегенерация: `.venv/Scripts/python.exe scripts/build_technical_reference.py`.

## HTML-шаблоны (164)

### `resource_storefront/templates/resource_storefront/_card.html`

Части: `resource_storefront/_placeholder.html`.

### `resource_storefront/templates/resource_storefront/_cart_content.html`

### `resource_storefront/templates/resource_storefront/_placeholder.html`

### `resource_storefront/templates/resource_storefront/base.html`

Части: `core/_test_environment_banner.html`.

### `resource_storefront/templates/resource_storefront/cart.html`

Базовый шаблон: `resource_storefront/base.html`.

Части: `resource_storefront/_cart_content.html`.

### `resource_storefront/templates/resource_storefront/catalogue.html`

Базовый шаблон: `resource_storefront/base.html`.

Части: `resource_storefront/_card.html`.

### `resource_storefront/templates/resource_storefront/contacts.html`

Базовый шаблон: `base.html`.

Именованные действия: `resource_storefront:contact_edit`, `resource_storefront:contact_new`, `resource_storefront:link_issue`, `resource_storefront:link_revoke`.

### `resource_storefront/templates/resource_storefront/home.html`

Базовый шаблон: `resource_storefront/base.html`.

Части: `resource_storefront/_card.html`.

Именованные действия: `resource_storefront:catalogue`, `resource_storefront:content_asset`, `resource_storefront:manage`, `resource_storefront:new`, `resource_storefront:news_detail`, `resource_storefront:news_list`.

### `resource_storefront/templates/resource_storefront/manage.html`

Базовый шаблон: `base.html`.

Именованные действия: `admin:resource_storefront_catalogimagecrop_changelist`, `resource_storefront:collection_edit`, `resource_storefront:collection_new`, `resource_storefront:collection_product_add`, `resource_storefront:collection_product_remove`, `resource_storefront:news_edit`, `resource_storefront:news_new`, `resource_storefront:news_product_add`, `resource_storefront:news_product_remove`, `resource_storefront:news_unpublish`, `resource_storefront:preview_start`, `resource_storefront:product_publication`, `resource_storefront:settings_save`, `resource_storefront:slot_add`, `resource_storefront:slot_remove`.

### `resource_storefront/templates/resource_storefront/news_detail.html`

Базовый шаблон: `resource_storefront/base.html`.

Части: `resource_storefront/_card.html`.

Именованные действия: `resource_storefront:content_asset`.

### `resource_storefront/templates/resource_storefront/news_list.html`

Базовый шаблон: `resource_storefront/base.html`.

Именованные действия: `resource_storefront:content_asset`, `resource_storefront:news_detail`.

### `resource_storefront/templates/resource_storefront/product.html`

Базовый шаблон: `resource_storefront/base.html`.

Части: `resource_storefront/_placeholder.html`.

### `resource_storefront/templates/resource_storefront/success.html`

Базовый шаблон: `resource_storefront/base.html`.

### `resource_storefront/templates/resource_storefront/unavailable.html`

Базовый шаблон: `resource_storefront/base.html`.

### `templates/403.html`

Базовый шаблон: `base.html`.

Именованные действия: `core:home`.

### `templates/accounts/form.html`

Базовый шаблон: `base.html`.

### `templates/accounts/login.html`

Базовый шаблон: `base.html`.

### `templates/accounts/permission_set_list.html`

Базовый шаблон: `base.html`.

Именованные действия: `accounts:permission_set_create`, `accounts:permission_set_delete`, `accounts:permission_set_edit`.

### `templates/accounts/staff_by_group.html`

Базовый шаблон: `base.html`.

Именованные действия: `accounts:user_detail`, `accounts:user_list`.

### `templates/accounts/user_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `accounts:password_reset`, `accounts:user_update`, `accounts:verification_document`.

### `templates/accounts/user_list.html`

Базовый шаблон: `base.html`.

Именованные действия: `accounts:permission_sets`, `accounts:user_create`, `accounts:user_detail`.

### `templates/admin/base_site.html`

Базовый шаблон: `admin/base.html`.

Части: `core/_test_environment_banner.html`, `sales/_notification_assets.html`, `sales/_notification_counter.html`, `sales/_notification_panel.html`, `sales/_notification_sound_button.html`.

Именованные действия: `admin:index`, `core:home`.

### `templates/admin/color_theme_toggle.html`

### `templates/base.html`

Части: `core/_test_environment_banner.html`, `integrations/_worker_alert.html`, `sales/_notification_assets.html`, `sales/_notification_counter.html`, `sales/_notification_panel.html`, `sales/_notification_sound_button.html`.

Именованные действия: `accounts:logout`, `accounts:password_change`, `accounts:staff_by_group`, `accounts:user_list`, `admin:index`, `cash:register`, `catalog:warehouse`, `consignment:list`, `consignment:platform`, `core:exchange_rates`, `core:home`, `creditors:list`, `integrations:api_keys`, `integrations:avito`, `integrations:updates`, `integrations:workers`, `nomenclature:cd_list`, `nomenclature:create`, `nomenclature:list`, `nomenclature:tech_list`, `orders:list`, `partners:list`, `partners:partner_list`, `price:imports`, `price:index`, `price:site_links`, `pricing:avito_check`, `pricing:cd_list`, `pricing:list`, `pricing:tech_list`, `resource_storefront:manage`, `sales:cancelled`, `sales:completed`, `sales:create`, `sales:incomplete`, `sales:settlement_preview`, `statistics:index`, `supplies:list`, `warehouse:detail`, `warehouse:transfer_list`, `yandex_market:dashboard`.

### `templates/cash/operation.html`

Базовый шаблон: `base.html`.

Именованные действия: `cash:register`.

### `templates/cash/register.html`

Базовый шаблон: `base.html`.

Именованные действия: `cash:cash_to_safe`, `cash:collect`, `cash:deposit`, `cash:safe_collect`, `cash:safe_deposit`, `cash:safe_to_cash`, `sales:detail`, `warehouse:detail`.

### `templates/catalog/_product_filters.html`

Именованные действия: `warehouse:storage_location_autocomplete`.

### `templates/catalog/warehouse.html`

Базовый шаблон: `warehouse/global_stock.html`.

### `templates/consignment/_platform_panel.html`

Части: `consignment/_stock_group.html`.

Именованные действия: `consignment:platform_export`, `consignment:report_import`.

### `templates/consignment/_stock_group.html`

Части: `consignment/_stock_row.html`.

### `templates/consignment/_stock_row.html`

Именованные действия: `consignment:reward_update`, `consignment:row_action`.

### `templates/consignment/list.html`

Базовый шаблон: `base.html`.

Части: `catalog/_product_filters.html`, `consignment/_platform_panel.html`.

Именованные действия: `consignment:list`, `consignment:platform_create`, `consignment:transfer`.

### `templates/consignment/movement_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `consignment:list`.

### `templates/consignment/report_import.html`

Базовый шаблон: `base.html`.

Именованные действия: `consignment:platform`.

### `templates/consignment/report_partner_payment.html`

Базовый шаблон: `base.html`.

Именованные действия: `sales:detail`.

### `templates/consignment/transfer.html`

Базовый шаблон: `base.html`.

Именованные действия: `consignment:list`, `supplies:autocomplete`.

### `templates/core/_test_environment_banner.html`

### `templates/core/no_access.html`

Базовый шаблон: `base.html`.

Именованные действия: `accounts:password_change`.

### `templates/core/updates.html`

Базовый шаблон: `base.html`.

Именованные действия: `integrations:updates`.

### `templates/creditors/_debt_field.html`

### `templates/creditors/debt.html`

Базовый шаблон: `base.html`.

Части: `creditors/_debt_field.html`.

Именованные действия: `creditors:detail`.

### `templates/creditors/detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `creditors:debt`, `creditors:edit`, `creditors:list`.

### `templates/creditors/form.html`

Базовый шаблон: `base.html`.

Именованные действия: `creditors:detail`, `creditors:list`.

### `templates/creditors/list.html`

Базовый шаблон: `base.html`.

Именованные действия: `creditors:create`, `creditors:debt`, `creditors:detail`.

### `templates/integrations/_pagination.html`

### `templates/integrations/_product_block.html`

Именованные действия: `integrations:photo_add`, `integrations:photo_delete`, `integrations:photo_move`, `integrations:product_save`.

### `templates/integrations/_required_actions.html`

Именованные действия: `integrations:required_actions_refresh`, `integrations:required_actions_status`, `nomenclature:cd_detail`, `nomenclature:tech_detail`.

### `templates/integrations/_worker_alert.html`

Именованные действия: `integrations:worker_status`.

### `templates/integrations/api_keys.html`

Базовый шаблон: `base.html`.

Именованные действия: `integrations:credentials_check`, `integrations:credentials_save`, `integrations:google_sheets_settings`, `integrations:google_sheets_sync`, `integrations:reef_check`, `integrations:reef_key_save`.

### `templates/integrations/avito_dashboard.html`

Базовый шаблон: `base.html`.

Части: `integrations/_required_actions.html`.

Именованные действия: `integrations:api_keys`, `integrations:connections`, `integrations:manual_sync`, `integrations:manual_sync_status`.

### `templates/integrations/bind.html`

Базовый шаблон: `base.html`.

Именованные действия: `integrations:connections`.

### `templates/integrations/connections.html`

Базовый шаблон: `base.html`.

Части: `integrations/_pagination.html`.

Именованные действия: `integrations:bind`, `integrations:listings_refresh`, `integrations:rebind`, `nomenclature:cd_detail`, `nomenclature:tech_detail`.

### `templates/integrations/rebind.html`

Базовый шаблон: `base.html`.

Именованные действия: `integrations:connections`, `integrations:unbind`.

### `templates/integrations/workers.html`

Базовый шаблон: `base.html`.

Именованные действия: `integrations:worker_restore`, `integrations:worker_start`, `sales:print_resolve`.

### `templates/nomenclature/_barcode_formset.html`

Именованные действия: `nomenclature:barcode_print`.

### `templates/nomenclature/_field.html`

### `templates/nomenclature/_product_media.html`

Именованные действия: `nomenclature:product_gallery_delete`, `nomenclature:product_gallery_image`, `nomenclature:product_gallery_upload`, `nomenclature:product_title_delete`, `nomenclature:product_title_image`, `nomenclature:product_title_upload`.

### `templates/nomenclature/_product_options.html`

Части: `nomenclature/_field.html`.

### `templates/nomenclature/barcode_print.html`

### `templates/nomenclature/create.html`

Базовый шаблон: `base.html`.

Части: `nomenclature/_barcode_formset.html`, `nomenclature/_field.html`, `nomenclature/_product_options.html`.

Именованные действия: `nomenclature:create`, `nomenclature:list`.

### `templates/nomenclature/detail.html`

Базовый шаблон: `base.html`.

Части: `integrations/_product_block.html`, `nomenclature/_barcode_formset.html`, `nomenclature/_field.html`, `nomenclature/_product_media.html`, `nomenclature/_product_options.html`, `yandex_market/_product_content.html`.

Именованные действия: `nomenclature:barcode_generate`, `nomenclature:list`, `nomenclature:product_delete`.

### `templates/nomenclature/list.html`

Базовый шаблон: `base.html`.

Части: `catalog/_product_filters.html`.

Именованные действия: `nomenclature:bulk_delete`, `nomenclature:cd_detail`, `nomenclature:create`, `nomenclature:product_title_image`, `nomenclature:tech_detail`.

### `templates/orders/_changes_confirmation.html`

### `templates/orders/_independent_supply_expenses.html`

Именованные действия: `orders:arrival_supply_post`.

### `templates/orders/_operation_actions.html`

Именованные действия: `orders:arrival_receipt`, `orders:detail`, `orders:operation_prepare`, `sales:detail`, `supplies:detail`.

### `templates/orders/_operation_calculation.html`

Именованные действия: `orders:detail`.

### `templates/orders/_operation_panel.html`

Именованные действия: `orders:operation_prepare`, `sales:detail`, `supplies:detail`, `supplies:price_review`.

### `templates/orders/_operation_source.html`

Именованные действия: `orders:arrival_receipt`, `orders:detail`, `orders:trip_detail`.

### `templates/orders/_orders_table.html`

Части: `orders/_operation_actions.html`.

Именованные действия: `orders:assign_trip`, `orders:detail`, `orders:export`, `orders:trip_detail`.

### `templates/orders/_procurement_financials.html`

### `templates/orders/_stock_detail.html`

Части: `orders/_operation_panel.html`.

Именованные действия: `orders:adjust`, `orders:assign_trip`, `orders:complete`, `orders:confirm`, `orders:edit`, `orders:export`, `orders:export_suppliers`, `orders:list`, `orders:start_receiving`, `price:procurement_detail`, `supplies:detail`, `supplies:price_review`.

### `templates/orders/_trip_arrival.html`

Именованные действия: `orders:arrival_finalization`, `orders:trip_arrival`.

### `templates/orders/_trip_price_dialog.html`

### `templates/orders/adjust.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:detail`.

### `templates/orders/arrival_finalization.html`

Базовый шаблон: `base.html`.

Части: `supplies/_finalization_toolbar.html`.

Именованные действия: `orders:arrival_finalization_auto`, `orders:trip_detail`.

### `templates/orders/arrival_prepare.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:trip_detail`.

### `templates/orders/arrival_receipt.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:trip_detail`, `sales:detail`, `supplies:detail`.

### `templates/orders/detail.html`

Базовый шаблон: `base.html`.

Части: `orders/_operation_panel.html`, `orders/_procurement_financials.html`, `orders/_stock_detail.html`.

Именованные действия: `orders:adjust`, `orders:assign_trip`, `orders:complete`, `orders:confirm`, `orders:edit`, `orders:export`, `orders:export_suppliers`, `orders:list`, `orders:start_receiving`, `partners:partner_detail`, `price:procurement_detail`.

### `templates/orders/edit.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:detail`.

### `templates/orders/list.html`

Базовый шаблон: `base.html`.

Части: `orders/_orders_table.html`.

Именованные действия: `orders:stock_create`, `orders:supplier_batch_detail`, `orders:trip_create`, `orders:trip_detail`, `orders:trip_empty_create`, `orders:trip_full_export`, `orders:upload`.

### `templates/orders/operation_prepare.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:detail`.

### `templates/orders/preview.html`

Базовый шаблон: `base.html`.

### `templates/orders/stock_create.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:upload`, `price:imports`.

### `templates/orders/supplier_batch_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:list`.

### `templates/orders/trip_add_orders.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:trip_detail`.

### `templates/orders/trip_addition.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:trip_addition_calculation`, `orders:trip_addition_search`, `orders:trip_detail`.

### `templates/orders/trip_assign.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:detail`, `orders:list`.

### `templates/orders/trip_detail.html`

Базовый шаблон: `base.html`.

Части: `orders/_operation_actions.html`, `orders/_procurement_financials.html`, `orders/_trip_arrival.html`, `orders/_trip_price_dialog.html`.

Именованные действия: `orders:assign_trip`, `orders:detail`, `orders:list`, `orders:trip_add_orders`, `orders:trip_addition`, `orders:trip_export`, `orders:trip_invoice_update`, `orders:trip_line_update`.

### `templates/orders/trip_empty_create.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:list`.

### `templates/orders/upload.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:list`, `orders:stock_create`.

### `templates/partners/_partner_telegram.html`

### `templates/partners/partner_detail.html`

Базовый шаблон: `base.html`.

Части: `partners/_partner_telegram.html`.

Именованные действия: `creditors:detail`, `partners:partner_edit`, `partners:partner_list`.

### `templates/partners/partner_form.html`

Базовый шаблон: `base.html`.

Именованные действия: `partners:partner_list`.

### `templates/partners/partner_list.html`

Базовый шаблон: `base.html`.

Части: `partners/_partner_telegram.html`.

Именованные действия: `partners:partner_create`, `partners:partner_detail`.

### `templates/partners/platform_form.html`

Базовый шаблон: `base.html`.

Именованные действия: `consignment:list`.

### `templates/partners/supplier_form.html`

Базовый шаблон: `accounts/form.html`.

### `templates/partners/supplier_list.html`

Базовый шаблон: `base.html`.

Именованные действия: `partners:create`, `partners:update`.

### `templates/price/_procurement_fields.html`

### `templates/price/imports.html`

Базовый шаблон: `base.html`.

Части: `price/_procurement_fields.html`.

Именованные действия: `orders:stock_create`, `price:procurement_create`, `price:procurement_detail`, `price:procurement_stock_export`, `price:supplier_template_kind`, `price:supplier_template_prefilled`, `price:supplier_upload`.

### `templates/price/index.html`

Базовый шаблон: `base.html`.

Именованные действия: `price:retail_export`, `price:settings_update`, `price:wholesale_export`.

### `templates/price/procurement_confirm.html`

Базовый шаблон: `base.html`.

Именованные действия: `price:procurement_detail`, `price:procurement_update`.

### `templates/price/procurement_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `orders:stock_create`, `price:imports`, `price:procurement_export_kind`, `price:procurement_stock_export`, `price:procurement_update`.

### `templates/price/procurement_prepare.html`

Базовый шаблон: `base.html`.

Части: `price/_procurement_fields.html`.

Именованные действия: `price:imports`, `price:procurement_create`.

### `templates/price/site_links.html`

Базовый шаблон: `base.html`.

Именованные действия: `admin:resource_storefront_retailsettings_change`, `resource_storefront:contacts`, `resource_storefront:link_issue`, `resource_storefront:retail_regenerate`.

### `templates/pricing/_avito_check_results.html`

### `templates/pricing/_fbs_form.html`

Именованные действия: `pricing:fbs_preview`, `pricing:fbs_save`.

### `templates/pricing/_price_cell.html`

Именованные действия: `pricing:fbs_detail`, `pricing:fbs_preview`.

### `templates/pricing/_price_table.html`

Части: `pricing/_price_cell.html`.

Именованные действия: `nomenclature:cd_detail`, `nomenclature:product_title_image`, `nomenclature:tech_detail`, `pricing:product_update`.

### `templates/pricing/avito_check.html`

Базовый шаблон: `base.html`.

Части: `pricing/_avito_check_results.html`.

Именованные действия: `integrations:api_keys`, `nomenclature:product_title_image`, `pricing:avito_check`, `pricing:avito_check_next`, `pricing:avito_check_run`.

### `templates/pricing/avito_check_complete.html`

Базовый шаблон: `base.html`.

Именованные действия: `pricing:avito_check`, `pricing:avito_check_automatic`.

### `templates/pricing/avito_check_list.html`

Базовый шаблон: `base.html`.

Части: `pricing/_price_cell.html`.

Именованные действия: `nomenclature:product_title_image`, `pricing:avito_check`, `pricing:avito_check_automatic`, `pricing:avito_check_found_price`, `pricing:product_update`.

### `templates/pricing/fbs_detail.html`

Базовый шаблон: `base.html`.

Части: `pricing/_fbs_form.html`.

Именованные действия: `pricing:list`.

### `templates/pricing/list.html`

Базовый шаблон: `base.html`.

Части: `catalog/_product_filters.html`, `pricing/_price_table.html`.

### `templates/sales/_list_group.html`

Части: `sales/_list_row.html`.

### `templates/sales/_list_row.html`

Части: `sales/_market_attention.html`, `sales/_market_controls.html`.

Именованные действия: `sales:detail`, `sales:inline_status`.

### `templates/sales/_market_attention.html`

Именованные действия: `sales:market_acknowledge`.

### `templates/sales/_market_cancel_dialog.html`

### `templates/sales/_market_controls.html`

Части: `sales/_market_attention.html`.

Именованные действия: `sales:market_action`, `sales:market_print`.

### `templates/sales/_notification_assets.html`

### `templates/sales/_notification_counter.html`

Именованные действия: `integrations:avito`, `integrations:required_actions_count`, `sales:market_pending`.

### `templates/sales/_notification_panel.html`

Именованные действия: `sales:market_notifications`, `sales:market_pending`.

### `templates/sales/_notification_sound_button.html`

### `templates/sales/_partner_operations.html`

### `templates/sales/_payment_partner_field.html`

### `templates/sales/avito_bridge.html`

Базовый шаблон: `base.html`.

### `templates/sales/create.html`

Базовый шаблон: `base.html`.

Части: `orders/_changes_confirmation.html`, `orders/_operation_calculation.html`.

Именованные действия: `sales:import_wholesale`, `sales:list`, `supplies:autocomplete`.

### `templates/sales/detail.html`

Базовый шаблон: `base.html`.

Части: `orders/_operation_source.html`, `sales/_market_cancel_dialog.html`, `sales/_market_controls.html`, `sales/_payment_partner_field.html`.

Именованные действия: `sales:advance`, `sales:cancel`, `sales:edit`, `sales:invoice`, `sales:list`, `sales:mark_paid`, `sales:note_update`, `sales:payment_method`.

### `templates/sales/edit.html`

Базовый шаблон: `base.html`.

Именованные действия: `sales:detail`, `supplies:autocomplete`.

### `templates/sales/import_wholesale.html`

Базовый шаблон: `base.html`.

Именованные действия: `sales:create`.

### `templates/sales/invoice.html`

### `templates/sales/list.html`

Базовый шаблон: `base.html`.

Части: `sales/_list_group.html`, `sales/_market_cancel_dialog.html`, `sales/_payment_partner_field.html`.

Именованные действия: `sales:cancelled`, `sales:completed`, `sales:create`, `sales:incomplete`, `sales:market_scan`.

### `templates/sales/market_pending.html`

Базовый шаблон: `base.html`.

Именованные действия: `sales:detail`, `sales:incomplete`, `sales:market_acknowledge`.

### `templates/sales/statistics.html`

Базовый шаблон: `base.html`.

Части: `sales/_partner_operations.html`.

Именованные действия: `sales:detail`, `statistics:export`, `statistics:index`.

### `templates/supplies/_finalization_rows.html`

### `templates/supplies/_finalization_toolbar.html`

### `templates/supplies/create.html`

Базовый шаблон: `base.html`.

Части: `orders/_changes_confirmation.html`, `orders/_operation_calculation.html`.

Именованные действия: `supplies:autocomplete`, `supplies:detail`, `supplies:list`, `supplies:product_barcode`, `supplies:product_codes`, `supplies:product_weight`.

### `templates/supplies/detail.html`

Базовый шаблон: `base.html`.

Части: `orders/_independent_supply_expenses.html`, `orders/_operation_source.html`.

Именованные действия: `orders:arrival_receipt`, `orders:detail`, `supplies:cancel`, `supplies:edit`, `supplies:finalization`, `supplies:list`, `supplies:price_review`, `supplies:revision_detail`.

### `templates/supplies/finalization.html`

Базовый шаблон: `base.html`.

Части: `supplies/_finalization_rows.html`, `supplies/_finalization_toolbar.html`.

Именованные действия: `supplies:detail`, `supplies:finalization_auto`.

### `templates/supplies/list.html`

Базовый шаблон: `base.html`.

Именованные действия: `supplies:create`, `supplies:detail`, `supplies:price_review`.

### `templates/supplies/price_review.html`

Базовый шаблон: `base.html`.

Именованные действия: `supplies:detail`, `supplies:edit`.

### `templates/supplies/revision_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `supplies:detail`.

### `templates/warehouse/_global_stock_table.html`

Именованные действия: `nomenclature:cd_detail`, `nomenclature:product_title_image`, `nomenclature:tech_detail`.

### `templates/warehouse/_inventory_search.html`

### `templates/warehouse/_storage_location_editor.html`

Именованные действия: `warehouse:storage_location_autocomplete`, `warehouse:storage_location_update`.

### `templates/warehouse/detail.html`

Базовый шаблон: `base.html`.

Части: `catalog/_product_filters.html`, `warehouse/_storage_location_editor.html`.

Именованные действия: `catalog:warehouse`, `nomenclature:cd_detail`, `nomenclature:product_title_image`, `nomenclature:tech_detail`, `warehouse:revision`, `warehouse:transfer_create`.

### `templates/warehouse/global_stock.html`

Базовый шаблон: `base.html`.

Части: `catalog/_product_filters.html`, `warehouse/_global_stock_table.html`.

Именованные действия: `warehouse:transfer_list`.

### `templates/warehouse/revision.html`

Базовый шаблон: `base.html`.

Именованные действия: `warehouse:detail`, `warehouse:revision_check`, `warehouse:revision_start`.

### `templates/warehouse/transfer_create.html`

Базовый шаблон: `base.html`.

Именованные действия: `warehouse:detail`, `warehouse:transfer_create`, `warehouse:transfer_list`.

### `templates/warehouse/transfer_detail.html`

Базовый шаблон: `base.html`.

Именованные действия: `warehouse:transfer_advance`, `warehouse:transfer_list`.

### `templates/warehouse/transfer_list.html`

Базовый шаблон: `base.html`.

Именованные действия: `catalog:warehouse`, `warehouse:transfer_detail`, `warehouse:transfer_start`.

### `templates/warehouse/transfer_start.html`

Базовый шаблон: `base.html`.

Именованные действия: `warehouse:transfer_list`.

### `templates/yandex_market/_product_content.html`

Части: `yandex_market/confirm.html`.

Именованные действия: `yandex_market:connection`, `yandex_market:content_action`, `yandex_market:dashboard`, `yandex_market:new_offer`.

### `templates/yandex_market/base.html`

Базовый шаблон: `base.html`.

Именованные действия: `yandex_market:dashboard`.

### `templates/yandex_market/bind.html`

Базовый шаблон: `yandex_market/base.html`.

Части: `yandex_market/confirm.html`.

Именованные действия: `yandex_market:bind`.

### `templates/yandex_market/categories.html`

Базовый шаблон: `yandex_market/base.html`.

Части: `yandex_market/confirm.html`.

Именованные действия: `yandex_market:connection`, `yandex_market:content_action`.

### `templates/yandex_market/confirm.html`

### `templates/yandex_market/connection.html`

Базовый шаблон: `yandex_market/base.html`.

Части: `yandex_market/confirm.html`.

Именованные действия: `yandex_market:bind`, `yandex_market:categories`, `yandex_market:content_action`, `yandex_market:media`, `yandex_market:unlink`.

### `templates/yandex_market/dashboard.html`

Базовый шаблон: `yandex_market/base.html`.

Части: `yandex_market/confirm.html`.

Именованные действия: `sales:detail`, `yandex_market:bind`, `yandex_market:connection`, `yandex_market:label_request`, `yandex_market:order`, `yandex_market:retry`, `yandex_market:settings`, `yandex_market:settings_new`, `yandex_market:sync`.

### `templates/yandex_market/error.html`

Базовый шаблон: `yandex_market/base.html`.

### `templates/yandex_market/label.html`

Базовый шаблон: `yandex_market/base.html`.

Именованные действия: `sales:detail`, `sales:incomplete`, `yandex_market:label_file`.

### `templates/yandex_market/order.html`

Базовый шаблон: `yandex_market/base.html`.

Части: `yandex_market/confirm.html`.

Именованные действия: `sales:detail`, `yandex_market:label`, `yandex_market:label_request`, `yandex_market:order_action`, `yandex_market:return_accept`.

### `templates/yandex_market/pricing_settings.html`

Базовый шаблон: `yandex_market/base.html`.

Именованные действия: `yandex_market:settings`.

### `templates/yandex_market/settings.html`

Базовый шаблон: `yandex_market/base.html`.

Именованные действия: `yandex_market:check`, `yandex_market:notifications`, `yandex_market:pricing_settings`.

### `yandex_market/templates/yandex_market/object_list_widget.html`

## JavaScript и CSS (90)

### `browser_extensions/avito_check/background.js`

ReSOURCE: Service worker расширения: разрешённые вкладки/сообщения и очередь ручного поиска CRM.

### `browser_extensions/avito_check/cards.css`

ReSOURCE: Оформление цен карточек Avito в расширении. Стили не заменяют серверные учётные проверки.

### `browser_extensions/avito_check/cards.js`

ReSOURCE: Распознавание исходной цены Avito, блокировка перехода по карточке и сравнение с минимумом; неоднозначность не подменяется случайной ценой.

### `browser_extensions/avito_check/crm.js`

ReSOURCE: Связь расширения с ручным поиском CRM и сохранённым минимумом; работает только в разрешённом контексте.

### `browser_extensions/avito_check/order-controls.js`

Доставка, оплата и отмена только связанной продажи CRM; цветовые классы приходят из CRM.

### `browser_extensions/avito_check/order-presentation.js`

Фотографии и фон строки Avito: без изменения данных и высоты исходной строки.

### `browser_extensions/avito_check/orders-background.js`

Разрешённые команды заказов; Avito не получает ключей или доступа к CRM напрямую.

### `browser_extensions/avito_check/orders-crm.js`

Мост session/CSRF только на фиксированном маршруте CRM.

### `browser_extensions/avito_check/orders.css`

Цвет строки дополняет текст Avito; размеры и отступы исходной строки сохраняются.

### `browser_extensions/avito_check/orders.js`

Заказы Avito: только видимые данные текущей страницы, без изменения заказа на Avito.

### `browser_extensions/avito_check/panel.js`

ReSOURCE: Панель на Avito: минимальная цена, сохранение/пропуск и следующий товар, без служебных API-ключей.

### `browser_extensions/avito_check/protocol.js`

ReSOURCE: Протокол сообщений расширения между CRM, background и Avito; проверка источника обязательна.

### `static/css/admin-gamebat.css`

ReSOURCE: Оформление Django Admin в оболочке ReSOURCE. Стили не заменяют серверные учётные проверки.

### `static/css/avito-check-list.css`

ReSOURCE: Оформление ручной таблицы Avito Check. Стили не заменяют серверные учётные проверки.

### `static/css/avito-required-actions.css`

ReSOURCE: Оформление необходимых действий/уведомлений Avito. Стили не заменяют серверные учётные проверки.

### `static/css/consignment-actions.css`

ReSOURCE: Оформление действий партии реализации. Стили не заменяют серверные учётные проверки.

### `static/css/creditor-debt.css`

ReSOURCE: Оформление Предпросмотр абсолютной/относительной коррекции долга; конечный баланс берётся под серверной блокировкой.. Стили не заменяют серверные учётные проверки.

### `static/css/creditors.css`

ReSOURCE: Оформление финансовых карточек/знака долга. Стили не заменяют серверные учётные проверки.

### `static/css/fbs-pricing.css`

ReSOURCE: Оформление Предпросмотр/сохранение расчёта FBS; итоговую цену и ограничения проверяет сервер.. Стили не заменяют серверные учётные проверки.

### `static/css/gamebat.css`

ReSOURCE: Оформление общих панелей, таблиц и форм ReSOURCE. Стили не заменяют серверные учётные проверки.

### `static/css/market-notifications.css`

ReSOURCE: Оформление бейджей и сообщений Яндекса. Стили не заменяют серверные учётные проверки.

### `static/css/navigation.css`

ReSOURCE: Оформление адаптивной навигации и мобильного диалога. Стили не заменяют серверные учётные проверки.

### `static/css/nomenclature-bulk-delete.css`

ReSOURCE: Оформление Выбор и подтверждение массового удаления карточек; связи/историю проверяет backend.. Стили не заменяют серверные учётные проверки.

### `static/css/order-trips.css`

ReSOURCE: Оформление таблиц поставщиков и состояний рейса. Стили не заменяют серверные учётные проверки.

### `static/css/orders-list.css`

ReSOURCE: Оформление списка рейсов/заказов. Стили не заменяют серверные учётные проверки.

### `static/css/procurement-suppliers.css`

ReSOURCE: Оформление выбора предложения поставщика. Стили не заменяют серверные учётные проверки.

### `static/css/product-options.css`

ReSOURCE: Оформление Управление полями карточки, новинкой и исключениями поставщика с серверными permissions.. Стили не заменяют серверные учётные проверки.

### `static/css/sale-market.css`

ReSOURCE: Оформление действий и печати Yandex-продажи. Стили не заменяют серверные учётные проверки.

### `static/css/sales-list.css`

ReSOURCE: Оформление читаемых строк продажи и статусов. Стили не заменяют серверные учётные проверки.

### `static/css/stock-order-form.css`

ReSOURCE: Оформление Ручная закупка на склад и подсказка ранее заказанного складского количества, без подмешивания клиентских назначений.. Стили не заменяют серверные учётные проверки.

### `static/css/supply-price-review.css`

ReSOURCE: Оформление проверки цен по будущей средней себестоимости. Стили не заменяют серверные учётные проверки.

### `static/css/test-environment.css`

Только local_test. Цвета товаров, денег, ошибок и обычных кнопок не меняются.

### `static/css/trip-finalization.css`

ReSOURCE: Оформление компактной финализации рейса. Стили не заменяют серверные учётные проверки.

### `static/css/updates.css`

Страница ручного обновления: длинные SHA и журнал остаются в границах экрана.

### `static/css/warehouse-revision.css`

ReSOURCE: Оформление Мобильная сверка выбранного склада с общим scanner; отметки ревизии сами не меняют физический остаток.. Стили не заменяют серверные учётные проверки.

### `static/css/workers.css`

Мониторинг использует панели, таблицы и цвета ReSOURCE.

### `static/css/yandex-market.css`

ReSOURCE: Оформление Формы FBS и упаковка; входящие параметры/доступные действия повторно валидирует сервер.. Стили не заменяют серверные учётные проверки.

### `static/js/app.js`

ReSOURCE: Общая оболочка CRM: сворачивание, фокус и регистрация глобального сканера. Обработчики страниц используют window.GameBAT, не перехватывают обычный ввод.

### `static/js/avito-alert-sound.js`

ReSOURCE: Звуковой канал Avito и взаимодействие с разрешением воспроизведения.

### `static/js/avito-check-list.js`

ReSOURCE: Ручной минимум Avito и передача разрешённого контекста расширению; найденная цена отделена от цены продажи.

### `static/js/avito-check.js`

ReSOURCE: Автоматическая проверка рынка, результат и управление состоянием запроса.

### `static/js/avito-notifications.js`

ReSOURCE: Бейдж и звук новых необходимых действий Avito, без повторного сигнала на неизменившийся список.

### `static/js/avito-required-actions.js`

ReSOURCE: Локальные действия списка объявлений и обновление статусов; внешнее состояние подтверждает сервер.

### `static/js/avito-sync-progress.js`

ReSOURCE: Опрос прогресса задания Avito; постановка в очередь не равна завершённой синхронизации.

### `static/js/barcode-formset.js`

ReSOURCE: Ввод штрихкодов и добавление строк formset с сохранением обычного клавиатурного ввода.

### `static/js/consignment-actions.js`

ReSOURCE: Действия конкретной партии stock_id, вознаграждение/возврат/продажа и защита повторной отправки.

### `static/js/consignment-transfer.js`

ReSOURCE: Форма передачи конкретного физического склада на площадку реализации.

### `static/js/creditor-debt.js`

ReSOURCE: Предпросмотр абсолютной/относительной коррекции долга; конечный баланс берётся под серверной блокировкой.

### `static/js/fbs-pricing.js`

ReSOURCE: Предпросмотр/сохранение расчёта FBS; итоговую цену и ограничения проверяет сервер.

### `static/js/fbs-settings.js`

ReSOURCE: Интерфейс параметров FBS-интеграции, без хранения API-секретов на клиенте.

### `static/js/market-notification-state.js`

ReSOURCE: Чистое состояние повторов и подтверждений уведомлений, отделённое от DOM и внешнего API.

### `static/js/market-notifications.js`

ReSOURCE: Опрос локального внимания к заказам Яндекса; подтверждение уведомления не означает готовность к отгрузке.

### `static/js/navigation.js`

ReSOURCE: Единственная адаптивная навигация: перенос существующих узлов в «Ещё»/мобильный диалог без дублирования ID и обработчиков.

### `static/js/nomenclature-bulk-delete.js`

ReSOURCE: Выбор и подтверждение массового удаления карточек; связи/историю проверяет backend.

### `static/js/notification-sound-controls.js`

ReSOURCE: Единый пользовательский регулятор звука нескольких каналов; учитывает блокировку autoplay браузером.

### `static/js/order-trips.js`

ReSOURCE: Выбор/привязка заказов и действия таблицы рейсов с проверкой ревизии на сервере.

### `static/js/partner-customers.js`

ReSOURCE: Выбор связанного партнёра или разрешённого текстового заказчика; текст не создаёт финансовую связь.

### `static/js/partner-platform.js`

ReSOURCE: Создание площадки реализации в форме партнёра без независимого дублирования контрагента.

### `static/js/partner-settlements.js`

ReSOURCE: Предпросмотр/подтверждение знакового долга. Клиентские суммы в копейках/BigInt, токен повторно сверяется сервером.

### `static/js/price-links.js`

ReSOURCE: Публичные ссылки прайсов с сохранением выбранного контекста.

### `static/js/price.js`

ReSOURCE: Действия прайсов/экспортов и пользовательские поля формирования документа.

### `static/js/pricing-scroll.js`

ReSOURCE: Восстановление позиции таблицы цен; не изменяет финансовые значения.

### `static/js/pricing.js`

ReSOURCE: AJAX-сохранение полевых цен с серверной валидацией и сохранением контекста таблицы.

### `static/js/procurement-pricing.js`

ReSOURCE: Расчётные поля закупочного прайса, наценка/постоплата и серверное подтверждение изменений.

### `static/js/product-cost-confirmation.js`

ReSOURCE: Подтверждение значимого изменения стоимости карточки; сервер остаётся источником правил.

### `static/js/product-image-preview.js`

ReSOURCE: Превью защищённых изображений товара с управлением доступным состоянием наведения.

### `static/js/product-options.js`

ReSOURCE: Управление полями карточки, новинкой и исключениями поставщика с серверными permissions.

### `static/js/sale-market-actions.js`

ReSOURCE: Прямые действия Яндекс-заказа; отмена требует подтверждения, готовность проверяет сервер.

### `static/js/sale-market-print.js`

ReSOURCE: Постановка и опрос задачи тихой печати; браузерный ответ не заменяет подтверждение принтера.

### `static/js/sale-market-scan.js`

ReSOURCE: Сборка заказа Яндекса сканами через общий scanner; готовность возможна только после полного состава и печати.

### `static/js/sales-channels.js`

ReSOURCE: Согласование типа продажи и доступного типа цены; оптовая цена предназначена оптовому сценарию.

### `static/js/sales-statistics.js`

ReSOURCE: Выбор и раскрытие продаж в отчёте, без пересчёта исторических снимков на клиенте.

### `static/js/sales-status.js`

ReSOURCE: Асинхронные переходы продажи и обработка устаревшей версии; оплата и доставка раздельны.

### `static/js/stock-lines.js`

ReSOURCE: Управление товарными строками/показателями доступности; фактическое наличие проверяется сервером.

### `static/js/stock-order-form.js`

ReSOURCE: Ручная закупка на склад и подсказка ранее заказанного складского количества, без подмешивания клиентских назначений.

### `static/js/storage-locations.js`

ReSOURCE: Назначение и автодополнение мест хранения конкретного склада.

### `static/js/supply-finalization.js`

ReSOURCE: Точные инструменты перераспределения затрат, используемые приходом и рейсом; контрольный итог сохраняется.

### `static/js/supply.js`

ReSOURCE: Форма прихода: состав, вес, CUSA/PPSA, штрихкоды и цены. Проведение подтверждается серверным сервисом.

### `static/js/trip-additions.js`

ReSOURCE: Шаги дополнительных партий, расчёт и распределение по заказчикам с серверным контролем сумм количеств.

### `static/js/trip-invoices.js`

ReSOURCE: Сохраняемый флаг инвойса и блокировка блока поставщика; backend повторно проверяет доступность изменения.

### `static/js/trip-prices.js`

ReSOURCE: Предпросмотр и подтверждение закупочной AED-цены партии рейса, без изменения глобального прайса поставщика.

### `static/js/trip-supply-expenses.js`

ReSOURCE: Независимые расходы рейсового прихода перед обычной проверкой средней себестоимости; доставка рейса не дублируется.

### `static/js/warehouse-revision.js`

ReSOURCE: Мобильная сверка выбранного склада с общим scanner; отметки ревизии сами не меняют физический остаток.

### `static/js/wholesale-margin.js`

ReSOURCE: Клиентское предупреждение о наценке; порог не является формулой автоматического изменения цены.

### `static/js/worker-monitoring.js`

Локальный статус и отдельный звуковой канал. GET не запускает обработчики.

### `static/js/yandex-market.js`

ReSOURCE: Формы FBS и упаковка; входящие параметры/доступные действия повторно валидирует сервер.

### `static/resource/crop-preview.js`

ReSOURCE: Предпросмотр кадрирования изображения; исходный защищённый файл не становится публичным целиком.

### `static/resource/storefront.css`

ReSOURCE: Оформление Каталог, корзина и оформление оптовой/розничной витрины; наличие/цена повторно проверяются при отправке.. Стили не заменяют серверные учётные проверки.

### `static/resource/storefront.js`

ReSOURCE: Каталог, корзина и оформление оптовой/розничной витрины; наличие/цена повторно проверяются при отправке.

### `static/resource/tokens.css`

ReSOURCE: Оформление дизайн-токенов витрин. Стили не заменяют серверные учётные проверки.

## Тесты Python/CJS и браузерные проверки (215)

### `GameBAT_CRM/test_guard.py`

Дополнительный запрет стандартных транспортов и чужой SQLite в local_test.

Это защита от случайного обхода клиентской политики, не ОС-песочница для враждебного
Python/C-кода. Отдельная инфраструктурная сеть остаётся обязательной для такого кода.

### `accounts/tests.py`

### `browser_extensions/avito_check/test_background.cjs`

### `browser_extensions/avito_check/test_cards.cjs`

### `browser_extensions/avito_check/test_orders_background.cjs`

### `cash/tests.py`

### `catalog/features_browser_checks.py`

Проверка реальных форм и JS в Chromium на отдельной тестовой БД.

### `catalog/newness_browser_settings.py`

Отдельная SQLite только для явного запуска браузерных проверок карточек.

### `catalog/test_game_series.py`

### `catalog/test_migrations.py`

### `catalog/test_multiple_barcodes.py`

### `catalog/test_nomenclature.py`

### `catalog/test_nomenclature_grouping.py`

Эталонная иерархия номенклатуры и сохранение строк документов.

### `catalog/test_operation_search.py`

### `catalog/test_packaging_defaults.py`

Стандартные размеры при создании и сохранение ручных габаритов.

### `catalog/test_price_markup_migration.py`

### `catalog/test_product_browsing.py`

### `catalog/test_product_creation.py`

### `catalog/test_product_media.py`

### `catalog/test_product_options_js.cjs`

### `catalog/test_product_ordering.py`

Порядок прайса в таблицах CRM и сохранность строк при группировке.

### `catalog/test_product_removal.py`

### `catalog/test_supplier_newness.py`

### `catalog/test_weight_barcodes.py`

### `catalog/tests.py`

### `consignment/excel_browser_checks.py`

Явно запускаемая браузерная проверка скачивания на отдельной тестовой БД.

### `consignment/test_actions_js.cjs`

### `consignment/test_excel.py`

Проверки выгрузки реализации: права, реальные остатки, партии и отсутствие затрат.

### `consignment/test_opening_balances.py`

### `consignment/test_reports.py`

### `consignment/test_reward.py`

### `consignment/test_row_actions.py`

### `consignment/tests.py`

### `core/crm_complex_browser_checks.py`

Сквозные проверки новых форм на отдельной SQLite без внешних интеграций.

### `core/local_test_browser_checks.py`

Браузерная приёмка отдельно запущенного local_test; live URL не открываются.

### `core/navigation_browser_checks.py`

Проверка фактического переполнения шапки и мобильного меню в Chromium.

### `core/sound_browser_checks.py`

Общая кнопка звука: включение каналов, отказ autoplay и компактная шапка.

### `core/test_barcode_focus_js.cjs`

### `core/test_coinbase.py`

### `core/test_collapse_js.cjs`

### `core/test_container_runtime.py`

Жизненный цикл контейнера проверяется только фиктивными процессами без БД и API.

### `core/test_environments.py`

Запуски настроек проверяются в отдельных процессах без чтения рабочей БД.

### `core/test_external_isolation.py`

Подменённые транспорты доказывают запрет до сетевого/физического эффекта.

### `core/test_local_network.py`

Проверки запуска LAN без изменения сетевых настроек и рабочих процессов.

### `core/test_rapira.py`

### `core/test_updates.py`

Обновление доступно только администратору production и только по явному POST.

### `core/test_warehouse_defaults.py`

### `core/tests.py`

### `core/updates_browser_checks.py`

Кнопка локальной CRM и меню обновлений на отдельной тестовой БД.

### `creditors/debt_browser_checks.py`

Изменение долга в браузере с проверкой проводки в отдельной БД.

### `creditors/test_debt_adjustment.py`

Итоговая сумма и относительное изменение через прежний денежный журнал.

### `creditors/tests.py`

### `deployment/ci_browser_settings.py`

### `deployment/test_docker_backend.py`

### `deployment/test_gateway.py`

### `deployment/test_github.py`

### `deployment/test_manager.py`

Проверки очереди без настоящего Docker, GitHub, БД CRM и маркетплейсов.

### `deployment/test_policy.py`

### `deployment/test_store.py`

### `integrations/notification_browser_checks.py`

Два счётчика в шапке, переход к действиям и обновление без вызовов Avito.

### `integrations/test_action_schedule.py`

Периодическая проверка не меняет публикации и не обходит очередь повторов.

### `integrations/test_avito_check.py`

### `integrations/test_avito_notifications_js.cjs`

### `integrations/test_google_sheets.py`

### `integrations/test_linux_processes.py`

Распознавание только процессов данного контейнера без Docker socket и реальных API.

### `integrations/test_required_actions.py`

### `integrations/test_worker_monitoring.py`

Контроль процессов проверяется без запуска API, Windows-печати и рабочих worker.

### `integrations/tests.py`

### `integrations/worker_browser_checks.py`

Реальный Chromium и отдельная БД; ОС, внешние API и принтер не запускаются.

### `orders/arrival_browser_checks.py`

Полный цикл рейса в Chromium на отдельной тестовой БД.

### `orders/arrival_layout_browser_checks.py`

Проверка плотности финализации рейса в настоящем Chromium.

### `orders/empty_trips_browser_checks.py`

Пустой рейс → дополнительная партия → привязка обычным заказом в Chromium.

### `orders/fulfillment_browser_checks.py`

Актуальный сквозной сценарий рейса перенесён в arrival_browser_checks.

Прежняя форма отдельных валютных курсов и индивидуальная финализация
рейсового прихода заменены общей фиксацией прибытия и затрат.

### `orders/stock_order_form_browser_checks.py`

Ручной складской заказ на двух ширинах; только тестовая БД и подменённые курсы.

### `orders/stock_orders_browser_checks.py`

Путь скачивание → складской заказ → рейс → приход в изолированном Chromium.

### `orders/test_arrival.py`

Прибытие, сверка и общая финализация фактических затрат рейса.

### `orders/test_arrival_concurrency.py`

Версия рейса и сериализация конкурентных сверок количества.

### `orders/test_arrival_documents.py`

Отдельные документы рейса, источники строк и запрет раннего проведения.

### `orders/test_arrival_edge_cases.py`

Непоступление, партии, отложенные цены и атомарность общих затрат.

### `orders/test_arrival_finalization.py`

Общая финализация сохраняет сумму рейса и не проводит его документы.

### `orders/test_arrival_http.py`

Пользовательский путь без повторного ввода курсов и индивидуальной финализации.

### `orders/test_arrival_math.py`

Денежные инварианты фактической доставки и копеечных групп единиц.

### `orders/test_arrival_price_review.py`

Приход рейса подтверждает цены по средней себестоимости физического склада.

### `orders/test_arrival_schema_compatibility.py`

Прежний worker может писать обычные строки после расширения схемы.

### `orders/test_arrival_tariffs.py`

Пропорции исторических тарифов дисков и разных категорий техники.

### `orders/test_empty_trips.py`

Пустой рейс, дополнительные партии и привязка первым обычным заказом.

### `orders/test_excel_grouping.py`

Группировка обычного состава заказа и отдельных таблиц рейса.

### `orders/test_fulfillment.py`

Стоимость, склад, жизненный цикл и повторные запросы операций из рейса.

### `orders/test_operation_changes.py`

Отличия документа от заказа требуют точного подтверждения до любых проводок.

### `orders/test_stock_order_form.py`

Создание складского импортного заказа без Excel и совместимость загрузки.

### `orders/test_stock_order_form_js.cjs`

### `orders/test_stock_orders.py`

Закупка на наличие: сохранённая цена, общие рейсы и одноразовый приход.

### `orders/test_supplier_export.py`

Экспорт одного заказа по фактическим поставщикам и сохранённым закупочным ценам.

### `orders/test_trip_additions.py`

### `orders/test_trip_assignment.py`

Перенос целых заказов между рейсами без изменения их цен, денег и количества.

### `orders/test_trip_completion.py`

Завершение рейса следует за продажами и приходами без отдельной записи в БД.

### `orders/test_trip_display.py`

Порядок товаров внутри каждого поставщика без изменения партий рейса.

### `orders/test_trip_full_export.py`

Общий Excel рейса: снимки AED, сортировка, объединение и доступ.

### `orders/test_trip_invoices.py`

Отметка инвойса блокирует только редактирование с HTTP-страницы рейса.

### `orders/test_trip_price_concurrency.py`

Одновременная корректировка и передача закупки не переписывают историю.

### `orders/test_trip_prices.py`

Цена закупки рейса меняет расходы магазина, сохраняя цены покупателей.

### `orders/test_trip_reductions.py`

Уменьшение закупки у последнего поставщика и автоматические однозначные доли.

### `orders/test_trip_reductions_js.cjs`

### `orders/test_trips.py`

### `orders/tests.py`

### `orders/trip_completion_browser_checks.py`

Серый завершённый рейс и возврат в работу после отмены прихода, отдельная БД.

### `orders/trip_export_browser_checks.py`

Скачивание общего состава рейса из таблицы заказов в Chromium.

### `orders/trip_invoice_browser_checks.py`

Сохранение отметки, выделение таблицы и восстановление редактирования в браузере.

### `orders/trip_price_browser_checks.py`

Предпросмотр цены и сохранение в реальном Chromium на отдельной БД.

### `orders/trip_reductions_browser_checks.py`

Уменьшение строк рейса в Chromium на отдельной тестовой БД.

### `orders/trips_browser_checks.py`

Полный сценарий рейса в Chromium на изолированной тестовой БД.

### `partners/partner_browser_checks.py`

Полный путь оптовой продажи с подтверждением взаимозачёта в Chromium.

### `partners/platform_browser_checks.py`

Проверки создания площадок в Chromium на отдельной тестовой базе.

### `partners/telegram_browser_checks.py`

Поле Telegram и открытие новой вкладки проверяются без обращения к чужому чату.

### `partners/test_partner_concurrency.py`

Две параллельные продажи не могут зачесть один и тот же остаток долга.

### `partners/test_partners.py`

Партнёры, подписанный прайс, взаимные долги и единый финансовый отчёт.

### `partners/test_platform_creation.py`

Создание площадки отдельно и в одной транзакции с партнёром.

### `partners/test_priority.py`

### `partners/test_telegram.py`

Сохранение Telegram, повтор формы и защита контакта правами справочника.

### `partners/tests.py`

### `price/anonymous_wholesale_browser_checks.py`

Безымянный оптовый прайс: скачивание, импорт и выбор заказчика в браузере.

### `price/procurement_browser_settings.py`

Отдельная SQLite для явного запуска браузерных проверок закупочного прайса.

### `price/procurement_suppliers_browser_checks.py`

Выбор поставщика и сохранение в Chromium, без рабочего API и рабочей БД.

### `price/test_nomenclature_excel.py`

Группировка закупочных файлов и совместимость обратного импорта.

### `price/test_postpayment_backfill.py`

### `price/test_postpayment_surcharges.py`

### `price/test_procurement_delivery.py`

### `price/test_procurement_memory.py`

### `price/test_procurement_pricing.py`

### `price/test_procurement_pricing_js.cjs`

### `price/test_procurement_suppliers.py`

Закрепление выбранного поставщика, точный пересчёт и защита снимка прайса.

### `price/test_sony_gamepad_sorting.py`

### `price/test_supplier_import.py`

### `price/test_supplier_newness_rounding.py`

### `price/tests.py`

### `pricing/avito_extension_browser_checks.py`

Реальное MV3-расширение в Chromium: Avito подменён локальным ответом, CRM настоящая тестовая.

### `pricing/test_avito_check_list.py`

### `pricing/test_avito_manual_queue.py`

Очередь расширения использует список Avito Check и существующий аудит найденной цены.

### `pricing/test_fbs_js.cjs`

### `pricing/test_price_warnings.py`

### `pricing/test_pricing_js.cjs`

### `pricing/test_pricing_scroll.cjs`

### `pricing/tests.py`

### `print_agent/test_engine.py`

Транспорт и восстановление проверяются без настоящей печати и сети.

### `resource_storefront/catalog_browser_checks.py`

Явная проверка сетки на реальных фото, только в тестовой БД.

### `resource_storefront/retail_browser_checks.py`

Розничный путь покупателя в отдельной SQLite; оплата в тесте задаётся явно.

### `resource_storefront/test_catalog_crops.py`

### `resource_storefront/test_mobile.py`

### `resource_storefront/test_refinement.py`

### `resource_storefront/test_retail.py`

### `resource_storefront/test_storefront.py`

### `resource_storefront/test_storefront_js.cjs`

### `sales/avito_orders_browser_checks.py`

MV3 Chromium с подменённым Avito: форма, связь продажи и очередь этикетки.

### `sales/invoice_browser_checks.py`

Скачивание накладной из карточки продажи на отдельной тестовой БД.

### `sales/market_browser_checks.py`

Изолированная проверка управления Маркетом в Chromium, без рабочего API и worker.

### `sales/market_scan_browser_checks.py`

Сканер и подтверждённая печать на отдельной тестовой БД, без рабочего API и принтера.

### `sales/notification_browser_checks.py`

Реальные вкладки/IndexedDB, изолированные данные и подменённый проигрыватель.

### `sales/partner_debt_browser_checks.py`

Создание продаж в долг обоими способами через реальную форму Chromium.

### `sales/payment_browser_checks.py`

Проверка оплаты в Chromium с отдельной тестовой БД и снимками интерфейса.

### `sales/price_type_browser_checks.py`

Выбор оптовой цены и сохранение продажи в изолированном Chromium.

### `sales/print_agent_browser_checks.py`

Живая страница агента и ручная проверка результата, только отдельная БД.

### `sales/statistics_browser_checks.py`

Читаемость карточек, раскрытие операций и состав продаж в Chromium.

### `sales/system_browser_settings.py`

Настройки только для явного запуска изолированных браузерных проверок.

### `sales/system_products_browser_checks.py`

Реальный браузер и отдельная тестовая БД, без рабочих продаж и интеграций.

### `sales/test_avito_commission.py`

### `sales/test_avito_orders.py`

Заказы расширения: никаких реальных заказов, внешних API и физической печати.

### `sales/test_cancellation.py`

### `sales/test_cash_received_notes.py`

### `sales/test_channels.py`

Каналы меняют видимость таблиц, сохраняя типы и исторические документы.

### `sales/test_custom_items.py`

### `sales/test_discounts_and_consignment.py`

### `sales/test_discounts_js.cjs`

### `sales/test_independent_rows.py`

### `sales/test_invoice.py`

### `sales/test_label_printing.py`

### `sales/test_listing.py`

### `sales/test_local_inventory_ui.py`

### `sales/test_market_actions_js.cjs`

### `sales/test_market_controls.py`

Стикер и разрешённые действия Маркета доступны из продажи без ручной подмены статусов.

### `sales/test_market_notification_state_js.cjs`

### `sales/test_market_print_js.cjs`

### `sales/test_market_scan_js.cjs`

### `sales/test_market_scanning.py`

### `sales/test_notifications.py`

Новые заказы, права и подтверждение без влияния на склад/деньги/статусы.

### `sales/test_order_statuses.py`

Удаление промежуточного статуса сохраняет денежные снимки и историю продаж.

### `sales/test_partner_debt.py`

Продажа в долг, нулевое получение наличных и обратимость финансового журнала.

### `sales/test_payment_methods.py`

Четыре способа оплаты: суммы, склад, касса, история и общие отчёты.

### `sales/test_payment_methods_js.cjs`

### `sales/test_payment_partner.py`

Явная привязка партнёра при частичной оплате ранее созданной продажи.

### `sales/test_price_type.py`

Оптовая цена доступна только при создании оптовой продажи.

### `sales/test_price_type_js.cjs`

### `sales/test_print_agents.py`

Протокол печати проверяется на искусственных заказах и PDF, без оборудования/API.

### `sales/test_sales_status_js.cjs`

### `sales/test_statistics.py`

### `sales/test_system_products.py`

Системные операции: штрихкоды, снимки, касса, склад, отчёт и запреты backend.

### `sales/test_system_products_js.cjs`

### `sales/tests.py`

### `scripts/test_repository_hygiene.py`

Интеграционные проверки защиты Git на отдельных временных репозиториях.

### `supplies/pending_browser_checks.py`

Остатки и места хранения в редакторе до и после приёмки, на тестовой БД.

### `supplies/test_cancellation.py`

### `supplies/test_finalization.py`

### `supplies/test_game_codes.py`

### `supplies/test_pending_edit.py`

Редактирование прихода до приёмки без изменения физического учёта.

### `supplies/test_price_review.py`

### `supplies/test_revision.py`

### `supplies/test_weight_transport.py`

### `supplies/tests.py`

### `warehouse/test_revision.py`

### `warehouse/test_storage_locations.py`

### `warehouse/tests.py`

### `yandex_market/test_boxes_js.cjs`

### `yandex_market/test_fbs_pricing.py`

FBS: формула, округления, общие габариты и изоляция публикации цены.

### `yandex_market/test_label_cache.py`

PDF готовится отдельно от печати и хранится до завершения заказа.

### `yandex_market/test_sync_recovery.py`

Сверка продолжает независимые участки обмена при сбое одного метода API.

### `yandex_market/tests.py`

Проверки на изолированной БД и подменённом API; рабочие ключи не используются.

## Миграции (160)

### `accounts/migrations/0001_initial.py`

Зависимости: `[('auth', '0012_alter_user_first_name_max_length')]`.

### `cash/migrations/0001_initial.py`

Зависимости: `[('sales', '0001_initial'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `cash/migrations/0002_ensure_warehouse_cash_registers.py`

Зависимости: `[('cash', '0001_initial')]`.

Преобразования данных: `ensure_warehouse_cash_registers`. Не удалять только по возрасту файла.

### `cash/migrations/0003_cashtransaction_operation_key_and_more.py`

Зависимости: `[('cash', '0002_ensure_warehouse_cash_registers'), ('sales', '0002_sale_consignment_platform_alter_sale_price_type_and_more'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `cash/migrations/0004_ensure_warehouse_safes.py`

Зависимости: `[('cash', '0003_cashtransaction_operation_key_and_more')]`.

Преобразования данных: `ensure_warehouse_safes`. Не удалять только по возрасту файла.

### `cash/migrations/0005_remove_cashtransaction_cash_transaction_safe_matches_type.py`

Зависимости: `[('cash', '0004_ensure_warehouse_safes')]`.

### `cash/migrations/0006_cashtransaction_customer_order_and_more.py`

Зависимости: `[('cash', '0005_remove_cashtransaction_cash_transaction_safe_matches_type'), ('orders', '0001_initial'), ('sales', '0003_alter_sale_options'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `cash/migrations/0007_remove_cashtransaction_cash_transaction_safe_matches_type_and_more.py`

Зависимости: `[('cash', '0006_cashtransaction_customer_order_and_more'), ('orders', '0002_initial'), ('sales', '0003_alter_sale_options'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `cash/migrations/0008_cashtransaction_sale_cash_operation_has_sale.py`

Зависимости: `[('cash', '0007_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('orders', '0002_initial'), ('sales', '0004_alter_sale_options_sale_cancellation_comment_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `cash/migrations/0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more.py`

Зависимости: `[('cash', '0008_cashtransaction_sale_cash_operation_has_sale'), ('orders', '0002_initial'), ('sales', '0005_alter_sale_price_type'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `catalog/migrations/0001_initial.py`

Зависимости: `[]`.

### `catalog/migrations/0002_multiwarehouse_and_pricing.py`

Зависимости: `[('catalog', '0001_initial'), ('warehouse', '0002_migrate_legacy_stock')]`.

### `catalog/migrations/0003_cost_two_decimal_places.py`

Зависимости: `[('catalog', '0002_multiwarehouse_and_pricing')]`.

Преобразования данных: `round_existing_costs`. Не удалять только по возрасту файла.

### `catalog/migrations/0004_alter_cd_options_alter_tech_options_and_more.py`

Зависимости: `[('catalog', '0003_cost_two_decimal_places'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `catalog/migrations/0005_productchangeevent_action_kind_and_more.py`

Зависимости: `[('catalog', '0004_alter_cd_options_alter_tech_options_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `catalog/migrations/0006_alter_productchangeevent_source.py`

Зависимости: `[('catalog', '0005_productchangeevent_action_kind_and_more')]`.

Преобразования данных: `mark_existing_nomenclature_events`, `restore_legacy_source`. Не удалять только по возрасту файла.

### `catalog/migrations/0007_alter_cd_barcode_alter_tech_barcode.py`

Зависимости: `[('catalog', '0006_alter_productchangeevent_source')]`.

### `catalog/migrations/0008_product_weights_and_optional_sku.py`

Зависимости: `[('catalog', '0007_alter_cd_barcode_alter_tech_barcode')]`.

Преобразования данных: `set_existing_cd_weight`, `clear_cd_weight`. Не удалять только по возрасту файла.

### `catalog/migrations/0009_barcode_registry.py`

Зависимости: `[('catalog', '0008_product_weights_and_optional_sku')]`.

Преобразования данных: `populate_barcode_registry`, `clear_barcode_registry`. Не удалять только по возрасту файла.

### `catalog/migrations/0010_rename_retail_price_to_avito_price.py`

Зависимости: `[('catalog', '0009_barcode_registry')]`.

### `catalog/migrations/0011_cd_default_weight_120.py`

Зависимости: `[('catalog', '0010_rename_retail_price_to_avito_price')]`.

Преобразования данных: `update_cd_weight_to_120`. Не удалять только по возрасту файла.

### `catalog/migrations/0012_alter_productchangeevent_action_kind.py`

Зависимости: `[('catalog', '0011_cd_default_weight_120')]`.

### `catalog/migrations/0013_gameseries_alter_cd_options_cd_game_series.py`

Зависимости: `[('catalog', '0012_alter_productchangeevent_action_kind')]`.

### `catalog/migrations/0014_cd_archived_at_cd_archived_by_cd_is_archived_and_more.py`

Зависимости: `[('catalog', '0013_gameseries_alter_cd_options_cd_game_series'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `catalog/migrations/0015_multiple_product_barcodes.py`

Зависимости: `[('catalog', '0014_cd_archived_at_cd_archived_by_cd_is_archived_and_more')]`.

Преобразования данных: `migrate_legacy_barcodes`, `restore_legacy_barcodes`. Не удалять только по возрасту файла.

### `catalog/migrations/0016_price_markup_fields.py`

Зависимости: `[('catalog', '0015_multiple_product_barcodes')]`.

### `catalog/migrations/0017_initialize_price_markups.py`

Зависимости: `[('catalog', '0016_price_markup_fields')]`.

Преобразования данных: `initialize_markups`. Не удалять только по возрасту файла.

### `catalog/migrations/0018_price_markups_189.py`

Зависимости: `[('catalog', '0017_initialize_price_markups')]`.

Преобразования данных: `set_markups`. Не удалять только по возрасту файла.

### `catalog/migrations/0019_dedupe_platform_names.py`

Зависимости: `[('catalog', '0018_price_markups_189')]`.

Преобразования данных: `merge_case_insensitive_platforms`. Не удалять только по возрасту файла.

### `catalog/migrations/0020_cd_zero_stock_since_tech_zero_stock_since.py`

Зависимости: `[('catalog', '0019_dedupe_platform_names')]`.

Преобразования данных: `initialize_zero_stock_since`. Не удалять только по возрасту файла.

### `catalog/migrations/0021_product_media.py`

Зависимости: `[('catalog', '0020_cd_zero_stock_since_tech_zero_stock_since')]`.

### `catalog/migrations/0022_cd_wholesale_site_enabled_and_more.py`

Зависимости: `[('catalog', '0021_product_media')]`.

### `catalog/migrations/0023_product_stock_history.py`

Зависимости: `[('catalog', '0022_cd_wholesale_site_enabled_and_more'), ('warehouse', '0002_migrate_legacy_stock')]`.

Преобразования данных: `initialize_stock_history`. Не удалять только по возрасту файла.

### `catalog/migrations/0024_supplier_template_exclusion.py`

Зависимости: `[('catalog', '0023_product_stock_history')]`.

### `catalog/migrations/0025_cd_height_cm_cd_length_cm_cd_width_cm_and_more.py`

Зависимости: `[('catalog', '0024_supplier_template_exclusion'), ('yandex_market', '0003_categoryschema_name_categoryschema_placement_rate')]`.

### `catalog/migrations/0026_default_cd_packaging_dimensions.py`

Зависимости: `[('catalog', '0025_cd_height_cm_cd_length_cm_cd_width_cm_and_more')]`.

### `catalog/migrations/0027_default_fbs_desired_profit.py`

Зависимости: `[('catalog', '0026_default_cd_packaging_dimensions')]`.

### `catalog/migrations/0028_default_cd_and_gamepad_profit.py`

Зависимости: `[('catalog', '0027_default_fbs_desired_profit')]`.

### `catalog/migrations/0029_producttype_procurement_delivery_group.py`

Зависимости: `[('catalog', '0028_default_cd_and_gamepad_profit')]`.

Преобразования данных: `assign_delivery_groups`. Не удалять только по возрасту файла.

### `catalog/migrations/0030_systemproduct_and_more.py`

Зависимости: `[('catalog', '0029_producttype_procurement_delivery_group')]`.

### `catalog/migrations/0031_initialize_system_products.py`

Зависимости: `[('catalog', '0030_systemproduct_and_more')]`.

Преобразования данных: `initialize`, `uninitialize`. Не удалять только по возрасту файла.

### `catalog/migrations/0032_supplier_selection_newness_rounding.py`

Зависимости: `[('catalog', '0031_initialize_system_products'), ('partners', '0002_supplier_priority'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `consignment/migrations/0001_initial.py`

Зависимости: `[('catalog', '0001_initial'), ('partners', '0001_initial')]`.

### `consignment/migrations/0002_consignmentmovement.py`

Зависимости: `[('catalog', '0005_productchangeevent_action_kind_and_more'), ('consignment', '0001_initial'), ('partners', '0001_initial'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `consignment/migrations/0003_consignment_multiline_and_sales_amount.py`

Зависимости: `[('catalog', '0007_alter_cd_barcode_alter_tech_barcode'), ('consignment', '0002_consignmentmovement'), ('partners', '0001_initial'), ('warehouse', '0003_transfers')]`.

Преобразования данных: `move_existing_data`. Не удалять только по возрасту файла.

### `consignment/migrations/0004_alter_cdconsignmentstock_options.py`

Зависимости: `[('consignment', '0003_consignment_multiline_and_sales_amount')]`.

### `consignment/migrations/0005_consignmentactionreceipt.py`

Зависимости: `[('consignment', '0004_alter_cdconsignmentstock_options'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `consignment/migrations/0006_consignment_lots.py`

Зависимости: `[('consignment', '0005_consignmentactionreceipt')]`.

### `consignment/migrations/0007_consignment_cost_snapshots.py`

Зависимости: `[('consignment', '0006_consignment_lots')]`.

Преобразования данных: `populate_cost_snapshots`. Не удалять только по возрасту файла.

### `core/migrations/0001_initial.py`

Зависимости: `[]`.

### `creditors/migrations/0001_initial.py`

Зависимости: `[('cash', '0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `creditors/migrations/0002_remove_creditor_creditor_debt_nonnegative_and_more.py`

Зависимости: `[('cash', '0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('creditors', '0001_initial'), ('sales', '0023_market_order_attention')]`.

### `creditors/migrations/0003_partner_settlement_constraints.py`

Зависимости: `[('cash', '0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('creditors', '0002_remove_creditor_creditor_debt_nonnegative_and_more'), ('sales', '0024_remove_sale_sale_cash_received_not_below_total_and_more'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `creditors/migrations/0004_partner_legacy_defaults.py`

Зависимости: `[('creditors', '0003_partner_settlement_constraints')]`.

### `creditors/migrations/0005_alter_creditortransaction_kind.py`

Зависимости: `[('creditors', '0004_partner_legacy_defaults')]`.

### `creditors/migrations/0006_debt_delta_cent_precision.py`

Зависимости: `[('cash', '0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('creditors', '0005_alter_creditortransaction_kind'), ('sales', '0033_trip_cost_sources'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `integrations/migrations/0001_initial.py`

Зависимости: `[('catalog', '0012_alter_productchangeevent_action_kind'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `integrations/migrations/0002_avitoremotelisting_remote_price.py`

Зависимости: `[('integrations', '0001_initial')]`.

### `integrations/migrations/0003_avitossyncjob_manual_progress.py`

Зависимости: `[('integrations', '0002_avitoremotelisting_remote_price')]`.

### `integrations/migrations/0004_avito_status_refresh_job.py`

Зависимости: `[('integrations', '0003_avitossyncjob_manual_progress')]`.

### `integrations/migrations/0005_googlesheetsintegration_googlesheetssyncjob.py`

Зависимости: `[('integrations', '0004_avito_status_refresh_job'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `integrations/migrations/0006_reefapicredential_avitopricecheckresult.py`

Зависимости: `[('integrations', '0005_googlesheetsintegration_googlesheetssyncjob')]`.

### `integrations/migrations/0007_avito_check_economy_cache.py`

Зависимости: `[('integrations', '0006_reefapicredential_avitopricecheckresult')]`.

### `integrations/migrations/0008_avito_manual_price.py`

Зависимости: `[('integrations', '0007_avito_check_economy_cache'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `integrations/migrations/0009_worker_monitoring.py`

Зависимости: `[('integrations', '0008_avito_manual_price'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0001_initial.py`

Зависимости: `[('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0002_initial.py`

Зависимости: `[('catalog', '0007_alter_cd_barcode_alter_tech_barcode'), ('orders', '0001_initial'), ('partners', '0001_initial'), ('price', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0003_suppliertripallocation_suppliertripchange_and_more.py`

Зависимости: `[('catalog', '0031_initialize_system_products'), ('orders', '0002_initial'), ('partners', '0002_supplier_priority'), ('price', '0007_postpayment_surcharges'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0004_customerprocurementorder_purpose_and_more.py`

Зависимости: `[('orders', '0003_suppliertripallocation_suppliertripchange_and_more'), ('supplies', '0010_remove_supply_supply_cancellation_fields_consistent_and_more')]`.

### `orders/migrations/0005_trip_supplier_price.py`

Зависимости: `[('orders', '0004_customerprocurementorder_purpose_and_more')]`.

### `orders/migrations/0006_customerprocurementorder_partner_and_more.py`

Зависимости: `[('orders', '0005_trip_supplier_price'), ('partners', '0003_partner')]`.

### `orders/migrations/0007_partner_legacy_defaults.py`

Зависимости: `[('orders', '0006_customerprocurementorder_partner_and_more')]`.

### `orders/migrations/0008_suppliertripinvoice.py`

Зависимости: `[('orders', '0007_partner_legacy_defaults'), ('partners', '0005_partner_telegram'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0009_trip_additions.py`

Зависимости: `[('orders', '0008_suppliertripinvoice'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0010_triporderoperation.py`

Зависимости: `[('orders', '0009_trip_additions'), ('sales', '0031_consignment_report'), ('supplies', '0010_remove_supply_supply_cancellation_fields_consistent_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `orders/migrations/0011_trip_arrival_costs.py`

Зависимости: `[('catalog', '0032_supplier_selection_newness_rounding'), ('orders', '0010_triporderoperation'), ('partners', '0005_partner_telegram'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `partners/migrations/0001_initial.py`

Зависимости: `[]`.

### `partners/migrations/0002_supplier_priority.py`

Зависимости: `[('partners', '0001_initial')]`.

Преобразования данных: `assign_supplier_priorities`, `reset_supplier_priorities`. Не удалять только по возрасту файла.

### `partners/migrations/0003_partner.py`

Зависимости: `[('creditors', '0002_remove_creditor_creditor_debt_nonnegative_and_more'), ('partners', '0002_supplier_priority')]`.

### `partners/migrations/0004_partner_creation_key.py`

Зависимости: `[('partners', '0003_partner')]`.

Преобразования данных: `fill_keys`. Не удалять только по возрасту файла.

### `partners/migrations/0005_partner_telegram.py`

Зависимости: `[('partners', '0004_partner_creation_key')]`.

### `price/migrations/0001_initial.py`

Зависимости: `[('catalog', '0007_alter_cd_barcode_alter_tech_barcode'), ('partners', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `price/migrations/0002_procurementpricelist_exchange_rate_usdt_aed_and_more.py`

Зависимости: `[('price', '0001_initial')]`.

### `price/migrations/0003_procurementpricelist_delivery_devices_usdt_per_kg_and_more.py`

Зависимости: `[('catalog', '0029_producttype_procurement_delivery_group'), ('price', '0002_procurementpricelist_exchange_rate_usdt_aed_and_more')]`.

### `price/migrations/0004_procurementpricelist_delivery_cd_rub.py`

Зависимости: `[('price', '0003_procurementpricelist_delivery_devices_usdt_per_kg_and_more')]`.

### `price/migrations/0005_remembered_prices_and_negative_markup.py`

Зависимости: `[('catalog', '0029_producttype_procurement_delivery_group'), ('price', '0004_procurementpricelist_delivery_cd_rub'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

Преобразования данных: `seed_remembered_prices`. Не удалять только по возрасту файла.

### `price/migrations/0006_remember_markup_instead_of_final_price.py`

Зависимости: `[('price', '0005_remembered_prices_and_negative_markup')]`.

Преобразования данных: `_copy_source_value`, `remember_markup`, `restore_final_price`. Не удалять только по возрасту файла.

### `price/migrations/0007_postpayment_surcharges.py`

Зависимости: `[('catalog', '0029_producttype_procurement_delivery_group'), ('partners', '0002_supplier_priority'), ('price', '0006_remember_markup_instead_of_final_price'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `price/migrations/0008_procurementpricelist_supplier_offers_complete_and_more.py`

Зависимости: `[('partners', '0002_supplier_priority'), ('price', '0007_postpayment_surcharges')]`.

### `price/migrations/0009_saved_selected_supplier_offers.py`

Зависимости: `[('price', '0008_procurementpricelist_supplier_offers_complete_and_more')]`.

Преобразования данных: `preserve_selected_offers`. Не удалять только по возрасту файла.

### `price/migrations/0010_supplier_selection_newness_rounding.py`

Зависимости: `[('catalog', '0032_supplier_selection_newness_rounding'), ('partners', '0002_supplier_priority'), ('price', '0009_saved_selected_supplier_offers')]`.

### `price/migrations/0011_trip_addition_snapshot.py`

Зависимости: `[('price', '0010_supplier_selection_newness_rounding')]`.

### `pricing/migrations/0001_initial.py`

Зависимости: `[('catalog', '0002_multiwarehouse_and_pricing'), ('partners', '0001_initial')]`.

### `pricing/migrations/0002_supplier_price_default_zero.py`

Зависимости: `[('pricing', '0001_initial')]`.

### `pricing/migrations/0003_alter_suppliercdprice_options.py`

Зависимости: `[('pricing', '0002_supplier_price_default_zero')]`.

### `resource_storefront/migrations/0001_initial.py`

Зависимости: `[('catalog', '0022_cd_wholesale_site_enabled_and_more'), ('sales', '0014_merge_wholesale_sale_types'), ('warehouse', '0005_transfer_cost_snapshots'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `resource_storefront/migrations/0002_initialize_storefront_warehouse.py`

Зависимости: `[('resource_storefront', '0001_initial'), ('warehouse', '0005_transfer_cost_snapshots')]`.

Преобразования данных: `configure_known_warehouse`. Не удалять только по возрасту файла.

### `resource_storefront/migrations/0003_catalogimagecrop.py`

Зависимости: `[('catalog', '0022_cd_wholesale_site_enabled_and_more'), ('resource_storefront', '0002_initialize_storefront_warehouse')]`.

### `resource_storefront/migrations/0004_retailsettings_retailsubmission.py`

Зависимости: `[('resource_storefront', '0003_catalogimagecrop'), ('sales', '0015_sale_buyer_address_snapshot_sale_buyer_comment_and_more'), ('warehouse', '0005_transfer_cost_snapshots')]`.

### `resource_storefront/migrations/0005_initialize_retail_warehouse.py`

Зависимости: `[('resource_storefront', '0004_retailsettings_retailsubmission')]`.

Преобразования данных: `configure`. Не удалять только по возрасту файла.

### `resource_storefront/migrations/0006_wholesalecontact_partner.py`

Зависимости: `[('partners', '0003_partner'), ('resource_storefront', '0005_initialize_retail_warehouse')]`.

### `sales/migrations/0001_initial.py`

Зависимости: `[('catalog', '0002_multiwarehouse_and_pricing'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0002_sale_consignment_platform_alter_sale_price_type_and_more.py`

Зависимости: `[('partners', '0001_initial'), ('sales', '0001_initial')]`.

### `sales/migrations/0003_alter_sale_options.py`

Зависимости: `[('sales', '0002_sale_consignment_platform_alter_sale_price_type_and_more')]`.

### `sales/migrations/0004_alter_sale_options_sale_cancellation_comment_and_more.py`

Зависимости: `[('partners', '0001_initial'), ('sales', '0003_alter_sale_options'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0005_alter_sale_price_type.py`

Зависимости: `[('sales', '0004_alter_sale_options_sale_cancellation_comment_and_more')]`.

### `sales/migrations/0006_remove_sale_sale_refund_not_above_total_and_more.py`

Зависимости: `[('cash', '0009_remove_cashtransaction_cash_transaction_safe_matches_type_and_more'), ('partners', '0002_supplier_priority'), ('sales', '0005_alter_sale_price_type'), ('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

Преобразования данных: `backfill_cash_received`, `clear_cash_received`. Не удалять только по возрасту файла.

### `sales/migrations/0007_alter_sale_options_salecditem_unit_cost_snapshot_and_more.py`

Зависимости: `[('sales', '0006_remove_sale_sale_refund_not_above_total_and_more')]`.

### `sales/migrations/0008_salecustomitem.py`

Зависимости: `[('sales', '0007_alter_sale_options_salecditem_unit_cost_snapshot_and_more')]`.

### `sales/migrations/0009_salecustomitem_sale_custom_name_nonempty.py`

Зависимости: `[('sales', '0008_salecustomitem')]`.

### `sales/migrations/0010_remove_salecustomitem_sale_custom_cost_nonnegative_and_more.py`

Зависимости: `[('sales', '0009_salecustomitem_sale_custom_name_nonempty')]`.

### `sales/migrations/0011_alter_salecustomitem_article_snapshot.py`

Зависимости: `[('sales', '0010_remove_salecustomitem_sale_custom_cost_nonnegative_and_more')]`.

### `sales/migrations/0012_saleconsignmentitem_salecditem_unit_discount_and_more.py`

Зависимости: `[('catalog', '0020_cd_zero_stock_since_tech_zero_stock_since'), ('partners', '0002_supplier_priority'), ('sales', '0011_alter_salecustomitem_article_snapshot')]`.

### `sales/migrations/0013_salecditem_avito_commission_amount_and_more.py`

Зависимости: `[('catalog', '0020_cd_zero_stock_since_tech_zero_stock_since'), ('sales', '0012_saleconsignmentitem_salecditem_unit_discount_and_more')]`.

### `sales/migrations/0014_merge_wholesale_sale_types.py`

Зависимости: `[('sales', '0013_salecditem_avito_commission_amount_and_more')]`.

Преобразования данных: `merge_wholesale_sale_types`, `restore_wholesale_pickup_type`. Не удалять только по возрасту файла.

### `sales/migrations/0015_sale_buyer_address_snapshot_sale_buyer_comment_and_more.py`

Зависимости: `[('resource_storefront', '0001_initial'), ('sales', '0014_merge_wholesale_sale_types'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0016_sale_buyer_contact_methods_sale_buyer_telegram_and_more.py`

Зависимости: `[('sales', '0015_sale_buyer_address_snapshot_sale_buyer_comment_and_more')]`.

### `sales/migrations/0017_alter_sale_payment_method_and_more.py`

Зависимости: `[('partners', '0002_supplier_priority'), ('resource_storefront', '0005_initialize_retail_warehouse'), ('sales', '0016_sale_buyer_contact_methods_sale_buyer_telegram_and_more'), ('warehouse', '0005_transfer_cost_snapshots'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0018_signed_unit_discount.py`

Зависимости: `[('sales', '0017_alter_sale_payment_method_and_more')]`.

### `sales/migrations/0019_sale_creation_fingerprint_sale_creation_key_and_more.py`

Зависимости: `[('catalog', '0031_initialize_system_products'), ('partners', '0002_supplier_priority'), ('resource_storefront', '0005_initialize_retail_warehouse'), ('sales', '0018_signed_unit_discount'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0020_payment_methods.py`

Зависимости: `[('partners', '0002_supplier_priority'), ('resource_storefront', '0005_initialize_retail_warehouse'), ('sales', '0019_sale_creation_fingerprint_sale_creation_key_and_more'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

Преобразования данных: `migrate_pending_bank_sales`, `reverse_only_empty_sales`. Не удалять только по возрасту файла.

### `sales/migrations/0021_remove_shipped_status.py`

Зависимости: `[('sales', '0020_payment_methods')]`.

Преобразования данных: `remove_shipped_status`. Не удалять только по возрасту файла.

### `sales/migrations/0022_marketpicking_marketscanevent_marketprintjob.py`

Зависимости: `[('sales', '0021_remove_shipped_status'), ('yandex_market', '0006_offerconnection_exchange_defaults'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0023_market_order_attention.py`

Зависимости: `[('sales', '0022_marketpicking_marketscanevent_marketprintjob'), ('yandex_market', '0006_offerconnection_exchange_defaults'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0024_remove_sale_sale_cash_received_not_below_total_and_more.py`

Зависимости: `[('partners', '0003_partner'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0023_market_order_attention'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0025_partner_settlement_constraints.py`

Зависимости: `[('partners', '0003_partner'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0024_remove_sale_sale_cash_received_not_below_total_and_more'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0026_partner_legacy_defaults.py`

Зависимости: `[('sales', '0025_partner_settlement_constraints')]`.

### `sales/migrations/0027_partner_digital_settlement.py`

Зависимости: `[('partners', '0004_partner_creation_key'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0026_partner_legacy_defaults'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0028_remove_sale_sale_cash_received_not_below_total_and_more.py`

Зависимости: `[('partners', '0004_partner_creation_key'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0027_partner_digital_settlement'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0029_partner_partial_payment.py`

Зависимости: `[('partners', '0005_partner_telegram'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0028_remove_sale_sale_cash_received_not_below_total_and_more'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0030_independent_sale_rows.py`

Зависимости: `[('sales', '0029_partner_partial_payment')]`.

### `sales/migrations/0031_consignment_report.py`

Зависимости: `[('sales', '0030_independent_sale_rows')]`.

### `sales/migrations/0032_sale_direct_delivery_sale_procurement_prepaid_amount_and_more.py`

Зависимости: `[('partners', '0005_partner_telegram'), ('resource_storefront', '0006_wholesalecontact_partner'), ('sales', '0031_consignment_report'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `sales/migrations/0033_trip_cost_sources.py`

Зависимости: `[('orders', '0011_trip_arrival_costs'), ('sales', '0032_sale_direct_delivery_sale_procurement_prepaid_amount_and_more')]`.

Преобразования данных: `preserve_existing_direct_sources`. Не удалять только по возрасту файла.

### `sales/migrations/0034_print_agent_delivery.py`

Зависимости: `[('sales', '0033_trip_cost_sources')]`.

### `sales/migrations/0035_avito_browser_orders.py`

Зависимости: `[('sales', '0034_print_agent_delivery'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0001_initial.py`

Зависимости: `[('catalog', '0001_initial'), ('partners', '0001_initial'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0002_supplycditem_supply_cd_allocated_nonnegative_and_more.py`

Зависимости: `[('catalog', '0001_initial'), ('partners', '0001_initial'), ('supplies', '0001_initial')]`.

### `supplies/migrations/0003_supply_warehouse.py`

Зависимости: `[('supplies', '0002_supplycditem_supply_cd_allocated_nonnegative_and_more'), ('warehouse', '0003_transfers')]`.

Преобразования данных: `assign_existing_supplies`. Не удалять только по возрасту файла.

### `supplies/migrations/0004_supplycostcalculation.py`

Зависимости: `[('catalog', '0007_alter_cd_barcode_alter_tech_barcode'), ('supplies', '0003_supply_warehouse')]`.

### `supplies/migrations/0005_alter_supply_options_supply_cancellation_comment_and_more.py`

Зависимости: `[('supplies', '0004_supplycostcalculation'), ('warehouse', '0003_transfers'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0006_supply_total_weight_grams_and_more.py`

Зависимости: `[('catalog', '0010_rename_retail_price_to_avito_price'), ('partners', '0001_initial'), ('supplies', '0005_alter_supply_options_supply_cancellation_comment_and_more'), ('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0007_alter_supply_options_supply_last_revised_at_and_more.py`

Зависимости: `[('catalog', '0011_cd_default_weight_120'), ('partners', '0001_initial'), ('supplies', '0006_supply_total_weight_grams_and_more'), ('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0008_alter_supply_options_supplyfinalization_and_more.py`

Зависимости: `[('catalog', '0012_alter_productchangeevent_action_kind'), ('supplies', '0007_alter_supply_options_supply_last_revised_at_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0009_warehouse_cost_labels.py`

Зависимости: `[('supplies', '0008_alter_supply_options_supplyfinalization_and_more')]`.

### `supplies/migrations/0010_remove_supply_supply_cancellation_fields_consistent_and_more.py`

Зависимости: `[('supplies', '0009_warehouse_cost_labels'), ('warehouse', '0005_transfer_cost_snapshots'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `supplies/migrations/0011_trip_cost_sources.py`

Зависимости: `[('orders', '0011_trip_arrival_costs'), ('supplies', '0010_remove_supply_supply_cancellation_fields_consistent_and_more'), ('warehouse', '0006_warehouse_revision'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `warehouse/migrations/0001_initial.py`

Зависимости: `[('catalog', '0001_initial')]`.

### `warehouse/migrations/0002_migrate_legacy_stock.py`

Зависимости: `[('warehouse', '0001_initial')]`.

Преобразования данных: `forwards`, `backwards`. Не удалять только по возрасту файла.

### `warehouse/migrations/0003_transfers.py`

Зависимости: `[('warehouse', '0002_migrate_legacy_stock'), ('catalog', '0002_multiwarehouse_and_pricing'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `warehouse/migrations/0004_alter_warehouse_options_warehousestoragelocation_and_more.py`

Зависимости: `[('warehouse', '0003_transfers')]`.

### `warehouse/migrations/0005_transfer_cost_snapshots.py`

Зависимости: `[('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more')]`.

Преобразования данных: `populate_cost_snapshots`. Не удалять только по возрасту файла.

### `warehouse/migrations/0006_warehouse_revision.py`

Зависимости: `[('catalog', '0022_cd_wholesale_site_enabled_and_more'), ('warehouse', '0005_transfer_cost_snapshots'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `yandex_market/migrations/0001_initial.py`

Зависимости: `[('catalog', '0018_price_markups_189'), ('sales', '0007_alter_sale_options_salecditem_unit_cost_snapshot_and_more'), ('warehouse', '0004_alter_warehouse_options_warehousestoragelocation_and_more'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]`.

### `yandex_market/migrations/0002_offerconnection_last_sent_state.py`

Зависимости: `[('yandex_market', '0001_initial')]`.

### `yandex_market/migrations/0003_categoryschema_name_categoryschema_placement_rate.py`

Зависимости: `[('yandex_market', '0002_offerconnection_last_sent_state')]`.

### `yandex_market/migrations/0004_offerconnection_sell_on_yandex_default.py`

Зависимости: `[('yandex_market', '0003_categoryschema_name_categoryschema_placement_rate')]`.

### `yandex_market/migrations/0005_offerconnection_resume_display_pending.py`

Зависимости: `[('yandex_market', '0004_offerconnection_sell_on_yandex_default')]`.

### `yandex_market/migrations/0006_offerconnection_exchange_defaults.py`

Зависимости: `[('yandex_market', '0005_offerconnection_resume_display_pending')]`.

### `yandex_market/migrations/0007_label_cache_signature.py`

Зависимости: `[('yandex_market', '0006_offerconnection_exchange_defaults')]`.

## Management commands (22)

### `cash/management/commands/verify_cash.py`

Диагностика балансов кассы/сейфа по журналу; команда ничего не исправляет.

### `catalog/management/commands/backfill_product_newness.py`

План и безопасное однократное присвоение исторического статуса новинки.

### `catalog/management/commands/classify_game_series.py`

Первичная классификация исторической базы CD без сетевых запросов.

### `catalog/management/commands/ensure_system_products.py`

Идемпотентное создание системных цифровых/расходных позиций с сохранением выданных штрихкодов.

### `catalog/management/commands/import_catalog_names.py`

Ручной импорт номенклатуры из внешнего файла; не запускать повторно как процедуру развёртывания.

### `catalog/management/commands/import_current_inventory.py`

Явный перенос исходного наличия из файла; меняет рабочие данные только по отдельному поручению.

### `catalog/management/commands/import_wholesale_prices.py`

Явный импорт оптовых цен; не является миграцией и требует проверки источника/области.

### `catalog/management/commands/verify_inventory.py`

Диагностика физического склада и суммы партий реализации; команда ничего не исправляет.

### `consignment/management/commands/import_itech_consignment.py`

Адресный импорт партий реализации из файла; повторный запуск не является штатной проверкой.

### `consignment/management/commands/replace_playbox_consignment.py`

Адресная замена состава PlayBox; потенциально меняет партии и требует прямого поручения на данные.

### `core/management/commands/initialize_local_test.py`

Только синтетические пользователь/склад, без копирования рабочей базы.

### `core/management/commands/seed_demo_data.py`

Заполнение локальной базы демонстрационными данными GameBAT CRM.

### `integrations/management/commands/configure_worker_monitoring.py`

Явная политика штатного запуска, не изменяющая настройки бизнес-интеграций.

### `integrations/management/commands/import_avito_credentials.py`

Перенос секретных реквизитов Avito в защищённое хранилище; значения не выводить и не коммитить.

### `integrations/management/commands/run_integration_worker.py`

Фоновый исполнитель очередей Avito/Яндекс/Sheets; даже --once может менять реальные внешние данные.

### `integrations/management/commands/run_worker_supervisor.py`

Единственный локальный владелец восстановления; может возобновлять реальные очереди.

### `integrations/management/commands/verify_avito_sync.py`

Сверка с реальным Avito; без --fix остаётся сетевой операцией, с --fix может менять объявления.

### `price/management/commands/backfill_procurement_tech_surcharges.py`

Контролируемое заполнение исторических доплат; сначала dry-run и согласованная копия БД.

### `sales/management/commands/register_print_agent.py`

Регистрация администратором: stdin содержит только публичный хеш, не токен.

### `sales/management/commands/run_label_print_worker.py`

Windows-исполнитель печати ярлыков. Подтверждённая печать отделена от постановки задания/готовности FBS.

### `supplies/management/commands/recalculate_warehouse_costs.py`

Одноразовый безопасный пересчёт истории приходов по физическому складу.

### `yandex_market/management/commands/configure_yandex_market.py`

Первичная настройка отключённого подключения; только чтение внешнего API.
