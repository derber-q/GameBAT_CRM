"""Изолированные таможенные документы; поля не участвуют в складском учёте."""
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

CUSTOMS_FIELDS=('number','hs_code','marking','ru_description','en_description','material','country','manufacturer','unit')
CONFIRMABLE_FIELDS=tuple(f for f in CUSTOMS_FIELDS if f!='number')


class CustomsValues(models.Model):
    number=models.CharField('N',max_length=32,blank=True)
    hs_code=models.CharField('Код ТН ВЭД',max_length=10,blank=True)
    marking=models.CharField('Маркировка',max_length=255,blank=True)
    ru_description=models.TextField('Описание на русском',max_length=2000,blank=True)
    en_description=models.TextField('Описание на английском',max_length=2000,blank=True)
    material=models.CharField('Материал',max_length=120,blank=True)
    country=models.CharField('Страна',max_length=80,blank=True)
    manufacturer=models.CharField('Производитель',max_length=255,blank=True)
    unit=models.CharField('Единица',max_length=24,default='ШТ')
    confirmed_fields=models.JSONField(default=list,blank=True)

    class Meta:abstract=True

    def clean(self):
        super().clean()
        import re
        for field in CUSTOMS_FIELDS:
            if re.search(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff]',getattr(self,field)):
                raise ValidationError({field:'Текст содержит символы, недопустимые в Excel.'})
        if self.hs_code and not re.fullmatch(r'[0-9]{10}',self.hs_code):
            raise ValidationError({'hs_code':'Введите 10 цифр либо оставьте код пустым. Формат не подтверждает правильность классификации.'})
        if not isinstance(self.confirmed_fields,list) or any(f not in CONFIRMABLE_FIELDS for f in self.confirmed_fields):
            raise ValidationError('Некорректный список подтверждённых характеристик.')
        if any(not getattr(self,f) for f in self.confirmed_fields):
            raise ValidationError('Пустая характеристика не может считаться подтверждённой.')


class CustomsGroup(CustomsValues):
    name=models.CharField('Название группы',max_length=160)
    medium=models.CharField('Тип товара/носителя',max_length=16,choices=[
        ('disc','Игровой диск'),('cartridge','Игровой картридж'),('tech','Техника')])
    platform=models.OneToOneField('catalog.Platform',null=True,blank=True,on_delete=models.PROTECT,related_name='customs_group')
    product_type=models.OneToOneField('catalog.ProductType',null=True,blank=True,on_delete=models.PROTECT,related_name='customs_group')
    active=models.BooleanField(default=True)
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

    class Meta:
        default_permissions=()
        ordering=('name','pk')
        constraints=[models.CheckConstraint(condition=(models.Q(platform__isnull=False,product_type__isnull=True)|
            models.Q(platform__isnull=True,product_type__isnull=False)),name='customs_group_one_reference')]

    def __str__(self):return self.name


class CustomsProductDefaults(CustomsValues):
    cd=models.OneToOneField('catalog.CD',null=True,blank=True,on_delete=models.CASCADE,related_name='customs_defaults')
    tech=models.OneToOneField('catalog.Tech',null=True,blank=True,on_delete=models.CASCADE,related_name='customs_defaults')
    updated_at=models.DateTimeField(auto_now=True)
    updated_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)

    class Meta:
        default_permissions=()
        constraints=[models.CheckConstraint(condition=(models.Q(cd__isnull=False,tech__isnull=True)|
            models.Q(cd__isnull=True,tech__isnull=False)),name='customs_defaults_one_product')]


