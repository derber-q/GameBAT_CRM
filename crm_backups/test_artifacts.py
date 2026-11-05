"""ZIP проверяется и публикуется явно; файловые пути не принимаются веб-клиентом."""
import json
from pathlib import Path
import tempfile
import zipfile
from django.test import TestCase,override_settings
from django.urls import reverse
from django.contrib.auth.models import Permission
from accounts.models import User
from .client_apps import package_extension,publish


class ApplicationArtifactsTests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'extension';self.source.mkdir()
        manifest={'manifest_version':3,'name':'Synthetic extension','version':'1.6.4',
            'background':{'service_worker':'background.js'},'content_scripts':[{'js':['page.js'],'css':['page.css']}]}
        (self.source/'manifest.json').write_text(json.dumps(manifest))
        for name in ('background.js','page.js','page.css'):(self.source/name).write_text('/* artificial */')
        self.enterContext(override_settings(CRM_APP_ARTIFACT_ROOT=self.root/'published'))
        self.actor=User.objects.create_superuser('publisher')

    def test_real_zip_publication_permissions_and_immutable_file(self):
        target=self.root/'extension.zip';package_extension(self.source,target)
        with zipfile.ZipFile(target) as stream:self.assertIn('manifest.json',stream.namelist())
        artifact=publish('opera',target,self.actor,notes='Test fixture')
        user=User.objects.create_user('app-reader');self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('crm_backups:applications')).status_code,403)
        user.user_permissions.add(Permission.objects.get(content_type__app_label='crm_backups',codename='download_client_apps'))
        self.client.force_login(user)
        self.assertContains(self.client.get(reverse('crm_backups:applications')),'1.6.4')
        response=self.client.get(reverse('crm_backups:app_download',args=[artifact.pk]))
        self.assertEqual(b''.join(response.streaming_content),target.read_bytes())
        self.assertEqual(self.client.get('/crm/backups/apps/download/../../db.sqlite3/').status_code,404)

    def test_missing_resource_and_private_file_are_refused(self):
        (self.source/'page.js').unlink()
        with self.assertRaises(ValueError):package_extension(self.source,self.root/'bad.zip')
        (self.source/'page.js').write_text('/* fake */')
        (self.source/'.env').write_text('fake secret')
        with self.assertRaises(ValueError):package_extension(self.source,self.root/'bad2.zip')
