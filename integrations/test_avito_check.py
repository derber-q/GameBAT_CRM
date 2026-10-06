from decimal import Decimal
from datetime import timedelta
from threading import Lock
from time import sleep
from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from catalog.models import Brand, CD, GameSeries, Platform, ProductType, Tech
from warehouse.models import CDWarehouseStock, TechWarehouseStock, Warehouse
from .avito_check import CHECK_VERSION, _check_signature, physical_game, _validated_offer, _city, _search_query, new_condition, product_matches, queue, run_check, search_offers, suspicious_price
from .models import AvitoCheckListingCache, AvitoListingConnection, AvitoPriceCheckResult, AvitoProductProfile, AvitoRemoteListing, ReefApiCredential
from .reef_api import ReefApiError
from .reef_api import ReefApiClient
from .reef_settings import save_key


class FakeClient:
    def __init__(self, pages, listings):
        self.pages = pages
        self.listings = listings
        self.calls = []
        self.queries = []

    def search(self, query, page, *, price_max=None):
        self.calls.append(("search", page, price_max))
        self.queries.append(query)
        rows = self.pages[page - 1]
        if price_max is not None:
            rows = [row for row in rows if Decimal(str(row.get("price", 0))) <= price_max]
        return {"listings": rows, "has_more": page < len(self.pages)}

    def listing(self, ad_id):
        self.calls.append(("listing", ad_id))
        value = self.listings[ad_id]
        if isinstance(value, Exception):
            raise value
        return {"listing": value}


class PagedPriceClient(FakeClient):
    def __init__(self, rows, listings, *, page_size=4):
        super().__init__([], listings)
        self.rows = rows
        self.page_size = page_size

    def search(self, query, page, *, price_max=None):
        self.calls.append(("search", page, price_max))
        self.queries.append(query)
        rows = [row for row in self.rows if price_max is None or Decimal(str(row["price"])) <= price_max]
        start = (page - 1) * self.page_size
        return {"listings": rows[start:start + self.page_size], "has_more": start + self.page_size < len(rows)}


def brief(ad_id, price, title="PS5 Slim Disc", **extra):
    return {"ad_id": str(ad_id), "price": price, "title": title,
            "url": f"https://www.avito.ru/moskva/igry_{ad_id}",
            "category": {"name": "Игровые приставки"}, **extra}


def full(ad_id, price, title="PS5 Slim Disc", condition="Новое", description="Продаю консоль"):
    return {**brief(ad_id, price, title), "status": "active", "description": description,
            "params": [{"name": "Состояние", "value": condition}, {"name": "Формат", "value": "Физический"}],
            "seller": {"name": "Магазин"}, "images": []}


