import csv
import io
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase
from django.urls import reverse

from .game_series_classifier import classify_game_title
from .models import CD, GameSeries, Platform, ProductChangeEvent
from .nomenclature_forms import CDCreateForm
from .nomenclature_forms import product_version


class GameSeriesTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ps4 = Platform.objects.create(name="PlayStation 4")
        cls.ps5 = Platform.objects.create(name="PlayStation 5")
        cls.series = GameSeries.objects.create(name=" Assassin’s   Creed ")
        cls.ps4_cd = CD.objects.create(platform=cls.ps4, name="Assassin's Creed Odyssey")
        cls.ps5_cd = CD.objects.create(platform=cls.ps5, name="Assassin's Creed Mirage")
        CD.objects.filter(pk__in=(cls.ps4_cd.pk, cls.ps5_cd.pk)).update(game_series=cls.series)

    def test_normalized_unique_name_and_rename(self):
        self.assertEqual(self.series.name, "Assassin's Creed")
        with self.assertRaises(ValidationError):
            GameSeries.objects.create(name="  ASSASSIN'S CREED  ")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                GameSeries.objects.bulk_create([GameSeries(name="ASSASSIN'S CREED", normalized_name="assassin's creed")])
        self.series.name = "  Resident   Evil "
        self.series.save(update_fields=["name"])
        self.series.refresh_from_db()
        self.assertEqual(self.series.normalized_name, "resident evil")
        self.assertEqual(self.ps4_cd.game_series_id, self.ps5_cd.game_series_id)

    def test_delete_used_series_is_protected(self):
        with self.assertRaises(ProtectedError):
            self.series.delete()

    def test_null_series_and_form_selection(self):
        CD.objects.create(platform=self.ps5, name="Новая игра без серии")
        form = CDCreateForm()
        self.assertFalse(form.fields["game_series"].required)
        self.assertIn(self.series, form.fields["game_series"].queryset)

    def test_platform_then_series_grouping_and_search(self):
        user = get_user_model().objects.create_superuser("series-admin", "admin@example.com", "password")
        self.client.force_login(user)
        response = self.client.get(reverse("nomenclature:list"))
        groups = response.context["cd_groups"]
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0][1]["series_groups"][0][0], self.series)
        self.assertEqual(groups[1][1]["series_groups"][0][0], self.series)
        self.assertContains(response, 'class="nomenclature-series collapsible-section"', count=2)

        response = self.client.get(reverse("nomenclature:list"), {"search": "Mirage"})
        groups = response.context["cd_groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0][0], self.ps5)
        self.assertEqual(len(groups[0][1]["series_groups"]), 1)

    def test_null_group_only_when_product_exists(self):
        user = get_user_model().objects.create_superuser("null-admin", "null@example.com", "password")
        self.client.force_login(user)
        response = self.client.get(reverse("nomenclature:list"))
        self.assertFalse(any(
            series is None
            for _, group in response.context["cd_groups"]
            for series, _ in group["series_groups"]
        ))
        CD.objects.create(platform=self.ps5, name="Новая игра без серии")
        response = self.client.get(reverse("nomenclature:list"))
        self.assertTrue(any(
            series is None
            for _, group in response.context["cd_groups"]
            for series, _ in group["series_groups"]
        ))

    def test_series_edit_permission_and_audit(self):
        user = get_user_model().objects.create_user("series-editor", password="password")
        user.user_permissions.add(Permission.objects.get(codename="view_nomenclature"))
        self.client.force_login(user)
        url = reverse("nomenclature:cd_detail", args=(self.ps5_cd.pk,))
        other = GameSeries.objects.create(name="Resident Evil")
        response = self.client.post(url, {
            "version": product_version(self.ps5_cd), "game_series": str(other.pk),
        })
        self.assertEqual(response.status_code, 200)
        self.ps5_cd.refresh_from_db()
        self.assertEqual(self.ps5_cd.game_series_id, self.series.pk)
        self.assertFalse(ProductChangeEvent.objects.exists())

        user.user_permissions.add(Permission.objects.get(codename="change_cd_game_series"))
        user = get_user_model().objects.get(pk=user.pk)
        self.client.force_login(user)
        response = self.client.post(url, {
            "version": product_version(self.ps5_cd), "game_series": str(other.pk),
        })
        self.assertEqual(response.status_code, 302)
        self.ps5_cd.refresh_from_db()
        self.assertEqual(self.ps5_cd.game_series_id, other.pk)
        change = ProductChangeEvent.objects.get().field_changes.get(field_name="game_series")
        self.assertEqual((change.old_value, change.new_value), (self.series.name, other.name))


class GameSeriesClassifierTests(TestCase):
    def test_known_series_editions_numbered_remaster_and_standalone(self):
        cases = {
            "PS5 Cyberpunk 2077 Ultimate Edition": "Cyberpunk 2077",
            "PS5 The Last of Us Part II Remastered": "The Last of Us",
            "PS4 Resident Evil 4 Remake": "Resident Evil",
            "NS2 Assassin’s Creed Shadows": "Assassin's Creed",
            "PS5 Hogwarts Legacy Deluxe Edition": "Hogwarts Legacy",
            "PS5 A Unique New Game Deluxe Edition": "A Unique New Game",
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(classify_game_title(title)[0], expected)

    def test_command_dry_run_apply_idempotence_and_preserve_manual(self):
        platform = Platform.objects.create(name="PlayStation 5")
        first = CD.objects.create(platform=platform, name="Cyberpunk 2077")
        second = CD.objects.create(platform=platform, name="Cyberpunk 2077 Ultimate Edition")
        manual = GameSeries.objects.create(name="Ручная классификация")
        CD.objects.filter(pk=second.pk).update(game_series=manual)
        with TemporaryDirectory() as temp_dir:
            output = io.StringIO()
            call_command("classify_game_series", "--dry-run", "--report-dir", temp_dir, stdout=output)
            self.assertFalse(CD.objects.get(pk=first.pk).game_series_id)
            self.assertEqual(GameSeries.objects.count(), 1)
            self.assertIn('"cd_without_series": 1', output.getvalue())

            output = io.StringIO()
            call_command("classify_game_series", "--apply", "--report-dir", temp_dir, stdout=output)
            self.assertIn('"cd_without_series": 0', output.getvalue())
            self.assertEqual(GameSeries.objects.count(), 2)
            self.assertEqual(CD.objects.get(pk=second.pk).game_series_id, manual.pk)
            self.assertEqual(CD.objects.get(pk=first.pk).game_series.name, "Cyberpunk 2077")

            with next(Path(temp_dir).glob("*applied*.csv")).open(encoding="utf-8-sig", newline="") as report:
                self.assertEqual(len(list(csv.DictReader(report))), 2)

            call_command("classify_game_series", "--apply", "--report-dir", temp_dir, stdout=io.StringIO())
            self.assertEqual(GameSeries.objects.count(), 2)
            self.assertEqual(CD.objects.get(pk=second.pk).game_series_id, manual.pk)