class CustomsManifest(models.Model):
    """Каждое сохранение создаёт новую редакцию, прежние строки остаются в истории."""
    trip=models.ForeignKey('orders.SupplierOrderBatch',on_delete=models.PROTECT,related_name='customs_manifests')
    arrival=models.ForeignKey('orders.TripArrival',null=True,on_delete=models.PROTECT,related_name='customs_manifests')
    source_kind=models.CharField(max_length=8,default='actual',choices=[('planned','Состав рейса'),('actual','Фактическое прибытие')])
    revision=models.PositiveIntegerField()
    arrival_revision=models.PositiveIntegerField()
    trip_revision=models.PositiveIntegerField()
    source_signature=models.CharField(max_length=64)
    arrived_at=models.DateTimeField(null=True)
    source_total=models.PositiveBigIntegerField()
    edited_total=models.PositiveBigIntegerField()
    reviewed_order_ids=models.JSONField(default=list)
    status=models.CharField(max_length=16,default='prepared',choices=[('prepared','Подготовлена'),('review','Требует проверки')])
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions=()
        ordering=('-revision',)
        constraints=[models.UniqueConstraint(fields=('trip','revision'),name='customs_manifest_trip_revision')]
        permissions=[('view_customs_manifest','Таможенная опись: просмотр'),
            ('change_customs_manifest','Таможенная опись: подготовка и редактирование'),
            ('download_customs_manifest','Таможенная опись: скачивание'),
            ('manage_customs_rules','Таможенная опись: общие правила и подтверждение характеристик'),
            ('approve_customs_quantity','Таможенная опись: подтверждение отличия количества')]


class CustomsManifestLine(CustomsValues):
    manifest=models.ForeignKey(CustomsManifest,on_delete=models.CASCADE,related_name='lines')
    group=models.ForeignKey(CustomsGroup,null=True,blank=True,on_delete=models.SET_NULL)
    stable_key=models.CharField(max_length=64)
    position=models.PositiveIntegerField()
    expected_quantity=models.PositiveBigIntegerField()
    quantity=models.PositiveBigIntegerField()
    quantity_reason=models.CharField(max_length=500,blank=True)
    quantity_confirmed=models.BooleanField(default=False)
    quantity_approved_by=models.ForeignKey(settings.AUTH_USER_MODEL,null=True,on_delete=models.PROTECT,related_name='+')
    quantity_approved_at=models.DateTimeField(null=True)
    edited_fields=models.JSONField(default=list,blank=True)
    review_notes=models.TextField(max_length=2000,blank=True)

    class Meta:
        default_permissions=()
        ordering=('position','pk')
        constraints=[models.UniqueConstraint(fields=('manifest','stable_key'),name='customs_line_unique_key')]


class CustomsManifestSource(models.Model):
    """SET_NULL сохраняет историю и не блокирует штатное пересоздание строк прибытия."""
    manifest=models.ForeignKey(CustomsManifest,on_delete=models.CASCADE,related_name='sources')
    line=models.ForeignKey(CustomsManifestLine,on_delete=models.CASCADE,related_name='sources')
    arrival_row=models.ForeignKey('orders.TripCostRow',null=True,on_delete=models.SET_NULL)
    trip_line=models.ForeignKey('orders.SupplierOrderBatchLine',null=True,on_delete=models.SET_NULL)
    source_kind=models.CharField(max_length=8,default='actual',choices=[('planned','Состав рейса'),('actual','Фактическое прибытие')])
    source_row_id=models.PositiveBigIntegerField()
    product_kind=models.CharField(max_length=8,choices=[('cd','CD'),('tech','Tech')])
    product_id_snapshot=models.PositiveBigIntegerField()
    product_name_snapshot=models.CharField(max_length=255)
    cd=models.ForeignKey('catalog.CD',null=True,on_delete=models.SET_NULL)
    tech=models.ForeignKey('catalog.Tech',null=True,on_delete=models.SET_NULL)
    actual_quantity=models.PositiveBigIntegerField()

    class Meta:
        default_permissions=()
        constraints=[models.UniqueConstraint(fields=('manifest','source_row_id'),name='customs_source_once_per_manifest')]


class CustomsManifestExport(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    manifest=models.ForeignKey(CustomsManifest,on_delete=models.PROTECT,related_name='exports')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    file=models.FileField(upload_to='customs_manifests/')
    filename=models.CharField(max_length=180)
    sha256=models.CharField(max_length=64)
    template_sha256=models.CharField(max_length=64)
    size=models.PositiveBigIntegerField()
    acknowledged_warnings=models.JSONField(default=list)

    class Meta:
        default_permissions=()
        ordering=('-created_at',)


class CustomsEvent(models.Model):
    manifest=models.ForeignKey(CustomsManifest,null=True,on_delete=models.SET_NULL,related_name='events')
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    action=models.CharField(max_length=32)
    details=models.JSONField(default=dict)

    class Meta:
        default_permissions=()
        ordering=('-created_at','-pk')
