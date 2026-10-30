from django.db import models
from django.core.validators import MinValueValidator
from .validators import hex_color_validator
from django.core.exceptions import ValidationError
from django.db import transaction
import uuid


class Supplier(models.Model):
    name = models.CharField("Название", max_length=255)
    letter = models.CharField("Буква", max_length=8, unique=True)
    highlight_color = models.CharField("Цвет", max_length=7, validators=[hex_color_validator])
    legal_entity = models.CharField("Юридическое лицо", max_length=255)
    email = models.EmailField("Email", blank=True)
    phone_1 = models.CharField("Телефон №1", max_length=40)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    phone_3 = models.CharField("Телефон №3", max_length=40, blank=True)
    website = models.URLField("Сайт", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    priority = models.PositiveIntegerField("Приоритет", default=1000, validators=[MinValueValidator(1)])

    class Meta:
        ordering = ("letter",)
        verbose_name = "поставщик"
        verbose_name_plural = "поставщики"
        permissions = [("view_supplier_details", "Может видеть полные данные поставщиков")]

    def __str__(self):
        return self.name

    @property
    def safe_label(self):
        return f"[{self.letter}]"


class SalesPlatform(models.Model):
    name = models.CharField("Название", max_length=255)
    address = models.CharField("Адрес", max_length=500)
    legal_entity = models.CharField("Юридическое лицо", max_length=255)
    phone_1 = models.CharField("Телефон №1", max_length=40)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    phone_3 = models.CharField("Телефон №3", max_length=40, blank=True)
    email = models.EmailField("Email", blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)

    class Meta:
        ordering = ("name",)
        verbose_name = "площадка реализации"
        verbose_name_plural = "площадки реализации"

    def __str__(self):
        return self.name


class Partner(models.Model):
    creation_key = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField("Название", max_length=255)
    contact_person = models.CharField("Контактное лицо", max_length=255, blank=True)
    phone_1 = models.CharField("Телефон №1", max_length=40, blank=True)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True, default='', db_default='')
    address = models.TextField("Адрес", blank=True)
    platform = models.OneToOneField(SalesPlatform, on_delete=models.PROTECT, null=True, blank=True,
        related_name="partner", verbose_name="Площадка реализации")
    creditor = models.OneToOneField("creditors.Creditor", on_delete=models.PROTECT,
        related_name="partner", verbose_name="Кредиторский счёт", editable=False)
    is_archived = models.BooleanField("В архиве", default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "pk")
        verbose_name = "партнёр"
        verbose_name_plural = "партнёры"
        permissions = [("view_partner_contacts", "Может просматривать контакты партнёров")]

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        contact = str(self.contact_person or '').strip()
        return f'{self.name} ({contact})' if contact else self.name

    @property
    def telegram_chat_url(self):
        from .telegram import telegram_chat_url
        return telegram_chat_url(self.telegram)

    def clean(self):
        super().clean()
        self._normalize_telegram()

    def _normalize_telegram(self):
        from .telegram import normalize_telegram
        try:
            self.telegram = normalize_telegram(self.telegram)
        except ValidationError as exc:
            raise ValidationError({'telegram': exc.messages}) from exc

    @transaction.atomic
    def save(self, *args, **kwargs):
        self._normalize_telegram()
        self.name = str(self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": "Укажите название партнёра."})
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list('creditor_id', flat=True).first()
            if previous and previous != self.creditor_id:
                raise ValidationError('Кредиторский счёт существующего партнёра нельзя заменять.')
        if not self.creditor_id:
            from creditors.models import Creditor
            self.creditor = Creditor.objects.create(name=f"{self.name[:230]} · {uuid.uuid4().hex[:10]}")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError('Партнёров следует архивировать, чтобы сохранить историю и кредиторский счёт.')
