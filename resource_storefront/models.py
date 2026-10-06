from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
import uuid

from catalog.models import CD, Tech
from sales.models import Sale
from warehouse.models import Warehouse


class WholesaleContact(models.Model):
    name = models.CharField("Контактное имя", max_length=160)
    phone = models.CharField("Основной номер телефона", max_length=40)
    address = models.TextField("Адрес", blank=True)
    is_archived = models.BooleanField("Архивирован", default=False)
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "оптовый контакт"
        verbose_name_plural = "оптовые контакты"
        permissions = [("manage_wholesale_contacts", "Управление контактами оптовой витрины")]

    def __str__(self):
        return f"{self.name} · {self.phone}"


class WholesaleAccessLink(models.Model):
    contact = models.ForeignKey(WholesaleContact, on_delete=models.PROTECT, related_name="access_links")
    token_digest = models.CharField(max_length=64, unique=True, editable=False)
    encrypted_token = models.TextField(editable=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="wholesale_links_created")
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        verbose_name = "ссылка оптового доступа"
        verbose_name_plural = "ссылки оптового доступа"
        constraints = [models.UniqueConstraint(fields=("contact",), condition=models.Q(is_active=True), name="resource_one_active_link_per_contact")]


class StorefrontSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Склад витрины")
    minimum_order_amount = models.DecimalField("Минимальная сумма заказа", max_digits=20, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(0)])
    hero_title = models.CharField("Заголовок главной", max_length=220, blank=True)
    hero_description = models.TextField("Описание главной", blank=True)
    hero_button_label = models.CharField("Текст кнопки", max_length=80, blank=True)
    hero_button_url = models.CharField("Адрес кнопки", max_length=300, blank=True)
    hero_image_desktop = models.ImageField(upload_to="resource/hero/", blank=True)
    hero_image_mobile = models.ImageField(upload_to="resource/hero/", blank=True)
    about_text = models.TextField("О бренде", blank=True)
    wholesale_terms = models.TextField("Условия оптовой работы", blank=True)
    public_contacts = models.TextField("Контакты", blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "настройки оптовой витрины"
        verbose_name_plural = "настройки оптовой витрины"
        permissions = [("manage_storefront", "Управление содержимым оптовой витрины")]

    @classmethod
    def get_solo(cls):
        return cls.objects.get_or_create(pk=1)[0]


class StorefrontProduct(models.Model):
    class Placement(models.TextChoices):
        NEW = "new", "Новинки"
        HOME = "home", "Главная подборка"

    placement = models.CharField(max_length=8, choices=Placement.choices)
    cd = models.ForeignKey(CD, null=True, blank=True, on_delete=models.CASCADE, related_name="storefront_slots")
    tech = models.ForeignKey(Tech, null=True, blank=True, on_delete=models.CASCADE, related_name="storefront_slots")
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.CheckConstraint(condition=(models.Q(cd__isnull=False, tech__isnull=True) | models.Q(cd__isnull=True, tech__isnull=False)), name="resource_slot_exact_product"),
            models.UniqueConstraint(fields=("placement", "cd"), condition=models.Q(cd__isnull=False), name="resource_slot_unique_cd"),
            models.UniqueConstraint(fields=("placement", "tech"), condition=models.Q(tech__isnull=False), name="resource_slot_unique_tech"),
        ]

    @property
    def product(self):
        return self.cd or self.tech

    @property
    def product_kind(self):
        return "cd" if self.cd_id else "tech"


