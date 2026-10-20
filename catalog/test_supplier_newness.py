from datetime import datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from partners.models import Supplier

from .audit import field_change, record_product_changes
from .models import Brand, CD, Platform, ProductChangeEvent, ProductSupplierExclusion, ProductType, Tech
from .newness import newness_expiry
from .newness_backfill import apply_newness_backfill, build_newness_backfill, web_creation_evidence
from .nomenclature_forms import CDCreateForm, TechCreateForm, product_version
from .nomenclature_services import create_product, update_product_card
from .supplier_exclusions import set_supplier_exclusions


class SupplierNewnessTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('newness-owner')
        self.other = User.objects.create_user('other-creator')
        self.platform = Platform.objects.create(name='PlayStation 5')
        self.brand = Brand.objects.create(name='Sony')
        self.product_type = ProductType.objects.create(name='Консоли')
        self.supplier = Supplier.objects.create(name='Поставщик A', letter='A', highlight_color='#37A7BA', legal_entity='A', phone_1='1')

    def cd(self, **kwargs):
        return CD.objects.create(platform=self.platform, name='Игра', **kwargs)

    def test_create_forms_default_to_one_month_and_supplier_choices_are_dynamic(self):
        for form_class in (CDCreateForm, TechCreateForm):
            with self.subTest(form=form_class):
                form = form_class(user=self.user)
                self.assertEqual(form['newness_months'].value(), '1')
                self.assertTrue(form.fields['newness_months'].required)
                second = Supplier.objects.create(name='Новый', letter=f'N{form_class.__name__[0]}', highlight_color='#37A7BA', legal_entity='N', phone_1='1')
                self.assertIn(second, form.fields['excluded_suppliers'].queryset)

    def test_required_and_custom_duration_validation(self):
        data = {'platform': self.platform.pk, 'name': 'Игра', 'weight_grams': 120}
        self.assertIn('newness_months', CDCreateForm(data).errors)
        for custom in ('', '0', '-1', '1.5', 'abc'):
            with self.subTest(custom=custom):
                form = CDCreateForm({**data, 'newness_months': 'custom', 'newness_custom_months': custom})
                self.assertFalse(form.is_valid())
                self.assertIn('newness_custom_months', form.errors)
        valid = CDCreateForm({**data, 'newness_months': 'custom', 'newness_custom_months': '7'})
        self.assertTrue(valid.is_valid(), valid.errors)
        self.assertEqual(valid.cleaned_data['newness_months'], 7)

    def test_web_create_records_origin_chosen_duration_and_exclusions(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('nomenclature:create'), {
            'product_kind': 'cd', 'platform': self.platform.pk, 'name': 'Ручная карточка',
            'newness_months': '3', 'excluded_suppliers': [self.supplier.pk],
        })
        self.assertEqual(response.status_code, 302)
        product = CD.objects.get(name='Ручная карточка')
        self.assertEqual(product.creation_source, CD.CreationSource.WEB)
        self.assertEqual(product.created_by, self.user)
        self.assertEqual(product.newness_until, newness_expiry(product.created_at, 3))
        self.assertTrue(product.is_new)
        self.assertTrue(product.supplier_exclusions.filter(supplier=self.supplier).exists())
        self.assertTrue(product.change_events.filter(action_kind='product_web_create').exists())

    def test_automatic_service_and_direct_model_do_not_enable_newness(self):
        product = create_product(actor=self.user, product_kind='cd', data={'platform': self.platform, 'name': 'Скрипт'})
        direct = self.cd()
        self.assertEqual(product.creation_source, CD.CreationSource.AUTOMATIC)
        self.assertEqual(direct.creation_source, CD.CreationSource.UNKNOWN)
        for item in (product, direct):
            self.assertEqual(item.newness_months, 0)
            self.assertFalse(item.is_new)

    def test_calendar_month_end_and_name_edit_do_not_extend_newness(self):
        created = datetime(2024, 1, 31, 12, tzinfo=dt_timezone.utc)
        self.assertEqual(newness_expiry(created, 1).day, 29)
        self.assertEqual(newness_expiry(created, 1).month, 2)
        product = self.cd(created_at=created, newness_months=1)
        original = product.newness_until
        product.name = 'Другое название'
        product.save(update_fields=('name',))
        product.refresh_from_db()
        self.assertEqual(product.newness_until, original)
        with patch('catalog.models.timezone.now', return_value=original - timedelta(seconds=1)):
            self.assertTrue(product.is_new)
        with patch('catalog.models.timezone.now', return_value=original):
            self.assertFalse(product.is_new)
        product.newness_months = 5
        product.save(update_fields=('newness_months',))
        self.assertEqual(product.newness_until, newness_expiry(created, 5))

    def test_exclusions_are_unique_product_specific_audited_and_versioned(self):
        first, second = self.cd(), self.cd()
        before = product_version(first)
        set_supplier_exclusions(product=first, supplier_ids=[self.supplier.pk, self.supplier.pk], actor=self.user)
        self.assertEqual(first.supplier_exclusions.count(), 1)
        self.assertFalse(second.supplier_exclusions.exists())
        self.assertNotEqual(product_version(first), before)
        exclusion = first.supplier_exclusions.get()
        self.assertEqual(exclusion.created_by, self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductSupplierExclusion.objects.create(cd=first, supplier=self.supplier)
        set_supplier_exclusions(product=first, supplier_ids=[], actor=self.user)
        self.assertFalse(first.supplier_exclusions.exists())
        self.assertEqual(first.change_events.count(), 2)

    def test_exclusion_service_checks_permission(self):
        with self.assertRaises(PermissionDenied):
            set_supplier_exclusions(product=self.cd(), supplier_ids=[self.supplier.pk], actor=self.other)

    def test_legacy_edit_post_preserves_new_options_and_explicit_checkbox_marker_clears(self):
        product = self.cd(newness_months=3)
        set_supplier_exclusions(product=product, supplier_ids=[self.supplier.pk], actor=self.user)
        # Полная старая форма была скачана до появления новых опций.
        from .nomenclature_forms import CDCardForm
        form = CDCardForm(instance=product, user=self.user)
        data = {name: form[name].value() for name in form.allowed_fields
                if name in form.fields and name not in ('newness_months', 'newness_custom_months', 'excluded_suppliers')}
        data.update({'version': product_version(product), 'name': 'Изменено старой формой'})
        result = update_product_card(actor=self.user, product_kind='cd', product_id=product.pk, data=data)
        self.assertTrue(result.saved, result.form.errors)
        product.refresh_from_db()
        self.assertEqual(product.newness_months, 3)
        self.assertTrue(product.supplier_exclusions.exists())
        data.update({'version': product_version(product), 'product_options_present': '1'})
        result = update_product_card(actor=self.user, product_kind='cd', product_id=product.pk, data=data)
        self.assertTrue(result.saved, result.form.errors)
        self.assertFalse(product.supplier_exclusions.exists())

    def test_forged_post_cannot_change_supplier_exclusions_with_name_permission(self):
        self.other.user_permissions.add(Permission.objects.get(content_type__app_label='catalog', codename='change_cd_name'))
        product = self.cd()
        result = update_product_card(actor=self.other, product_kind='cd', product_id=product.pk,
            data={'version': product_version(product), 'name': 'Новое', 'excluded_suppliers': [str(self.supplier.pk)]})
        self.assertFalse(result.saved)
        self.assertIn('excluded_suppliers', result.form.forbidden_fields)
        self.assertFalse(product.supplier_exclusions.exists())

    def test_tech_web_form_saves_newness_and_excluded_supplier(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('nomenclature:create'), {
            'product_kind': 'tech', 'brand': self.brand.pk, 'product_type': self.product_type.pk,
            'name': 'Ручная техника', 'newness_months': 'custom', 'newness_custom_months': '7',
            'excluded_suppliers': [self.supplier.pk],
        })
        self.assertEqual(response.status_code, 302)
        product = Tech.objects.get(name='Ручная техника')
        self.assertEqual(product.newness_months, 7)
        self.assertEqual(product.newness_until, newness_expiry(product.created_at, 7))
        self.assertTrue(product.supplier_exclusions.filter(supplier=self.supplier).exists())

    def test_backfill_requires_explicit_web_origin_correct_user_and_is_idempotent(self):
        now = timezone.now()
        created = now - timedelta(days=10)
        manual = self.cd(created_at=created, created_by=self.user, creation_source=CD.CreationSource.WEB)
        automatic = self.cd(created_at=created, created_by=self.user, creation_source=CD.CreationSource.AUTOMATIC)
        other_user = self.cd(created_at=created, created_by=self.other, creation_source=CD.CreationSource.WEB)
        old = self.cd(created_at=now - timedelta(days=70), created_by=self.user, creation_source=CD.CreationSource.WEB)
        unknown = self.cd(created_at=created, created_by=self.user)
        # Старый аудит «Номенклатура» мог оставить и скрипт: одного actor недостаточно.
        CD.objects.filter(pk=unknown.pk).update(creation_source=CD.CreationSource.UNKNOWN)
        record_product_changes(actor=self.user, instance=unknown, source=ProductChangeEvent.Source.NOMENCLATURE,
                               changes=[field_change(field_name='created', field_label='Создан', old_value='', new_value='CD')])
        plan = build_newness_backfill(user_id=self.user.pk, as_of=now)
        self.assertEqual(plan['counts'].get('eligible'), 1)
        self.assertEqual(next(r for r in plan['rows'] if r['id'] == unknown.pk)['status'], 'uncertain')
        changed = apply_newness_backfill(plan)
        self.assertEqual([r['id'] for r in changed], [manual.pk])
        manual.refresh_from_db()
        self.assertEqual(manual.newness_until, newness_expiry(created, 1))
        for product in (automatic, other_user, old, unknown):
            product.refresh_from_db()
            self.assertEqual(product.newness_months, 0)
        repeated = build_newness_backfill(user_id=self.user.pk, as_of=now)
        self.assertEqual(apply_newness_backfill(repeated), [])
        self.assertEqual(manual.change_events.count(), 1)

    def test_explicit_no_newness_choice_is_not_overwritten_by_backfill(self):
        product = create_product(actor=self.user, product_kind='cd', creation_source=CD.CreationSource.WEB,
                                 data={'platform': self.platform, 'name': 'Без выделения', 'newness_months': 0})
        plan = build_newness_backfill(user_id=self.user.pk, as_of=timezone.now())
        self.assertEqual(next(r for r in plan['rows'] if r['id'] == product.pk)['status'], 'configured')
        self.assertEqual(apply_newness_backfill(plan), [])

    def test_newness_metadata_does_not_enqueue_avito_but_name_change_still_does(self):
        product = self.cd()
        with patch('integrations.signals._enqueue_for_product') as enqueue:
            product.newness_months = 3
            product.save(update_fields=('newness_months',))
            enqueue.assert_not_called()
            product.name = 'Новое название'
            product.save(update_fields=('name',))
            enqueue.assert_called_once_with(product)

    def test_explicit_edit_of_legacy_duration_uses_creation_audit_without_assuming_web_origin(self):
        product = self.cd()
        event = record_product_changes(actor=self.user, instance=product, source=ProductChangeEvent.Source.NOMENCLATURE,
            changes=[field_change(field_name='created', field_label='Создан', old_value='', new_value='CD')])
        CD.objects.filter(pk=product.pk).update(created_at=None, creation_source=CD.CreationSource.UNKNOWN)
        product.refresh_from_db()
        from .nomenclature_forms import CDCardForm
        form = CDCardForm(instance=product, user=self.user)
        data = {name: form[name].value() for name in form.allowed_fields if name in form.fields}
        data.update({'version': product_version(product), 'newness_months': '3', 'product_options_present': '1'})
        result = update_product_card(actor=self.user, product_kind='cd', product_id=product.pk, data=data)
        self.assertTrue(result.saved, result.form.errors)
        product.refresh_from_db()
        self.assertEqual(product.created_at, event.created_at)
        self.assertEqual(product.newness_until, newness_expiry(event.created_at, 3))
        self.assertEqual(product.creation_source, CD.CreationSource.UNKNOWN)

    def test_http_chain_confirms_legacy_creation_but_missing_post_does_not(self):
        product = self.cd()
        CD.objects.filter(pk=product.pk).update(created_at=None, created_by=None, creation_source=CD.CreationSource.UNKNOWN)
        event = record_product_changes(actor=self.user, instance=product, source=ProductChangeEvent.Source.NOMENCLATURE,
            changes=[field_change(field_name='created', field_label='Создан', old_value='', new_value='CD')])
        stamp = timezone.localtime(event.created_at).strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
        lines = [f'{stamp} INFO gamebat.business: Товар создан: user_id={self.user.pk} type=cd product_id={product.pk}',
                 f'{stamp} INFO django.server: "POST /crm/nomenclature/new/?kind=cd HTTP/1.1" 302 0',
                 f'{stamp} INFO django.server: "GET /crm/nomenclature/cd/{product.pk}/ HTTP/1.1" 200 1000']
        with TemporaryDirectory() as folder:
            log = Path(folder) / 'server.log'
            log.write_bytes('\n'.join(lines).encode('cp1251'))
            proofs = web_creation_evidence(folder)
            plan = build_newness_backfill(user_id=self.user.pk, as_of=timezone.now(), web_evidence=proofs)
            self.assertEqual(plan['counts'].get('eligible'), 1)
            self.assertIsNotNone(plan['rows'][0]['http_creation_proof'])
            log.write_text('\n'.join((lines[0], lines[2])), 'utf-8')
            self.assertFalse(web_creation_evidence(folder))
        apply_newness_backfill(plan)
        product.refresh_from_db()
        self.assertEqual(product.created_at, event.created_at)
        self.assertEqual(product.creation_source, CD.CreationSource.WEB)
        self.assertEqual(product.newness_until, newness_expiry(event.created_at, 1))
