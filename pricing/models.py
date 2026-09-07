from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier


class SupplierPriceBase(models.Model):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, verbose_name="Поставщик")
    price = models.DecimalField(
        "Текущая цена", max_digits=20, decimal_places=6, default=0, validators=[MinValueValidator(0)]
    )
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        abstract = True


class SupplierCDPrice(SupplierPriceBase):
    cd = models.ForeignKey(CD, on_delete=models.PROTECT, related_name="supplier_prices", verbose_name="CD")

    class Meta:
        verbose_name = "текущая цена поставщика на CD"
        verbose_name_plural = "текущие цены поставщиков на CD"
        permissions = [
            ("view_pricing", "Может просматривать ценообразование"),
            ("view_supplier_prices", "Может просматривать текущие цены поставщиков"),
            ("change_supplier_prices", "Может изменять текущие цены поставщиков"),
            ("change_retail_price", "Может изменять розничные цены"),
            ("change_wholesale_price", "Может изменять оптовые цены"),
            ("change_yandex_market_price", "Может изменять цены Яндекс Маркет"),
        ]
        constraints = [
            models.UniqueConstraint(fields=("supplier", "cd"), name="unique_supplier_cd_price"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="supplier_cd_price_nonnegative"),
        ]

    def __str__(self):
        return f"{self.supplier.safe_label}: {self.cd}"


class SupplierTechPrice(SupplierPriceBase):
    tech = models.ForeignKey(Tech, on_delete=models.PROTECT, related_name="supplier_prices", verbose_name="Техника")

    class Meta:
        verbose_name = "текущая цена поставщика на технику"
        verbose_name_plural = "текущие цены поставщиков на технику"
        constraints = [
            models.UniqueConstraint(fields=("supplier", "tech"), name="unique_supplier_tech_price"),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="supplier_tech_price_nonnegative"),
        ]

    def __str__(self):
        return f"{self.supplier.safe_label}: {self.tech}"
