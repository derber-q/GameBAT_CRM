import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from catalog.models import CD, Tech
from partners.models import Supplier


class PriceDocumentSettings(models.Model):
    company_name = models.CharField("Название компании", max_length=255, default="ReSOURCE")
    address = models.CharField("Адрес", max_length=500, blank=True)
    phone_1 = models.CharField("Телефон №1", max_length=40, blank=True)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    website = models.URLField("Сайт", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    logo = models.ImageField("Логотип", upload_to="price_documents/", blank=True)
    additional_text = models.TextField("Дополнительный текст", blank=True)

    class Meta:
        verbose_name = "настройки документов прайса"
        verbose_name_plural = "настройки документов прайса"
        permissions = [
            ("view_price_page", "Прайс: просмотр раздела"),
            ("change_document_settings", "Прайс: изменение данных документов"),
            ("generate_retail_price", "Прайс: создание розничного файла"),
            ("generate_wholesale_price", "Прайс: создание оптового файла"),
            ("download_supplier_template", "Прайс: скачивание шаблона поставщика"),
            ("upload_supplier_price", "Прайс: загрузка цен поставщика"),
            ("view_supplier_prices", "Прайс: просмотр цен поставщиков"),
            ("create_procurement_price_list", "Прайс: создание закупочного прайса"),
            ("change_procurement_markup", "Прайс: изменение наценки"),
            ("change_procurement_delivery", "Прайс: изменение доставки"),
            ("export_procurement_price_list", "Прайс: экспорт закупочного прайса"),
        ]

    @classmethod
    def get_solo(cls):
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return None

    def __str__(self):
        return "Данные ReSOURCE для прайс-листов"


class ProcurementPriceList(models.Model):
    public_token = models.UUIDField("Публичный токен", default=uuid.uuid4, unique=True, editable=False)
    exchange_rate_aed_rub = models.DecimalField(
        "Курс AED → RUB", max_digits=20, decimal_places=6, validators=[MinValueValidator(0.000001)]
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        related_name="procurement_price_lists", verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "закупочный прайс"
        verbose_name_plural = "закупочные прайсы"

    def __str__(self):
        return f"Закупочный прайс №{self.pk}"


class ProcurementPriceListItem(models.Model):
    class ProductKind(models.TextChoices):
        CD = "cd", "CD"
        TECH = "tech", "Tech"

    price_list = models.ForeignKey(
        ProcurementPriceList, on_delete=models.PROTECT, related_name="items", verbose_name="Прайс"
    )
    product_kind = models.CharField("Тип товара", max_length=8, choices=ProductKind.choices, editable=False)
    cd = models.ForeignKey(
        CD, on_delete=models.PROTECT, related_name="procurement_price_items",
        verbose_name="CD", null=True, blank=True, editable=False,
    )
    tech = models.ForeignKey(
        Tech, on_delete=models.PROTECT, related_name="procurement_price_items",
        verbose_name="Техника", null=True, blank=True, editable=False,
    )
    product_name_snapshot = models.CharField("Название товара", max_length=255, editable=False)
    article_snapshot = models.CharField("Артикул", max_length=100, editable=False)
    selected_supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="selected_procurement_items",
        verbose_name="Выбранный поставщик", editable=False,
    )
    supplier_price_aed = models.DecimalField(
        "Цена поставщика, AED", max_digits=20, decimal_places=6,
        validators=[MinValueValidator(0.000001)], editable=False,
    )
    exchange_rate_aed_rub = models.DecimalField(
        "Курс AED → RUB", max_digits=20, decimal_places=6,
        validators=[MinValueValidator(0.000001)], editable=False,
    )
    base_price_rub = models.DecimalField("База, RUB", max_digits=20, decimal_places=2, editable=False)
    markup_rub = models.DecimalField(
        "Наценка, RUB", max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    delivery_rub = models.DecimalField(
        "Доставка, RUB", max_digits=20, decimal_places=2, default=0, validators=[MinValueValidator(0)]
    )
    prepayment_price_rub = models.DecimalField(
        "Цена предоплаты, RUB", max_digits=20, decimal_places=2, editable=False
    )
    postpayment_price_rub = models.DecimalField(
        "Цена постоплаты, RUB", max_digits=20, decimal_places=2, editable=False
    )

    class Meta:
        ordering = ("product_name_snapshot", "id")
        verbose_name = "позиция закупочного прайса"
        verbose_name_plural = "позиции закупочного прайса"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(product_kind="cd", cd__isnull=False, tech__isnull=True)
                    | models.Q(product_kind="tech", cd__isnull=True, tech__isnull=False)
                ),
                name="procurement_price_item_exact_product",
            ),
            models.UniqueConstraint(
                fields=("price_list", "cd"), condition=models.Q(cd__isnull=False),
                name="unique_procurement_price_cd",
            ),
            models.UniqueConstraint(
                fields=("price_list", "tech"), condition=models.Q(tech__isnull=False),
                name="unique_procurement_price_tech",
            ),
            models.CheckConstraint(condition=models.Q(base_price_rub__gte=0), name="proc_base_nonnegative"),
            models.CheckConstraint(condition=models.Q(markup_rub__gte=0), name="proc_markup_nonnegative"),
            models.CheckConstraint(condition=models.Q(delivery_rub__gte=0), name="proc_delivery_nonnegative"),
            models.CheckConstraint(
                condition=models.Q(prepayment_price_rub__gte=0), name="proc_prepayment_nonnegative"
            ),
            models.CheckConstraint(
                condition=models.Q(postpayment_price_rub__gte=0), name="proc_postpayment_nonnegative"
            ),
        ]

    @property
    def product(self):
        return self.cd if self.product_kind == self.ProductKind.CD else self.tech

    @property
    def product_id(self):
        return self.cd_id if self.product_kind == self.ProductKind.CD else self.tech_id

    def __str__(self):
        return self.product_name_snapshot
