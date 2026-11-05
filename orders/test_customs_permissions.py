"""Раздельные права и поддельный JSON не изменяют документ или справочники."""
import json
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from django.urls import reverse
from accounts.models import User
from .test_customs import CustomsTests
from .customs_service import source_snapshot,prepare_rows,save_document,download_existing
from .customs_models import CustomsManifest,CustomsProductDefaults,CustomsGroup


class CustomsPermissionsTests(CustomsTests):
    def employee(self,*codes):
        user=User.objects.create_user('customs-permissions-'+str(User.objects.count()))
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='orders',codename__in=codes))
        return user

    def test_missing_view_and_edit_permissions_are_enforced_on_http_and_service(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        viewer=self.employee('view_customs_manifest');self.client.force_login(viewer)
        url=reverse('orders:customs',args=[self.trip.pk])
        response=self.client.get(url);self.assertEqual(response.status_code,200)
        self.assertNotContains(response,'data-customs-action="save"')
        payload={'action':'save','revision':0,'source_signature':snapshot.signature,'rows':rows}
        self.assertEqual(self.client.post(url,{'payload':json.dumps(payload,default=str)}).status_code,403)
        with self.assertRaises(PermissionDenied):save_document(actor=viewer,trip_id=self.trip.pk,
            expected_revision=0,source_signature=snapshot.signature,rows=rows)
        denied=self.employee();self.client.force_login(denied)
        self.assertEqual(self.client.get(url).status_code,403)
        self.assertFalse(CustomsManifest.objects.exists())

    def test_download_permission_does_not_grant_edit_and_cannot_change_posted_values(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        manifest,_=self.save(snapshot,rows)
        employee=self.employee('view_customs_manifest','download_customs_manifest');self.client.force_login(employee)
        rows[0]['country']='FORGED'
        response=self.client.post(reverse('orders:customs',args=[self.trip.pk]),{'payload':json.dumps({
            'action':'download','revision':1,'source_signature':snapshot.signature,'acknowledged':True,'rows':rows},default=str)})
        self.assertEqual(response.status_code,200)
        self.assertEqual(CustomsManifest.objects.count(),1)
        self.assertEqual(manifest.lines.get().country,'AUSTRIA')
        file=self.client.get(response.json()['download_url']);self.assertEqual(file.status_code,200)
        self.assertTrue(b''.join(file.streaming_content).startswith(b'PK'))
        self.client.force_login(self.employee('view_customs_manifest'))
        self.assertEqual(self.client.get(response.json()['download_url']).status_code,403)

    def test_quantity_and_global_defaults_require_their_own_permissions(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        user=self.employee('view_customs_manifest','change_customs_manifest')
        changed=[dict(rows[0],quantity=11,quantity_confirmed=True,quantity_reason='Попытка без полномочий')]
        with self.assertRaises(PermissionDenied):save_document(actor=user,trip_id=self.trip.pk,
            expected_revision=0,source_signature=snapshot.signature,rows=changed)
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('orders:customs_rules')).status_code,403)
        self.assertFalse(CustomsProductDefaults.objects.exists())

    def test_rules_use_real_platform_and_detect_conflicts(self):
        from .customs_forms import CustomsGroupForm
        group=self.group();self.client.force_login(self.user)
        data={'name':group.name,'medium':'disc','platform':self.cd.platform_id,'unit':'ШТ','active':'on',
            'ru_description':'Проверенная группа','country':'AUSTRIA','expected_updated':group.updated_at.isoformat(),
            'confirm_values':'on'}
        url=reverse('orders:customs_rule_edit',args=[group.pk])
        self.assertEqual(self.client.post(url,data).status_code,302)
        group.refresh_from_db();self.assertIn('country',group.confirmed_fields)
        response=self.client.post(url,data);self.assertContains(response,'другим сотрудником')
        invalid={**data,'platform':'999999','medium':'tech'}
        self.assertFalse(CustomsGroupForm(invalid,instance=group).is_valid())

    def test_previous_revision_is_read_only_and_keeps_its_own_values(self):
        self.group();self.reviewed_arrival();snapshot=source_snapshot(self.trip.pk);rows=prepare_rows(snapshot)
        manifest,_=self.save(snapshot,rows)
        rows[0]['country']='JAPAN';self.save(snapshot,rows,revision=1)
        response=self.client.get(reverse('orders:customs',args=[self.trip.pk]),{'revision':1})
        self.assertContains(response,'Просмотр исторической редакции 1')
        self.assertFalse(response.context['can_edit'])
        self.assertEqual(response.context['rows'][0]['country'],'AUSTRIA')
        self.assertNotContains(response,'data-customs-action="save"')
