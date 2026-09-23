from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PriceMarkupMigrationTests(TransactionTestCase):
    def test_existing_cd_and_tech_get_defaults_without_price_changes(self):
        previous=[('catalog','0015_multiple_product_barcodes')]
        executor=MigrationExecutor(connection)
        executor.migrate(previous)
        apps=executor.loader.project_state(previous).apps
        platform=apps.get_model('catalog','Platform').objects.create(name='Markup migration platform')
        brand=apps.get_model('catalog','Brand').objects.create(name='Markup migration brand')
        product_type=apps.get_model('catalog','ProductType').objects.create(name='Markup migration type')
        prices=dict(avito_price=Decimal('99.25'),wholesale_price=Decimal('50.50'),yandex_market_price=None,cost=Decimal('75.15'))
        cd=apps.get_model('catalog','CD').objects.create(name='Old disc',platform=platform,**prices)
        tech=apps.get_model('catalog','Tech').objects.create(name='Old tech',brand=brand,product_type=product_type,**prices)
        target=[('catalog','0017_initialize_price_markups')]
        executor=MigrationExecutor(connection)
        executor.migrate(target)
        apps=executor.loader.project_state(target).apps
        for name,pk in [('CD',cd.pk),('Tech',tech.pk)]:
            product=apps.get_model('catalog',name).objects.get(pk=pk)
            self.assertEqual(product.avito_markup_from_wholesale,Decimal('200.00'))
            self.assertEqual(product.yandex_markup_from_wholesale,Decimal('200.00'))
            for field,value in prices.items():self.assertEqual(getattr(product,field),value)
        for name in ('CD', 'Tech'):
            apps.get_model('catalog', name).objects.all().update(
                avito_markup_from_wholesale=None, yandex_markup_from_wholesale=Decimal('350.00'))
        target = [('catalog', '0018_price_markups_189')]
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        apps = executor.loader.project_state(target).apps
        for name, pk in [('CD', cd.pk), ('Tech', tech.pk)]:
            product = apps.get_model('catalog', name).objects.get(pk=pk)
            self.assertEqual(product.avito_markup_from_wholesale, Decimal('189.00'))
            self.assertEqual(product.yandex_markup_from_wholesale, Decimal('189.00'))
            for field, value in prices.items():
                self.assertEqual(getattr(product, field), value)

    def tearDown(self):
        executor=MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()
