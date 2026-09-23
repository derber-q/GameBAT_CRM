from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from accounts.models import User
from catalog.models import Tech, Brand, ProductType
from partners.models import SalesPlatform
from warehouse.models import Warehouse, TechWarehouseStock
from .models import TechConsignmentStock
from .opening_balances import add_opening_balances
from .services import record_consignment_sale, return_from_consignment, transfer_to_consignment


class OpeningBalancesTests(TestCase):
    def test_separate_rewards_no_warehouse_deduction_and_independent_actions(self):
        actor = User.objects.create_superuser('opening-admin')
        warehouse = Warehouse.objects.create(name='Opening warehouse')
        platform = SalesPlatform.objects.create(name='Partner')
        product = Tech.objects.create(name='Headset', brand=Brand.objects.create(name='Sony'),
                                      product_type=ProductType.objects.create(name='Headphones'), cost=70)
        physical = TechWarehouseStock.objects.create(warehouse=warehouse, tech=product, quantity=10)
        rows = [dict(kind='tech', product_id=product.pk, platform_id=platform.pk, quantity=1, reward=reward, source_row=i)
                for i, reward in [(2, '13000'), (3, '11000')]]
        lots = add_opening_balances(actor=actor, warehouse_id=warehouse.pk, source_key='test-opening', rows=rows)
        physical.refresh_from_db(); product.refresh_from_db()
        self.assertEqual(physical.quantity, 10)
        self.assertEqual(product.quantity_on_consignment, 2)
        self.assertEqual(product.cost, 70)
        self.assertEqual(TechConsignmentStock.objects.count(), 2)
        self.client.force_login(actor)
        response = self.client.get(reverse('consignment:list'))
        for lot in lots:
            self.assertContains(response, f'data-consignment-row="tech-{lot.pk}"')
        with self.assertRaises(ValidationError):
            add_opening_balances(actor=actor, warehouse_id=warehouse.pk, source_key='test-opening', rows=rows)
        product.refresh_from_db(); self.assertEqual(product.quantity_on_consignment, 2)
        regular = transfer_to_consignment(actor=actor, warehouse_id=warehouse.pk, platform_id=platform.pk,
            product_type='tech', product_id=product.pk, quantity=2, receivable_per_unit='12000')
        self.assertEqual(regular.lot_key, '')
        self.assertEqual(regular.quantity, 2)
        sale = record_consignment_sale(actor=actor, product_type='tech', stock_id=lots[0].pk, quantity=1, payment_method='bank_account')
        self.assertEqual(sale.total_amount, 13000)
        return_from_consignment(actor=actor, warehouse_id=warehouse.pk, platform_id=platform.pk,
            product_type='tech', product_id=product.pk, stock_id=lots[1].pk, quantity=1)
        lots[0].refresh_from_db(); lots[1].refresh_from_db(); regular.refresh_from_db()
        self.assertEqual((lots[0].quantity, lots[1].quantity, regular.quantity), (0, 0, 2))
        physical.refresh_from_db(); self.assertEqual(physical.quantity, 9)
