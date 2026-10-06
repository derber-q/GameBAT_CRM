"""Запускать с browser_test_settings: два подключения к отдельной файловой SQLite."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from cryptography.fernet import Fernet
from django.db import close_old_connections
from django.test import Client, TransactionTestCase, override_settings
from django.urls import reverse
from catalog.models import CD, Platform
from warehouse.models import CDWarehouseStock, Warehouse
from sales.models import Sale
from cash.models import CashTransaction
from .models import RetailSettings, StorefrontSettings, WholesaleContact
from .retail_security import retail_link
from .security import issue_link, recover_token


@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class RetailConcurrencyTests(TransactionTestCase):
    def test_last_unit_between_retail_and_wholesale(self):
        warehouse = Warehouse.objects.create(name="Конкурентный склад")
        RetailSettings.objects.update_or_create(pk=1,defaults={"warehouse":warehouse})
        StorefrontSettings.objects.update_or_create(pk=1,defaults={"warehouse":warehouse})
        product=CD.objects.create(name="Последняя единица",platform=Platform.objects.create(name="Тест"),avito_price=5000,wholesale_price=4000,cost=3000)
        stock=CDWarehouseStock.objects.create(warehouse=warehouse,cd=product,quantity=1)
        token=recover_token(retail_link())
        contact=WholesaleContact.objects.create(name="Оптовик",phone="+79990000000")
        _,wholesale_token=issue_link(contact,None)
        clients=[]
        for namespace,access_token in (("retailer",token),("resource_storefront",wholesale_token)):
            client=Client()
            client.get(reverse(namespace+":access",args=[access_token]))
            client.post(reverse(namespace+":cart_add"),{"kind":"cd","product_id":product.pk,"quantity":1})
            version=client.get(reverse(namespace+":cart")).context["version"]
            clients.append((client,namespace,version))
        barrier=Barrier(2)
        def buy(item):
            close_old_connections()
            client,namespace,version=item
            try:
                barrier.wait(timeout=10)
                response=client.post(reverse(namespace+":checkout"),{"cart_version":version,"name":"Розничный покупатель","phone":"+79991234567"},HTTP_X_REQUESTED_WITH="XMLHttpRequest")
                return response.status_code
            finally:
                close_old_connections()
        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses=list(pool.map(buy,clients))
        self.assertEqual(sorted(statuses),[200,409])
        stock.refresh_from_db()
        self.assertEqual(stock.quantity,0)
        self.assertEqual(Sale.objects.count(),1)
        self.assertFalse(CashTransaction.objects.exists())
