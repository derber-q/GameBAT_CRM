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


class MultipleBarcodeMigrationTests(TransactionTestCase):
    migrate_from = [("catalog", "0014_cd_archived_at_cd_archived_by_cd_is_archived_and_more")]
    migrate_to = [("catalog", "0015_multiple_product_barcodes")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def _old_models(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        apps = executor.loader.project_state(self.migrate_from).apps
        return (
            apps.get_model("catalog", "Platform"),
            apps.get_model("catalog", "Brand"),
            apps.get_model("catalog", "ProductType"),
            apps.get_model("catalog", "CD"),
            apps.get_model("catalog", "Tech"),
            apps.get_model("catalog", "BarcodeRegistry"),
        )

    def test_legacy_values_are_preserved_for_both_product_types(self):
        Platform, Brand, ProductType, CD, Tech, Registry = self._old_models()
        cd = CD.objects.create(platform=Platform.objects.create(name="Migration PS5"),
                               name="CD", barcode="0012345")
        tech = Tech.objects.create(brand=Brand.objects.create(name="Migration Sony"),
                                   product_type=ProductType.objects.create(name="Migration Console"),
                                   name="Tech", barcode="0098765")
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        new_cd = apps.get_model("catalog", "CD")
        new_registry = apps.get_model("catalog", "BarcodeRegistry")
        self.assertFalse(any(field.name == "barcode" for field in new_cd._meta.fields))
        self.assertEqual(set(new_registry.objects.values_list("value", flat=True)), {"0012345", "0098765"})
        self.assertEqual(new_registry.objects.get(value="0012345").cd_id, cd.pk)
        self.assertEqual(new_registry.objects.get(value="0098765").tech_id, tech.pk)

    def test_cross_model_legacy_conflict_stops_migration_without_loss(self):
        Platform, Brand, ProductType, CD, Tech, Registry = self._old_models()
        CD.objects.create(platform=Platform.objects.create(name="Conflict PS5"),
                          name="CD", barcode="0012345")
        Tech.objects.create(brand=Brand.objects.create(name="Conflict Sony"),
                            product_type=ProductType.objects.create(name="Conflict Console"),
                            name="Tech", barcode="0012345")
        with self.assertRaisesRegex(RuntimeError, "Конфликты старых штрихкодов"):
            MigrationExecutor(connection).migrate(self.migrate_to)
        self.assertEqual(Registry.objects.count(), 0)
        self.assertEqual(CD.objects.get().barcode, "0012345")
        self.assertEqual(Tech.objects.get().barcode, "0012345")
        # Clear test-only conflicting legacy value to let teardown restore the leaf state.
        Tech.objects.update(barcode="")
