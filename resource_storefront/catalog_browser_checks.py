"""Явная проверка сетки на реальных фото, только в тестовой БД."""
import os
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import override_settings
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright, expect
from catalog.models import CD, Tech, Platform, Brand, ProductType
from warehouse.models import Warehouse, CDWarehouseStock, TechWarehouseStock
from .models import StorefrontSettings, WholesaleContact, CatalogImageCrop
from .security import issue_link

@override_settings(RESOURCE_TOKEN_ENCRYPTION_KEY=Fernet.generate_key().decode())
class CatalogBrowserTests(StaticLiveServerTestCase):
    def setUp(self):
        warehouse, _ = Warehouse.objects.get_or_create(name="Проверка сетки каталога")
        StorefrontSettings.objects.update_or_create(pk=1, defaults={"warehouse":warehouse})
        platform=Platform.objects.create(name="Nintendo Switch 2")
        brand=Brand.objects.create(name="Sony / Nintendo")
        category=ProductType.objects.create(name="Консоль")
        self.products=[]
        with sqlite3.connect(f"file:{Path(settings.BASE_DIR)/'db.sqlite3'}?mode=ro",uri=True) as db:
            for index,(kind,pk) in enumerate([("cd",1),("tech",20),("tech",67),("tech",11),("tech",60),("tech",7)]):
                name,photo=db.execute(f"SELECT name,title_image FROM catalog_{kind} WHERE id=?",(pk,)).fetchone()
                model=CD if kind=="cd" else Tech
                fields={"platform":platform} if kind=="cd" else {"brand":brand,"product_type":category}
                product=model.objects.create(name=name,title_image=photo,wholesale_price=4500+index*10000,**fields)
                stock=CDWarehouseStock if kind=="cd" else TechWarehouseStock
                stock.objects.create(warehouse=warehouse,quantity=99,**{kind:product})
                self.products.append((kind,product))
                framing = {("cd",1):(62,50,"1.10"), ("tech",67):(57,50,"1.00"), ("tech",11):(95,50,"1.00"), ("tech",60):(55,50,"1.00")}.get((kind,pk))
                if framing and os.environ.get("RESOURCE_CATALOG_BASELINE") != "1":
                    CatalogImageCrop.objects.create(**{kind:product},position_x=framing[0],position_y=framing[1],zoom=framing[2])
        missing=Tech.objects.create(name="Товар без фото — очень длинное название комплекта с аксессуарами и дополнительным контроллером",brand=brand,product_type=category,wholesale_price="999999.99")
        TechWarehouseStock.objects.create(warehouse=warehouse,tech=missing,quantity=99)
        contact=WholesaleContact.objects.create(name="Проверка сетки",phone="+79990000000")
        _,self.token=issue_link(contact,None)
        self.staff=get_user_model().objects.create_superuser(username="crop-review",password="test-only-crop-password")
        self.client.force_login(self.staff)
        self.staff_cookie=self.client.cookies[settings.SESSION_COOKIE_NAME].value

    def test_grid(self):
        baseline=os.environ.get("RESOURCE_CATALOG_BASELINE")=="1"
        output=Path(settings.BASE_DIR)/"outputs"/"resource-catalog"/("before" if baseline else "after")
        output.mkdir(parents=True,exist_ok=True)
        with sync_playwright() as pw:
            for engine in ("chromium","webkit"):
                browser=getattr(pw,engine).launch()
                context=browser.new_context(viewport={"width":390,"height":844},is_mobile=True,has_touch=True)
                page=context.new_page()
                page.goto(self.live_server_url+"/opt/"+self.token+"/",wait_until="networkidle")
                for width in (360,390,430,1440):
                    page.set_viewport_size({"width":width,"height":844 if width<600 else 1000})
                    page.goto(self.live_server_url+"/opt/catalog/?sort=price",wait_until="networkidle")
                    page.screenshot(path=str(output/f"{engine}-{width}.png"),full_page=True)
                    if baseline: continue
                    self.assertLessEqual(page.evaluate("document.documentElement.scrollWidth"),width)
                    cards=page.locator(".rs-card")
                    if width<600:
                        boxes=cards.evaluate_all("els=>els.slice(0,2).map(e=>e.getBoundingClientRect().toJSON())")
                        self.assertAlmostEqual(boxes[0]["y"],boxes[1]["y"],delta=1)
                        self.assertGreater(boxes[1]["x"],boxes[0]["x"])
                    for box in page.locator(".rs-card-image").evaluate_all("els=>els.map(e=>e.getBoundingClientRect().toJSON())"):
                        self.assertAlmostEqual(box["width"]/box["height"],.75,delta=.01)
                    self.assertTrue(page.locator(".rs-card button").evaluate_all("els=>els.every(e=>e.getBoundingClientRect().height>=44)"))
                    self.assertTrue(page.locator(".rs-card-buy").evaluate_all("els=>els.every(e=>Math.abs(e.querySelector('[type=submit]').getBoundingClientRect().width-e.closest('.rs-card').getBoundingClientRect().width)<2)"))
                    self.assertTrue(page.locator(".rs-card-image>img").evaluate_all("els=>els.every(e=>e.complete && e.naturalWidth>0 && getComputedStyle(e).objectFit==='cover')"))
                    first=cards.first
                    first.locator('[data-quantity-step="1"]').click()
                    expect(first.locator('[name="quantity"]')).to_have_value("2")
                    first.locator('[name="quantity"]').fill("3")
                    url=page.url
                    first.get_by_role("button",name="В корзину").click()
                    expect(page.locator(".rs-toast")).to_contain_text("Добавлено")
                    self.assertEqual(page.url,url)
                context.close()
                if not baseline:
                    editor=browser.new_context(viewport={"width":1200,"height":900})
                    editor.add_cookies([{"name":settings.SESSION_COOKIE_NAME,"value":self.staff_cookie,"url":self.live_server_url}])
                    tab=editor.new_page()
                    tab.goto(self.live_server_url+"/crm/admin/resource_storefront/catalogimagecrop/1/change/",wait_until="networkidle")
                    expect(tab.locator("[data-crop-preview]")).to_be_visible()
                    tab.locator("#id_position_x").fill("70")
                    self.assertEqual(tab.locator("[data-crop-preview]").evaluate("e=>e.style.objectPosition"),"70% 50%")
                    tab.screenshot(path=str(output/f"{engine}-crop-editor.png"),full_page=True)
                    editor.close()
                browser.close()