class ProductCollection(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    is_visible = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("sort_order", "id")
        verbose_name = "подборка витрины"
        verbose_name_plural = "подборки витрины"


class CollectionProduct(models.Model):
    collection = models.ForeignKey(ProductCollection, on_delete=models.CASCADE, related_name="items")
    cd = models.ForeignKey(CD, null=True, blank=True, on_delete=models.CASCADE, related_name="collection_slots")
    tech = models.ForeignKey(Tech, null=True, blank=True, on_delete=models.CASCADE, related_name="collection_slots")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [models.CheckConstraint(condition=(models.Q(cd__isnull=False, tech__isnull=True) | models.Q(cd__isnull=True, tech__isnull=False)), name="resource_collection_exact_product")]

    @property
    def product(self):
        return self.cd or self.tech

    @property
    def product_kind(self):
        return "cd" if self.cd_id else "tech"


class StorefrontNews(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликовано"

    title = models.CharField(max_length=220)
    slug = models.SlugField(max_length=240, unique=True)
    cover = models.ImageField(upload_to="resource/news/", blank=True)
    excerpt = models.TextField(blank=True)
    body = models.TextField(blank=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    products = models.ManyToManyField(CD, through="NewsCDProduct", related_name="storefront_news", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-published_at", "-id")
        verbose_name = "новость витрины"
        verbose_name_plural = "новости витрины"


class NewsCDProduct(models.Model):
    news = models.ForeignKey(StorefrontNews, on_delete=models.CASCADE)
    cd = models.ForeignKey(CD, on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)


class NewsTechProduct(models.Model):
    news = models.ForeignKey(StorefrontNews, on_delete=models.CASCADE)
    tech = models.ForeignKey(Tech, on_delete=models.CASCADE)
    sort_order = models.PositiveIntegerField(default=0)


class StorefrontSubmission(models.Model):
    contact = models.ForeignKey(WholesaleContact, on_delete=models.PROTECT, related_name="submissions")
    idempotency_key = models.CharField(max_length=64)
    cart_digest = models.CharField(max_length=64)
    sale = models.OneToOneField(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name="storefront_submission")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("contact", "idempotency_key"), name="resource_submission_once_per_contact")]


class CatalogImageCrop(models.Model):
    cd = models.OneToOneField(CD, null=True, blank=True, on_delete=models.CASCADE, verbose_name="Диск")
    tech = models.OneToOneField(Tech, null=True, blank=True, on_delete=models.CASCADE, verbose_name="Техника")
    source_image = models.CharField(max_length=300, editable=False)
    position_x = models.PositiveSmallIntegerField("Фокус по горизонтали, %", default=50, validators=[MaxValueValidator(100)], help_text="0 — слева, 50 — центр, 100 — справа.")
    position_y = models.PositiveSmallIntegerField("Фокус по вертикали, %", default=50, validators=[MaxValueValidator(100)], help_text="0 — сверху, 50 — центр, 100 — снизу.")
    zoom = models.DecimalField("Масштаб", max_digits=3, decimal_places=2, default=1, validators=[MinValueValidator(1), MaxValueValidator(3)], help_text="1 — обычное заполнение 3:4. Увеличивайте только для конкретного фото с лишними полями.")

    class Meta:
        verbose_name = "кадрирование фото каталога"
        verbose_name_plural = "кадрирование фото каталога"
        constraints = [
            models.CheckConstraint(condition=(models.Q(cd__isnull=False, tech__isnull=True) | models.Q(cd__isnull=True, tech__isnull=False)), name="resource_crop_exact_product"),
            models.CheckConstraint(condition=models.Q(position_x__lte=100, position_y__lte=100, zoom__gte=1, zoom__lte=3), name="resource_crop_bounds"),
        ]

    @property
    def product(self):
        return self.cd or self.tech

    def clean(self):
        from django.core.exceptions import ValidationError
        if bool(self.cd_id) == bool(self.tech_id):
            raise ValidationError("Выберите один товар: диск или технику.")
        if not self.product.title_image:
            raise ValidationError("Сначала загрузите титульное фото товара.")

    def save(self, *args, **kwargs):
        self.source_image = self.product.title_image.name
        super().save(*args, **kwargs)

    def __str__(self):
        return str(self.product)


class RetailSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    warehouse = models.ForeignKey(Warehouse, null=True, blank=True, on_delete=models.PROTECT, verbose_name="Склад розничного сайта")
    price_source = models.CharField("Источник цены", max_length=24, choices=[("avito_price", "Цена Avito")], default="avito_price")
    generation = models.UUIDField(default=uuid.uuid4, editable=False)
    token_digest = models.CharField(max_length=64, blank=True, editable=False)
    encrypted_token = models.TextField(blank=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    minimum_order_amount = None

    class Meta:
        verbose_name = "настройки розничной витрины"
        verbose_name_plural = "настройки розничной витрины"
        permissions = [("manage_retail_storefront", "Управление розничной витриной и общей ссылкой")]


class RetailSubmission(models.Model):
    visitor_id = models.UUIDField()
    idempotency_key = models.UUIDField()
    cart_digest = models.CharField(max_length=64)
    sale = models.OneToOneField(Sale, null=True, blank=True, on_delete=models.PROTECT, related_name="retail_submission")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=("visitor_id", "idempotency_key"), name="resource_retail_submission_once")]