@override_settings(INTEGRATION_ENCRYPTION_KEY=Fernet.generate_key().decode())
class AvitoCheckTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username="check-admin", password="test-password")
        self.client.force_login(self.user)
        self.warehouse = Warehouse.objects.create(name="Avito Check тест")
        self.platform = Platform.objects.create(name="PS5")
        self.cd = CD.objects.create(name="PS5 Slim Disc", platform=self.platform, cost=4000,
                                    wholesale_price=Decimal("4500"), avito_price=Decimal("5000"))
        self.stock = CDWarehouseStock.objects.create(cd=self.cd, warehouse=self.warehouse, quantity=2)
        self.profile = AvitoProductProfile.objects.create(cd=self.cd)
        own = AvitoRemoteListing.objects.create(avito_item_id=999)
        AvitoListingConnection.objects.create(profile=self.profile, remote_listing=own)

    def test_queue_uses_links_active_and_global_stock_for_cd_and_tech(self):
        brand = Brand.objects.create(name="Sony")
        kind = ProductType.objects.create(name="Консоль")
        tech = Tech.objects.create(name="PS5 Slim Disc", brand=brand, product_type=kind)
        TechWarehouseStock.objects.create(tech=tech, warehouse=self.warehouse, quantity=1)
        tech_profile = AvitoProductProfile.objects.create(tech=tech)
        AvitoListingConnection.objects.create(profile=tech_profile, remote_listing=AvitoRemoteListing.objects.create(avito_item_id=998))
        self.assertEqual([(kind, product.pk) for kind, product in queue()], [("cd", self.cd.pk), ("tech", tech.pk)])
        self.stock.quantity = 0; self.stock.save()
        self.assertEqual([kind for kind, _ in queue()], ["tech"])
        tech.is_archived = True; tech.save()
        self.assertEqual(queue(), [])

    def test_matcher_and_price_rules(self):
        for title in ("PS5 Slim Digital", "PS5 Slim Disc аккаунт", "PS5 Slim Disc ключ активации",
                      "PS5 Slim Disc подписка", "PS5 Slim Disc услуга"):
            self.assertFalse(product_matches(self.cd, "cd", full(2, 4000, title)), title)
        self.assertTrue(product_matches(self.cd, "cd", full(2, 4000, "PlayStation 5 Slim Disc")))
        self.assertTrue(new_condition(full(2, 4000)))
        self.assertFalse(new_condition(full(2, 4000, condition="Б/у")))
        self.assertFalse(new_condition({"params": []}))
        self.assertTrue(suspicious_price(full(2, 1), 5000, "Цена указана условно, реальная стоимость 5000 ₽"))
        self.assertTrue(suspicious_price(full(2, 500), 5000, "Реальная стоимость 5000 ₽"))
        self.assertFalse(suspicious_price(full(2, 500), 5000, "Продаю за 500 ₽"))
        other = CD(name="God of War", platform=self.platform)
        self.assertFalse(product_matches(other, "cd", full(3, 500, "God of War PS4")))
        self.assertTrue(product_matches(other, "cd", full(3, 500, "God of War PS5")))
        tech = Tech(name="iPhone 256GB", brand=Brand(name="Apple"), product_type=ProductType(name="Телефон"))
        self.assertFalse(product_matches(tech, "tech", full(4, 5000, "Apple iPhone 512 GB")))

    def test_ns2_alias_and_generic_platform_param_do_not_hide_cheaper_game(self):
        self.platform.name = "Nintendo Switch 2"
        self.platform.save()
        self.cd.name = "NS2 Animal Crossing"
        self.cd.save()
        self.profile.listing_title = "Animal Crossing: New Horizons Nintendo Switch2"
        self.profile.save()
        title = "Animal Crossing: New Horizons — Nintendo Switch 2"
        cheaper = full(8186778987, 4450, title)
        cheaper["location"] = {"name": "Санкт-Петербург"}
        cheaper["params"].append({"name": "Платформа", "value": "Nintendo Switch"})
        self.assertTrue(product_matches(self.cd, "cd", cheaper))
        self.assertFalse(product_matches(self.cd, "cd", full(12, 3900, "Animal Crossing New Horizons Nintendo Switch")))
        self.assertFalse(product_matches(self.cd, "cd", full(13, 4339, "Animal Crossing New Horizons Game-Key Switch 2")))
        fake = FakeClient(
            [[brief(11, 4800, "Animal Crossing New Horizons NS2")], [brief(8186778987, 4450, title)]],
            {"11": full(11, 4800, "Animal Crossing New Horizons NS2"), "8186778987": cheaper},
        )
        result = search_offers(self.cd, "cd", client=fake)
        self.assertEqual([offer["ad_id"] for offer in result], ["8186778987", "11"])
        self.assertEqual(result[0]["city"], "Санкт-Петербург")
        self.assertEqual(fake.calls[0], ("search", 1, None))
        self.assertEqual(fake.queries[0], "animal crossing new horizons Nintendo Switch 2")

    def test_product_image_uses_protected_media_view_and_results_show_city(self):
        self.cd.title_image = "catalog/cd/1/title/example.jpg"
        self.cd.save(update_fields=["title_image"])
        AvitoPriceCheckResult.objects.create(profile=self.profile, checked_at=timezone.now(), metadata={"version": CHECK_VERSION, "signature": _check_signature(self.cd, "cd")}, offers=[{
            "ad_id": "123", "title": "PS5 Slim Disc", "price": "4000",
            "city": "Казань", "url": "https://www.avito.ru/kazan/igry_123", "image": "", "seller": "",
        }])
        response = self.client.get(reverse("pricing:avito_check_automatic"))
        image_url = reverse("nomenclature:product_title_image", args=("cd", self.cd.pk))
        self.assertContains(response, f'src="{image_url}"')
        self.assertNotContains(response, "/protected-media/")
        self.assertContains(response, "<th>Город</th>", html=True)
        self.assertContains(response, "<td>Казань</td>", html=True)
        self.assertEqual(_city({"location": {"address": "Центр"}}, {"location": {"name": "Тверь"}}), "Тверь")

    def test_game_prefix_punctuation_mixed_letters_and_catalog_metadata(self):
        self.platform.name = "PlayStation 4"
        self.platform.save()
        self.cd.name = "PS4 Assassins Сreed: Odyssey CUSA 18535 (rus lang)"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "assassins creed odyssey PlayStation 4")
        self.assertTrue(product_matches(self.cd, "cd", full(10, 3000, "Assassin's Creed Odyssey PlayStation 4")))
        self.assertFalse(product_matches(self.cd, "cd", full(11, 3000, "Assassin's Creed Origins PlayStation 4")))
        self.assertFalse(product_matches(self.cd, "cd", full(12, 3000, "Assassin's Creed Odyssey PlayStation 5")))
        self.cd.name = "PS4 A Plague Tale Innocence"
        self.cd.save()
        self.assertTrue(product_matches(self.cd, "cd", full(13, 3000, "A Plague Tale: Innocence PS4")))
        self.cd.name = "PS4 Crash Bandicoot N.Sane Trilogy 11870 (eng lang)"
        self.cd.cusa_ppsa_code = "11870"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "crash bandicoot n sane trilogy PlayStation 4")
        self.cd.name = "PS4 LEGO Marvel Super Heroes CUSA 00044/08476 (rus sub)"
        self.cd.cusa_ppsa_code = ""
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "lego marvel super heroes PlayStation 4")
        self.cd.name = "PS4 Little Nightmares I+II CUSA 12779;05952 (rus sub)"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "little nightmares 1 2 PlayStation 4")
        self.assertTrue(product_matches(self.cd, "cd", full(14, 3000, "Little Nightmares 1 + 2 PS4")))

    def test_game_roman_numbers_editions_and_switch_generation(self):
        self.platform.name = "Nintendo Switch 2"
        self.platform.save()
        self.cd.name = "NS2 Civilization VII"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "civilization 7 Nintendo Switch 2")
        self.assertTrue(product_matches(self.cd, "cd", full(20, 3000, "Civilization 7 Nintendo Switch 2")))
        self.assertFalse(product_matches(self.cd, "cd", full(21, 3000, "Civilization VI Nintendo Switch 2")))
        self.assertFalse(product_matches(self.cd, "cd", full(22, 3000, "Civilization VII Nintendo Switch")))
        self.cd.name = "NS2 Resident Evil 7 Biohazard Gold Edition"
        self.cd.save()
        self.assertTrue(product_matches(self.cd, "cd", full(23, 3000, "Resident Evil 7 Biohazard Gold Edition Switch 2")))
        self.assertFalse(product_matches(self.cd, "cd", full(24, 3000, "Resident Evil 7 Biohazard Switch 2")))
        self.cd.name = "NS2 Elden Ring Tarnished Edition"
        self.cd.save()
        self.assertTrue(product_matches(self.cd, "cd", full(25, 3000, "Elden Ring Tranished Edition Switch 2")))
        self.cd.name = "NS2 SnowRunner"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "snowrunner Nintendo Switch 2")
        self.assertTrue(product_matches(self.cd, "cd", full(26, 3000, "Snow Runner Nintendo Switch 2")))
        self.cd.name = "NS2 Resident Evi 8 Village Gold Edition"
        self.cd.game_series = GameSeries.objects.create(name="Resident Evil")
        self.cd.save()
        self.profile.listing_title = "Resident Evil 8 Village Gold Edition NS2"
        self.profile.save()
        self.assertEqual(_search_query(self.cd, "cd"), "resident evil 8 village gold edition Nintendo Switch 2")
        self.assertTrue(product_matches(self.cd, "cd", full(27, 3000, "Resident Evil 8 Village Gold Edition Switch 2")))

    def test_incorrect_avito_profile_platform_does_not_poison_game_search(self):
        self.platform.name = "Nintendo Switch"
        self.platform.save()
        self.cd.name = "NS Gang Beasts"
        self.cd.save()
        self.profile.listing_title = "Gang Beatst PS4 (новый диск)"
        self.profile.save()
        self.assertEqual(_search_query(self.cd, "cd"), "gang beasts Nintendo Switch")
        self.assertTrue(product_matches(self.cd, "cd", full(30, 3000, "Gang Beasts Nintendo Switch")))
        self.cd.name = "NS FC 27"
        self.cd.save()
        self.profile.listing_title = "EA FC 27 (FIFA 27) Nintendo Switch"
        self.profile.save()
        self.assertEqual(_search_query(self.cd, "cd"), "fc 27 Nintendo Switch")
        self.platform.name = "PlayStation 4"
        self.platform.save()
        self.cd.name = "PS4 Crysis Remastered"
        self.cd.save()
        self.profile.listing_title = "Crysis Remastered Trilogy PS4"
        self.profile.save()
        self.assertEqual(_search_query(self.cd, "cd"), "crysis remastered PlayStation 4")
        self.assertFalse(product_matches(self.cd, "cd", full(31, 3000, "Crysis Remastered Trilogy PS4")))
        self.platform.name = "PlayStation 5"
        self.platform.save()
        self.cd.name = "PS5 Ninja Gaiden Ragebound"
        self.cd.game_series = GameSeries.objects.create(name="Ninja Gaiden")
        self.cd.save()
        self.profile.listing_title = "Ninjia Gaiden Ragebound PS5"
        self.profile.save()
        self.assertEqual(_search_query(self.cd, "cd"), "ninja gaiden ragebound PlayStation 5")

    def test_xbox_series_platform_prefix_and_typos(self):
        self.platform.name = "Xbox Series X"
        self.platform.save()
        self.cd.name = "XBOX Forza Horizon 5"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "forza horizon 5 Xbox Series X")
        self.assertTrue(product_matches(self.cd, "cd", full(40, 3000, "Forza Horison 5 Xbox Series X")))
        self.assertFalse(product_matches(self.cd, "cd", full(41, 3000, "Forza Horizon 5 Xbox One")))
        self.assertFalse(product_matches(self.cd, "cd", full(42, 3000, "Forza Horizon 6 Xbox Series X")))
        self.cd.name = "XBOX FC26"
        self.cd.save()
        self.assertEqual(_search_query(self.cd, "cd"), "fc 26 Xbox Series X")
        self.assertTrue(product_matches(self.cd, "cd", full(43, 3000, "FC 26 Xbox Series X")))

    def test_bounded_search_filters_deduplicates_and_sorts(self):
        pages = [[brief(999, 1), brief(11, 6000), brief(1, 1), brief(2, 500), brief(3, 3000), brief(4, 4000)],
                 [brief(2, 500), brief(5, 1500), brief(6, 900), brief(7, 1200), brief(8, 1000), brief(9, 1100)]]
        listings = {str(i): full(i, price) for i, price in ((1, 1), (2, 500), (3, 3000), (4, 4000),
                                                             (5, 1500), (6, 900), (7, 1200), (8, 1000), (9, 1100), (11, 6000))}
        listings["1"] = full(1, 1, description="Цена в описании, 5000 ₽")
        listings["2"] = full(2, 500, condition="Б/у")
        listings["6"] = full(6, 900, description="Аккаунт PSN")
        listings["8"] = full(8, 1000, title="PS5 Slim Digital")
        fake = FakeClient(pages, listings)
        result = search_offers(self.cd, "cd", client=fake)
        self.assertEqual([row["ad_id"] for row in result], ["9", "7"])
        self.assertEqual([price for price in map(lambda row: Decimal(row["price"]), result)], sorted(Decimal(row["price"]) for row in result))
        self.assertEqual(fake.calls[:2], [("search", 1, None), ("search", 2, None)])
        self.assertEqual(fake.calls.count(("listing", "2")), 1)
        self.assertNotIn(("listing", "999"), fake.calls)
        self.assertEqual(len([call for call in fake.calls if call[0] == "listing"]), 6)

    def test_economy_never_exceeds_ten_credits_even_without_matches(self):
        rows = [brief(i, 1000 + i) for i in range(1, 151)]
        listings = {str(i): full(i, 1000 + i, condition="Б/у") for i in range(1, 151)}
        fake = PagedPriceClient(rows, listings, page_size=50)
        stats = {}
        self.assertEqual(search_offers(self.cd, "cd", client=fake, stats=stats), [])
        self.assertEqual(stats["search_requests"], 2)
        self.assertEqual(stats["listing_requests"], 6)
        self.assertEqual(stats["credits"], 10)
        self.assertTrue(stats["search_limited"])
        self.assertTrue(stats["listing_limited"])
        self.assertNotIn(("search", 3, None), fake.calls)

    def test_deep_search_has_separate_bounded_budget(self):
        rows = [brief(i, 1000 + i) for i in range(1, 551)]
        fake = PagedPriceClient(rows, {str(i): full(i, 1000 + i, condition="Б/у") for i in range(1, 551)}, page_size=50)
        stats = {}
        self.assertEqual(search_offers(self.cd, "cd", client=fake, mode="deep", stats=stats), [])
        self.assertEqual((stats["search_requests"], stats["listing_requests"], stats["credits"]), (10, 20, 40))

    def test_cronos_digital_format_and_obfuscated_description_are_rejected(self):
        self.platform.name = "Nintendo Switch 2"
        self.platform.save()
        self.cd.name = "NS2 Cronos"
        self.cd.save()
        title = "Cronos: The New Dawn Nintendo Switch 2"
        for description in ("Новая игра", "Цифpовая лицeнзиoннaя веpсия", "Digital download", "Ключ активации", "Аккаунт Nintendo", "Цифровая копия"):
            with self.subTest(description=description):
                row = full(8204559868, 719, title, description=description)
                row["params"][1]["value"] = "Цифровой"
                self.assertFalse(product_matches(self.cd, "cd", row))
                self.assertFalse(physical_game(row))
        for description in ("Цифpовая лицeнзиoннaя веpсия", "Ци\u200bфровая копия", "Digital download", "aккаунт Nintendo", "Без картриджа", "Картриджа нет", "Код в коробке"):
            row = full(1, 719, title, description=description)
            row["params"] = row["params"][:1]
            self.assertFalse(physical_game(row), description)
        unknown = full(1, 4000, title, description="Новая игра в наличии")
        unknown["params"] = unknown["params"][:1]
        self.assertIsNone(_validated_offer(self.cd, "cd", "1", brief(1, 4000, title), unknown))
        for description in ("Новый картридж в заводской упаковке", "Новый диск в наличии"):
            row = {**unknown, "description": description}
            self.assertTrue(physical_game(row))
            self.assertIsNotNone(_validated_offer(self.cd, "cd", "1", brief(1, 4000, title), row))

    def test_digital_rows_never_reach_results_and_physical_copy_does(self):
        rows = [brief(i, 1000 + i * 100) for i in range(1, 5)]
        listings = {str(i): full(i, row["price"]) for i, row in enumerate(rows, 1)}
        for i in range(1, 4):
            listings[str(i)]["params"][1]["value"] = "Цифровой"
        fake = PagedPriceClient(rows, listings, page_size=50)
        self.assertEqual([row["ad_id"] for row in run_check(self.cd, "cd", client=fake)], ["4"])

    def test_digital_search_summary_is_rejected_without_listing_cost(self):
        for summary in ("Формат: Цифровой", {"Формат": "Цифровой"}, [{"name": "Формат", "value": "Цифровой"}]):
            fake = FakeClient([[brief(1, 719, params_summary=summary)]], {})
            self.assertEqual(search_offers(self.cd, "cd", client=fake), [])
            self.assertEqual(fake.calls, [("search", 1, None)])

    def test_daily_result_cache_costs_zero_and_refresh_bypasses_it(self):
        fake = FakeClient([[brief(1, 1000)]], {"1": full(1, 1000)})
        first = run_check(self.cd, "cd", client=fake)
        saved = AvitoPriceCheckResult.objects.get(profile=self.profile)
        fresh_calls = list(fake.calls)
        self.assertEqual(run_check(self.cd, "cd", client=fake), first)
        self.assertEqual(fake.calls, fresh_calls)
        saved.refresh_from_db()
        original_time = saved.checked_at
        run_check(self.cd, "cd", client=fake, force=True)
        self.assertEqual(len(fake.calls), 2 * len(fresh_calls))
        saved.refresh_from_db()
        self.assertGreater(saved.checked_at, original_time)

    def test_expired_results_recheck_search_and_reuse_fresh_listing(self):
        fake = FakeClient([[brief(1, 1000)]], {"1": full(1, 1000)})
        run_check(self.cd, "cd", client=fake)
        saved = AvitoPriceCheckResult.objects.get(profile=self.profile)
        saved.checked_at = timezone.now() - timedelta(hours=25)
        saved.save(update_fields=["checked_at"])
        run_check(self.cd, "cd", client=fake)
        self.assertEqual(fake.calls.count(("listing", "1")), 1)
        self.assertEqual(fake.calls.count(("search", 1, None)), 2)
        cached = AvitoCheckListingCache.objects.get(ad_id="1")
        cached.checked_at = timezone.now() - timedelta(hours=25)
        cached.save(update_fields=["checked_at"])
        saved.checked_at = timezone.now() - timedelta(hours=25)
        saved.save(update_fields=["checked_at"])
        run_check(self.cd, "cd", client=fake)
        self.assertEqual(fake.calls.count(("listing", "1")), 2)

    def test_old_results_are_hidden_until_revalidated(self):
        AvitoPriceCheckResult.objects.create(profile=self.profile, checked_at=timezone.now(),
                                             offers=[{"title": "Неверная цифровая копия", "price": "719"}])
        response = self.client.get(reverse("pricing:avito_check_automatic"))
        self.assertContains(response, "Результат прежней проверки требует обновления")
        self.assertNotContains(response, "Неверная цифровая копия")
        fake = FakeClient([[brief(1, 4000)]], {"1": full(1, 4000)})
        self.assertEqual(len(run_check(self.cd, "cd", client=fake)), 1)
        self.assertTrue(fake.calls)

    def test_unknown_check_mode_does_not_call_external_api(self):
        with patch("pricing.avito_check_views.run_check") as check:
            response = self.client.post(reverse("pricing:avito_check_run"), {"action": "unlimited"})
        self.assertEqual(response.status_code, 400)
        check.assert_not_called()

    def test_search_skips_game_accessories_before_paid_listing(self):
        rows = [brief(i, 1000 + i * 100, "Чехол для PS5 Slim Disc") for i in range(1, 7)]
        rows += [brief(i, 3000 + i * 100) for i in range(7, 12)]
        listings = {str(row["ad_id"]): full(row["ad_id"], row["price"], row["title"]) for row in rows}
        fake = PagedPriceClient(rows, listings, page_size=50)
        result = search_offers(self.cd, "cd", client=fake)
        self.assertEqual([row["ad_id"] for row in result], [str(i) for i in range(7, 10)])
        self.assertFalse(set(str(i) for i in range(1, 7)) & {call[1] for call in fake.calls if call[0] == "listing"})
        self.assertTrue(product_matches(self.cd, "cd", full(40, 4000, "PS5 Slim Disc, русская обложка")))

    def test_listing_requests_run_with_bounded_concurrency(self):
        class TimedClient(PagedPriceClient):
            active = 0
            peak = 0
            lock = Lock()

            def listing(self, ad_id):
                with self.lock:
                    self.active += 1
                    self.peak = max(self.peak, self.active)
                try:
                    sleep(0.02)
                    return super().listing(ad_id)
                finally:
                    with self.lock:
                        self.active -= 1

        rows = [brief(i, 3000 + i * 100) for i in range(1, 7)]
        fake = TimedClient(rows, {str(i): full(i, row["price"]) for i, row in enumerate(rows, 1)})
        self.assertEqual(len(search_offers(self.cd, "cd", client=fake)), 3)
        self.assertGreaterEqual(fake.peak, 2)
        self.assertLessEqual(fake.peak, 3)

    def test_partial_results_and_error_keep_old_cache(self):
        fake = FakeClient([[brief(1, 1000), brief(2, 1200)]], {"1": full(1, 1000), "2": full(2, 1200)})
        self.assertEqual(len(run_check(self.cd, "cd", client=fake)), 2)
        saved = AvitoPriceCheckResult.objects.get(profile=self.profile)
        failing = FakeClient([[brief(3, 900)]], {"3": ReefApiError("Сервис недоступен")})
        with self.assertRaises(ReefApiError):
            run_check(self.cd, "cd", client=failing, force=True)
        saved.refresh_from_db()
        self.assertEqual(len(saved.offers), 2)
        self.assertContains(self.client.get(reverse("pricing:avito_check_automatic")), "Найдено только 2 подходящих объявления")
        self.cd.refresh_from_db()
        self.assertEqual(self.cd.avito_price, Decimal("5000"))

    def test_next_updates_existing_prices_and_check_does_not(self):
        url = reverse("pricing:avito_check_automatic")
        self.assertContains(self.client.get(url), "Товар 1 из 1")
        fake = FakeClient([[brief(1, 1000)]], {"1": full(1, 1000)})
        with patch("pricing.avito_check_views.run_check", side_effect=lambda product, kind, **kwargs: run_check(product, kind, client=fake, **kwargs)):
            response = self.client.post(reverse("pricing:avito_check_run"), {"kind": "cd", "product_id": self.cd.pk})
        self.assertEqual(response.status_code, 200)
        self.cd.refresh_from_db(); self.assertEqual(self.cd.avito_price, Decimal("5000"))
        response = self.client.post(reverse("pricing:avito_check_next"), {
            "kind": "cd", "product_id": self.cd.pk, "wholesale_price": "4600", "avito_price": "5100",
        })
        self.assertEqual(response.status_code, 302)
        self.cd.refresh_from_db()
        self.assertEqual((self.cd.wholesale_price, self.cd.avito_price), (Decimal("4600"), Decimal("5100")))
        self.assertContains(self.client.get(response["Location"]), "Проверка списка завершена")

    def test_key_encrypted_and_absent_from_html(self):
        secret = "test-secret-reef-key"
        save_key(secret)
        credential = ReefApiCredential.objects.get(pk=1)
        self.assertNotIn(secret, credential.encrypted_api_key)
        for url in (reverse("integrations:api_keys"), reverse("pricing:avito_check_automatic")):
            self.assertNotIn(secret, self.client.get(url).content.decode())

    def test_invalid_price_preserves_input_and_both_existing_prices(self):
        response = self.client.post(reverse("pricing:avito_check_next"), {
            "kind": "cd", "product_id": self.cd.pk, "wholesale_price": "4600", "avito_price": "-1",
        })
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, 'value="4600"', status_code=400)
        self.cd.refresh_from_db()
        self.assertEqual((self.cd.wholesale_price, self.cd.avito_price), (Decimal("4500"), Decimal("5000")))

    def test_reef_http_errors_are_sanitized(self):
        class Response:
            status_code = 401
            def json(self):
                return {"ok": False, "error": {"code": "BAD_KEY", "message": "private-secret"}}
        client = ReefApiClient(key="private-secret", transport=lambda *args, **kwargs: Response())
        with self.assertRaises(ReefApiError) as caught:
            client.search("PS5", 1)
        self.assertNotIn("private-secret", str(caught.exception))

    def test_reef_search_sends_price_ceiling_only_when_requested(self):
        payloads = []

        class Response:
            status_code = 200

            def json(self):
                return {"ok": True, "data": {"listings": [], "has_more": False}}

        def transport(*args, **kwargs):
            payloads.append(kwargs["json"])
            return Response()

        client = ReefApiClient(key="test-key", transport=transport)
        client.search("PS5", 1, price_max=4673)
        client.search("PS5", 1)
        self.assertEqual(payloads[0]["price_max"], 4673)
        self.assertNotIn("price_max", payloads[1])
