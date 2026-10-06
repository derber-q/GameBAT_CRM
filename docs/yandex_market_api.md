# Официальные контракты Яндекс Маркета

Срез от 24.09.2026, официальный репозиторий https://github.com/yandex-market/yandex-market-partner-api, commit `321c272cfe218c21fd1644242cef205b6c9b8dbe`.

`yandex_market/contracts.json` содержит разрешённые операции, схемы, параметры, scopes и лимиты. `OPENAPI-LICENSE.txt` сохраняет BSD-лицензию источника. Это фиксированный проверенный срез; для обновления сверять изменения спецификации и регрессионные тесты.

Для полного сценария нужен `all-methods` либо совокупность `offers-and-cards-management`, `pricing`, `inventory-and-order-processing` и прав чтения настроек/магазинов. Read-only scopes достаточны для соответствующих чтений, но не для изменения цены, остатка, коробок и статуса. Проверка соединения не доказывает все права записи.

| Операция | Метод / путь | Лимит базового тарифа | Единица |
| --- | --- | --- | --- |
| `getBusinessSettings` | `POST /v2/businesses/{businessId}/settings` | 100 / 1 hours | `resp` |
| `getCampaigns` | `GET /v2/campaigns` | 1000 / 1 hours | `resp` |
| `getBusinessOrders` | `POST /v1/businesses/{businessId}/orders` | 10000 / 1 hours | `resp` |
| `updateOrderStatus` | `PUT /v2/campaigns/{campaignId}/orders/{orderId}/status` | 10000 / 1 hours | `resp` |
| `setOrderBoxLayout` | `PUT /v2/campaigns/{campaignId}/orders/{orderId}/boxes` | 10000 / 1 hours | `resp` |
| `generateOrderLabel` | `GET /v2/campaigns/{campaignId}/orders/{orderId}/delivery/shipments/{shipmentId}/boxes/{boxId}/label` | 10000 / 1 hours | `resp` |
| `generateOrderLabels` | `GET /v2/campaigns/{campaignId}/orders/{orderId}/delivery/labels` | 10000 / 1 hours | `resp` |
| `getOrderLabelsData` | `GET /v2/campaigns/{campaignId}/orders/{orderId}/delivery/labels/data` | 10000 / 1 hours | `resp` |
| `getReturns` | `GET /v2/campaigns/{campaignId}/returns` | 5000 / 1 hours | `resp` |
| `getReturn` | `GET /v2/campaigns/{campaignId}/orders/{orderId}/returns/{returnId}` | 7000 / 1 hours | `resp` |
| `getOfferMappings` | `POST /v2/businesses/{businessId}/offer-mappings` | 100 / 1 minutes | `resp` |
| `updateOfferMappings` | `POST /v2/businesses/{businessId}/offer-mappings/update` | 5000 / 1 minutes | `req.offerMappings` |
| `updateBusinessPrices` | `POST /v2/businesses/{businessId}/offer-prices/updates` | 10000 / 1 minutes | `req.offers` |
| `updatePrices` | `POST /v2/campaigns/{campaignId}/offer-prices/updates` | 10000 / 1 minutes | `req.offers` |
| `getPricesByOfferIds` | `POST /v2/campaigns/{campaignId}/offer-prices` | 10000 / 1 minutes | `resp.result.offers` |
| `getDefaultPrices` | `POST /v2/businesses/{businessId}/offer-prices` | 5000 / 1 minutes | `resp.result.offers` |
| `updateStocks` | `PUT /v2/campaigns/{campaignId}/offers/stocks` | 100000 / 1 minutes | `req.skus` |
| `getStocks` | `POST /v2/campaigns/{campaignId}/offers/stocks` | 100000 / 1 minutes | `resp.result.warehouses.offers.offerId` |
| `updateStocksOnPartnerWarehouses` | `POST /v3/businesses/{businessId}/offers/stocks/update` | 50 / 1 minutes | `resp` |
| `getStocksOnPartnerWarehouses` | `POST /v3/businesses/{businessId}/offers/stocks` | 500 / 1 minutes | `resp` |
| `getReportInfo` | `GET /v2/reports/info/{reportId}` | 100 / 1 minutes | `resp` |
| `generateMassOrderLabelsReport` | `POST /v2/reports/documents/labels/generate` | 1000 / 1 hours | `resp` |
| `getPagedWarehouses` | `POST /v2/businesses/{businessId}/warehouses` | 100 / 1 hours | `resp` |
| `getPartnerWarehouses` | `POST /v3/businesses/{businessId}/warehouses` | 100 / 1 hours | `resp` |
| `getCategoryContentParameters` | `POST /v2/category/{categoryId}/parameters` | 100 / 1 minutes | `resp` |
| `getOfferCardsContentStatus` | `POST /v2/businesses/{businessId}/offer-cards` | 100 / 1 minutes | `resp` |
| `getCategoriesTree` | `POST /v2/categories/tree` | 50 / 1 hours | `resp` |

## Устаревшие поля и методы

Не используются `getOrder`/`getOrders`: вместо них `getBusinessOrders`. Не используются `params`, `category`, `firstVideoAsCover`, `customsCommodityCode`, `available` и `OrderLabelDTO.url`. Параметр `onlyPartnerMediaContent=true` не отправляется. Цена, себестоимость и расходы не подмешиваются в запрос редактирования контента.

Суммы строк `ItemPriceDTO.payment/cashback/subsidy` относятся ко всем единицам строки. Количество к продаже сравнивается с AVAILABLE, не с FIT, включающим FREEZE.

В локальном срезе `BaseCampaignOfferDTO.available` помечен deprecated с отключением 19.10.2026. Создание карточки выполняется через updateOfferMappings; наличие статуса NO_CARD_ADD_TO_CAMPAIGN показывается как требование действий в кабинете, а не скрывается ложным успехом публикации.
