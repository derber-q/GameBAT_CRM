from django.core.validators import MinValueValidator
from django.db import models


class NamedReference(models.Model):
    name = models.CharField("Название", max_length=120, unique=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self):
        return self.name


class Platform(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "платформа"
        verbose_name_plural = "платформы"


class Brand(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "бренд"
        verbose_name_plural = "бренды"


class ProductType(NamedReference):
    class Meta(NamedReference.Meta):
        verbose_name = "тип товара"
        verbose_name_plural = "типы товара"


class ProductBase(models.Model):
    name = models.CharField("Название", max_length=255)
    description = models.TextField("Описание", blank=True)
    sku = models.CharField("Артикул", max_length=100)
    barcode = models.CharField("Штрихкод", max_length=100)
    quantity = models.PositiveIntegerField("Количество", default=0)
    quantity_on_consignment = models.PositiveIntegerField("На реализации", default=0, editable=False)
    cost = models.DecimalField("Средняя себестоимость", max_digits=20, decimal_places=6, default=0, validators=[MinValueValidator(0)])
    comment = models.TextField("Комментарий", blank=True)

    class Meta:
        abstract = True
        ordering = ("name", "id")

    def __str__(self):
        return self.name


class CD(ProductBase):
    platform = models.ForeignKey(Platform, on_delete=models.PROTECT, related_name="cds", verbose_name="Платформа")
    cusa_ppsa_code = models.CharField("CUSA/PPSA код", max_length=100, blank=True)

    class Meta(ProductBase.Meta):
        verbose_name = "CD"
        verbose_name_plural = "CD"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="cd_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_on_consignment__gte=0), name="cd_consignment_nonnegative"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="cd_cost_nonnegative"),
        ]


class Tech(ProductBase):
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Бренд")
    product_type = models.ForeignKey(ProductType, on_delete=models.PROTECT, related_name="tech_items", verbose_name="Тип товара")

    class Meta(ProductBase.Meta):
        verbose_name = "техника"
        verbose_name_plural = "техника"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=0), name="tech_quantity_nonnegative"),
            models.CheckConstraint(condition=models.Q(quantity_on_consignment__gte=0), name="tech_consignment_nonnegative"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="tech_cost_nonnegative"),
        ]
