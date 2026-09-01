from django.core.validators import MinValueValidator
from django.db import models


class CurrencyRate(models.Model):
    class Pair(models.TextChoices):
        USD_RUB = "USD_RUB", "USD/RUB"
        AED_RUB = "AED_RUB", "AED/RUB"
        USD_AED = "USD_AED", "USD/AED"

    pair = models.CharField("Валютная пара", max_length=7, choices=Pair.choices, unique=True)
    rate = models.DecimalField(
        "Курс", max_digits=16, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "курс валют"
        verbose_name_plural = "курсы валют"
        permissions = [("access_admin_panel", "Может входить в административную панель")]
        constraints = [models.CheckConstraint(condition=models.Q(rate__gte=0) | models.Q(rate__isnull=True), name="currency_rate_nonnegative")]

    def __str__(self):
        return self.get_pair_display()
