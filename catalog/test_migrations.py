from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class ProductDataMigrationTests(TransactionTestCase):
    migrate_from = [("catalog", "0007_alter_cd_barcode_alter_tech_barcode")]
    migrate_to = [("catalog", "0010_rename_retail_price_to_avito_price")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Platform = old_apps.get_model("catalog", "Platform")
        CD = old_apps.get_model("catalog", "CD")
        platform = Platform.objects.create(name="Migration PS5")
        self.product_id = CD.objects.create(
            platform=platform,
            name="Migration product",
            sku="MIGRATION-CD",
            barcode="012345678901",
            retail_price=Decimal("12345.67"),
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_weight_barcode_and_price_are_migrated_without_loss(self):
        CD = self.apps.get_model("catalog", "CD")
        Registry = self.apps.get_model("catalog", "BarcodeRegistry")
        product = CD.objects.get(pk=self.product_id)
        self.assertEqual(product.weight_grams, 140)
        self.assertEqual(product.avito_price, Decimal("12345.67"))
        self.assertFalse(hasattr(product, "retail_price"))
        self.assertTrue(Registry.objects.filter(
            value="012345678901", product_kind="cd", cd_id=product.pk,
        ).exists())


class CDDefaultWeightMigrationTests(TransactionTestCase):
    migrate_from = [("catalog", "0010_rename_retail_price_to_avito_price")]
    migrate_to = [("catalog", "0011_cd_default_weight_120")]

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        Platform = old_apps.get_model("catalog", "Platform")
        CD = old_apps.get_model("catalog", "CD")
        platform = Platform.objects.create(name="Migration weight platform")
        self.old_default_id = CD.objects.create(
            platform=platform, name="Old default weight", sku="MIGRATION-WEIGHT-140",
            weight_grams=140,
        ).pk
        self.custom_weight_id = CD.objects.create(
            platform=platform, name="Custom weight", sku="MIGRATION-WEIGHT-125",
            weight_grams=125,
        ).pk

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        self.apps = executor.loader.project_state(self.migrate_to).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_only_old_default_weight_is_changed(self):
        CD = self.apps.get_model("catalog", "CD")
        self.assertEqual(CD.objects.get(pk=self.old_default_id).weight_grams, 120)
        self.assertEqual(CD.objects.get(pk=self.custom_weight_id).weight_grams, 125)
        self.assertEqual(CD._meta.get_field("weight_grams").default, 120)
