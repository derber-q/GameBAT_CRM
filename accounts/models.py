from django.contrib.auth.models import AbstractUser, Group
from django.db import models


def verification_document_path(instance, filename):
    return f"verification_documents/{instance.pk or 'new'}/{filename}"


class User(AbstractUser):
    full_name = models.CharField("Ф.И.О.", max_length=255, blank=True)
    phone_1 = models.CharField("Телефон №1", max_length=40, blank=True)
    phone_2 = models.CharField("Телефон №2", max_length=40, blank=True)
    phone_3 = models.CharField("Телефон №3", max_length=40, blank=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    verification_document = models.ImageField(
        "Подтверждающий документ", upload_to=verification_document_path, blank=True
    )

    class Meta(AbstractUser.Meta):
        verbose_name = "пользователь"
        verbose_name_plural = "пользователи"
        permissions = [
            ("view_user_document", "Может просматривать подтверждающие документы"),
            ("reset_user_password", "Может сбрасывать пароли пользователей"),
        ]

    @property
    def role_label(self):
        return "Администратор" if self.is_superuser else "Работник"

    def __str__(self):
        return self.full_name or self.username


class PermissionSetMetadata(models.Model):
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name="gamebat_metadata", verbose_name="Набор прав")
    description = models.TextField("Описание", blank=True)

    class Meta:
        verbose_name = "описание набора прав"
        verbose_name_plural = "описания наборов прав"

    def __str__(self):
        return self.group.name
