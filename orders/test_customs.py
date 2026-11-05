"""Таможенный документ использует только сверенное фактическое прибытие."""
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError, PermissionDenied
from django.apps import apps
from .test_arrival import ArrivalFixture
from .arrival import reduce_received
from .customs_models import CustomsGroup,CustomsManifest,CustomsProductDefaults,CustomsManifestExport
from .customs_service import source_snapshot,prepare_rows,save_document,manifest_rows,save_defaults


class CustomsTests(ArrivalFixture, TestCase):
    def test_prearrival_document_uses_planned_trip_and_refreshes_to_actual(self):
        self.group();snapshot=source_snapshot(self.trip.pk)
        self.assertEqual(snapshot.source_kind,'planned');self.assertEqual(snapshot.total,12)
        rows=prepare_rows(snapshot);rows[0]['en_description']='Preserved before arrival'
        rows[0]['confirmed_fields'].append('en_description')
        manifest,export=self.save(snapshot,rows,export=True,acknowledged=True)
        self.assertEqual(manifest.source_kind,'planned');self.assertIsNone(manifest.arrival_id)
        self.assertIsNone(manifest.arrived_at);self.assertTrue(export)
        self.assertTrue(manifest.sources.filter(trip_line__isnull=False).exists())
        self.assertFalse(manifest.sources.filter(arrival_row__isnull=False).exists())
        arrival=self.reviewed_arrival()
        with self.assertRaisesMessage(ValidationError,'состав'):self.save(snapshot,manifest_rows(manifest),revision=1)
        updated,_=self.save(snapshot,manifest_rows(manifest),revision=1,refresh=True)
        self.assertEqual(updated.source_kind,'actual');self.assertEqual(updated.arrival_id,arrival.pk)
        self.assertEqual(updated.lines.get().en_description,'Preserved before arrival')
        self.assertTrue(updated.sources.filter(arrival_row__isnull=False).exists())
        self.no_stock_change()

    def reviewed_arrival(self):
        arrival=self.arrive()
        for order in self.trip.trip_orders.order_by('pk'):
            rows=arrival.rows.filter(order=order)
            reduce_received(actor=self.user,arrival_id=arrival.pk,order_id=order.pk,
                quantities={r.pk:r.actual_quantity for r in rows},expected_revision=arrival.revision)
            arrival.refresh_from_db()
        return arrival

    def add_product(self,product,quantity):
        from price.models import ProcurementPriceListItem
        from .trips import add_orders_to_trip
        kind='cd' if product._meta.model_name=='cd' else 'tech'
        source=self.price.items.filter(**{kind:product}).first()
        if not source:
            data={f.attname:getattr(self.source,f.attname) for f in self.source._meta.fields if not f.primary_key}
            data.update(product_kind=kind,cd_id=product.pk if kind=='cd' else None,
                tech_id=product.pk if kind=='tech' else None,product_name_snapshot=product.name,article_snapshot=product.sku)
            source=ProcurementPriceListItem.objects.create(**data)
        original=self.source;self.source=source
        try:order=self.make_order('stock',quantity)
        finally:self.source=original
        add_orders_to_trip(actor=self.user,batch_id=self.trip.pk,order_ids=[order.pk],revision=self.trip.revision)
        self.trip.refresh_from_db()
        return order

    def test_actual_sources_and_review_do_not_require_financial_finalization(self):
        from .customs_service import source_snapshot, prepare_rows
        arrival=self.arrive()
        with self.assertRaisesMessage(ValidationError,'свер'):source_snapshot(self.trip.pk)
        for order in (self.order,self.stock_order):
            row=arrival.rows.get(order=order)
            reduce_received(actor=self.user,arrival_id=arrival.pk,order_id=order.pk,
                quantities={row.pk:8 if order==self.order else 0},expected_revision=arrival.revision)
            arrival.refresh_from_db()
        snapshot=source_snapshot(self.trip.pk)
        self.assertIsNone(arrival.finalized_at)
        self.assertEqual(snapshot.total,8)
        rows=prepare_rows(snapshot)
        self.assertEqual(sum(r['quantity'] for r in rows),8)
        self.assertEqual(sum(len(r['sources']) for r in rows),1)
        self.no_stock_change()

    def test_template_is_original_layout_with_no_real_shipment_values(self):
        from .customs_excel import TEMPLATE,build_workbook
        from openpyxl import load_workbook
        clean=load_workbook(TEMPLATE);sheet=clean['ОПИСАНИЕ']
        self.assertEqual(clean.sheetnames,['ОПИСАНИЕ'])
        self.assertEqual(sheet['A5'].value,'GRAND TOTAL')
        self.assertIn('A5:J5',{str(m) for m in sheet.merged_cells.ranges})
        self.assertFalse(any(c.value is not None for row in sheet.iter_rows(min_row=6) for c in row))

    def group(self,**values):
        return CustomsGroup.objects.create(name='Игровые диски для PS5',platform=self.cd.platform,medium='disc',
            ru_description='Игровые диски для PS5',updated_by=self.user,**values)

    def save(self,snapshot,rows,revision=0,**options):
        return save_document(actor=self.user,trip_id=self.trip.pk,expected_revision=revision,
            source_signature=snapshot.signature,rows=rows,**options)

    def test_group_defaults_and_history_use_actual_totals_without_changing_business_rows(self):
        group=self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk)
        before=list(snapshot.arrival.rows.values());orders=list(self.trip.trip_orders.values())
        rows=prepare_rows(snapshot)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['quantity'],12)
        self.assertEqual(rows[0]['country'],'AUSTRIA');self.assertEqual(rows[0]['material'],'ПЛАСТИК')
        self.assertEqual(rows[0]['unit'],'ШТ');self.assertEqual(rows[0]['manufacturer'],'')
        self.assertNotIn('en_description',rows[0]['confirmed_fields'])
        manifest,_=self.save(snapshot,rows)
        self.assertEqual(manifest.sources.count(),2)
        self.assertEqual(sum(manifest.sources.values_list('actual_quantity',flat=True)),12)
        revised=manifest_rows(manifest);revised[0]['en_description']='Video game discs for PlayStation 5'
        revised[0]['confirmed_fields'].append('en_description')
        next_manifest,_=self.save(snapshot,revised,revision=manifest.revision)
        self.assertEqual(next_manifest.revision,2);self.assertEqual(CustomsManifest.objects.count(),2)
        self.assertNotEqual(manifest.lines.get().en_description,next_manifest.lines.get().en_description)
        self.assertEqual(list(snapshot.arrival.rows.values()),before);self.assertEqual(list(self.trip.trip_orders.values()),orders)
        self.no_stock_change()

    def test_quantity_correction_is_explicit_and_does_not_change_arrival(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        rows[0]['quantity']=11
        with self.assertRaisesMessage(ValidationError,'подтверждения'):self.save(snapshot,rows)
        rows[0].update(quantity_confirmed=True,quantity_reason='Исправлена отдельная таможенная упаковка')
        manifest,_=self.save(snapshot,rows)
        self.assertEqual((manifest.source_total,manifest.edited_total),(12,11))
        self.assertEqual(sum(snapshot.arrival.rows.values_list('actual_quantity',flat=True)),12)
        self.assertEqual(manifest.lines.get().quantity_approved_by,self.user)
        self.assertTrue(manifest.events.get().details['quantity_changes'])

    def test_stale_refresh_preserves_confirmed_english_and_rejects_old_editor(self):
        self.group();arrival=self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        rows[0]['en_description']='Video game discs';rows[0]['confirmed_fields'].append('en_description')
        manifest,_=self.save(snapshot,rows)
        row=arrival.rows.get(order=self.order)
        reduce_received(actor=self.user,arrival_id=arrival.pk,order_id=self.order.pk,
            quantities={row.pk:8},expected_revision=arrival.revision)
        with self.assertRaisesMessage(ValidationError,'Фактический состав'):self.save(snapshot,manifest_rows(manifest),revision=1)
        refreshed,_=self.save(snapshot,manifest_rows(manifest),revision=1,refresh=True)
        self.assertEqual(refreshed.edited_total,10)
        self.assertEqual(refreshed.lines.get().en_description,'Video game discs')
        self.assertIn('en_description',refreshed.lines.get().confirmed_fields)
        with self.assertRaisesMessage(ValidationError,'другим сотрудником'):self.save(snapshot,rows,revision=1)

    def test_defaults_are_explicit_and_applied_only_to_future_preparations(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        manifest,_=self.save(snapshot,rows)
        rows=manifest_rows(manifest);rows[0].update(en_description='Verified game media',country='JAPAN',
            hs_code='0123456789',confirmed_fields=['en_description','country','hs_code'])
        save_defaults(actor=self.user,trip_id=self.trip.pk,expected_revision=1,source_signature=snapshot.signature,
            key=rows[0]['stable_key'],data=rows[0],target='product',product_kind='cd',product_id=self.cd.pk)
        self.assertEqual(manifest.lines.get().country,'AUSTRIA')
        fresh=prepare_rows(snapshot)[0]
        self.assertEqual(fresh['country'],'JAPAN');self.assertEqual(fresh['hs_code'],'0123456789')
        self.assertEqual(fresh['en_description'],'Verified game media')
        self.cd.refresh_from_db();self.assertEqual(self.cd.name,'Игра')

    def test_export_warning_confirmation_and_file_history(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        with self.assertRaisesMessage(ValidationError,'предупреждения'):self.save(snapshot,rows,export=True)
        self.assertFalse(CustomsManifest.objects.exists())
        manifest,export=self.save(snapshot,rows,export=True,acknowledged=True)
        self.assertEqual(export.manifest,manifest);self.assertTrue(export.acknowledged_warnings)
        from openpyxl import load_workbook
        from io import BytesIO
        with export.file.open('rb') as f:book=load_workbook(BytesIO(f.read()))
        self.assertEqual(book.active['I6'].value,12);self.assertEqual(book.active.max_row,6)
        self.assertEqual(CustomsManifestExport.objects.count(),1)

    def test_platform_rules_are_explicit_and_unknown_platform_is_not_guessed(self):
        from catalog.models import CD,Platform
        self.group()
        for index,(name,medium,country) in enumerate((('PS4','disc','AUSTRIA'),('Nintendo Switch','cartridge','CHINA'),
            ('Nintendo Switch 2','cartridge','CHINA'),('Other PS5 media',None,'')),1):
            platform=Platform.objects.create(name=name)
            product=CD.objects.create(name='Игра '+name,platform=platform,sku=f'CUSTOMS-{index}',weight_grams=100)
            if medium:CustomsGroup.objects.create(name='Группа '+name,platform=platform,medium=medium,
                ru_description='Группа '+name,updated_by=self.user)
            self.add_product(product,index)
        self.reviewed_arrival();rows=prepare_rows(source_snapshot(self.trip.pk))
        self.assertEqual(sum(r['quantity'] for r in rows),22)
        self.assertEqual(len(rows),5)
        unknown=next(r for r in rows if r['ru_description']=='Игра Other PS5 media')
        self.assertEqual(unknown['country'],'');self.assertTrue(unknown['review_notes'])
        for row in rows:
            if 'Nintendo' in row['ru_description']:self.assertEqual(row['country'],'CHINA')
            if row['group_id']:self.assertEqual(row['material'],'ПЛАСТИК')

    def test_technical_models_are_separate_and_same_model_merges_across_orders(self):
        from catalog.models import Tech,Brand,ProductType
        brand=Brand.objects.create(name='Brand only');kind=ProductType.objects.create(name='Контроллеры таможни')
        tech=Tech.objects.create(name='Контроллер белый',brand=brand,product_type=kind,weight_grams=1000,sku='CUSTOMS-WHITE')
        other=Tech.objects.create(name='Контроллер синий',brand=brand,product_type=kind,weight_grams=1000,sku='CUSTOMS-BLUE')
        self.add_product(tech,2);self.add_product(tech,3);self.add_product(other,4)
        arrival=self.reviewed_arrival()
        # Разные закупочные цены искусственных источников не являются ключом группировки.
        arrival.rows.filter(tech=tech).first().__class__.objects.filter(pk=arrival.rows.filter(tech=tech).first().pk).update(price_aed=999)
        rows=prepare_rows(source_snapshot(self.trip.pk));technical=[r for r in rows if r['sources'][0]['product_kind']=='tech']
        self.assertEqual(len(technical),2)
        white=next(r for r in technical if 'белый' in r['ru_description'])
        self.assertEqual(white['quantity'],5);self.assertEqual(len(white['sources']),2)
        self.assertEqual(white['country'],'CHINA');self.assertEqual(white['material'],'МЕТАЛЛ / ПЛАСТИК')
        self.assertEqual(white['manufacturer'],'Brand only');self.assertNotIn('manufacturer',white['confirmed_fields'])

    def test_conflicting_characteristics_split_game_groups(self):
        from catalog.models import CD
        self.group();other=CD.objects.create(name='Другая игра PS5',platform=self.cd.platform,sku='OTHER-CUSTOMS',weight_grams=100)
        self.add_product(other,3);self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk)
        profile=CustomsProductDefaults.objects.create(cd=other,country='JAPAN',confirmed_fields=['country'],updated_by=self.user)
        self.assertEqual(len(prepare_rows(snapshot)),2)
        group=CustomsGroup.objects.get(platform=self.cd.platform)
        for field,base,different in [('material','ПЛАСТИК','ДРУГОЙ МАТЕРИАЛ'),('manufacturer','TEST A','TEST B'),
            ('hs_code','1111111111','2222222222'),('marking','MARK A','MARK B'),('unit','ШТ','НАБОР')]:
            setattr(group,field,base);group.confirmed_fields=[field];group.save()
            profile.country='';setattr(profile,field,different);profile.confirmed_fields=[field];profile.save()
            with self.subTest(field=field):
                rows=prepare_rows(snapshot);self.assertEqual(len(rows),2);self.assertEqual(sum(r['quantity'] for r in rows),15)

    def test_added_warehouse_sale_positions_are_not_imported_sources(self):
        from .arrival_documents import create_arrival_sale
        from .operation_changes import ChangesConfirmationRequired
        from uuid import uuid4
        arrival=self.reviewed_arrival();row=arrival.rows.get(order=self.order)
        values=dict(actor=self.user,arrival_id=arrival.pk,order_id=self.order.pk,expected_revision=arrival.revision,
            warehouse_id=self.warehouse.pk,draft_key=uuid4(),lines=[
                {'product_type':'cd','product_id':self.cd.pk,'quantity':10,'trip_row':str(row.pk)},
                {'product_type':'cd','product_id':self.cd.pk,'quantity':2,'trip_row':''}])
        try:create_arrival_sale(**values)
        except ChangesConfirmationRequired as exc:create_arrival_sale(**values,changes_confirmation=exc.token)
        snapshot=source_snapshot(self.trip.pk)
        self.assertEqual(snapshot.total,12);self.assertEqual(sum(r['quantity'] for r in prepare_rows(snapshot)),12)

    def test_ambiguous_refresh_keeps_old_edits_in_history_and_demands_review(self):
        from catalog.models import CD
        self.group();other=CD.objects.create(name='Игра с другим происхождением',platform=self.cd.platform,sku='SPLIT-CUSTOMS',weight_grams=100)
        self.add_product(other,3)
        profile=CustomsProductDefaults.objects.create(cd=other,country='JAPAN',confirmed_fields=['country'],updated_by=self.user)
        self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        self.assertEqual(len(rows),2)
        rows[0]['en_description']='Preserved old custom description'
        manifest,_=self.save(snapshot,rows)
        profile.confirmed_fields=[];profile.country='';profile.save()
        refreshed,_=self.save(snapshot,manifest_rows(manifest),revision=1,refresh=True)
        self.assertEqual(refreshed.lines.count(),1);self.assertEqual(refreshed.edited_total,15)
        self.assertIn('Неоднозначное',refreshed.lines.get().review_notes)
        self.assertTrue(manifest.lines.filter(en_description='Preserved old custom description').exists())

    def test_illegal_excel_text_and_noninteger_quantities_do_not_save(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        rows[0]['ru_description']='Illegal\x00text'
        with self.assertRaises(ValidationError):self.save(snapshot,rows)
        rows[0]['ru_description']='Safe'
        for value in ('1.5','1e2','NaN','-1','9223372036854775808'):
            rows[0]['quantity']=value
            with self.subTest(value=value),self.assertRaises(ValidationError):self.save(snapshot,rows)
        self.assertFalse(CustomsManifest.objects.exists())
