"""Ключевой допуск: полная копия настоящей схемы CRM, отдельное восстановление
и штатная диагностика склада/кассы. Только искусственные записи и ключи.
"""
from contextlib import closing
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import connection
from django.test import TransactionTestCase,override_settings
from cryptography.fernet import Fernet
from accounts.models import User
from catalog.models import CD,Platform
from warehouse.models import Warehouse,CDWarehouseStock
from sales.models import Sale
from sales.services import create_sale,mark_sale_paid
from integrations.models import IntegrationCredential
from .configuration import columns
from .crypto import generate_keys
from .snapshot import create_bundle,restore_bundle,digest


class CRMRestoreBusinessTests(TransactionTestCase):
    def test_restore_real_crm_sales_inventory_cash_users_media_and_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);media=root/'media';media.mkdir()
            key=Fernet.generate_key().decode()
            with override_settings(MEDIA_ROOT=media,INTEGRATION_ENCRYPTION_KEY=key):
                actor=User.objects.create_superuser('restored-synthetic-owner',password='Synthetic-only-strong-password')
                actor.verification_document.save('synthetic-document.png',ContentFile(b'artificial protected document'))
                warehouse=Warehouse.objects.create(name='Synthetic restore warehouse')
                product=CD.objects.create(platform=Platform.objects.create(name='Restore PS5'),name='Synthetic restore game',
                    sku='RESTORE-ONLY',avito_price=100,cost=20)
                stock=CDWarehouseStock.objects.create(warehouse=warehouse,cd=product,quantity=10)
                from .models import ApplicationArtifact
                import hashlib
                programs=root/'programs';programs.mkdir()
                binary=b'artificial installer bytes'
                artifact=ApplicationArtifact.objects.create(kind='local_agent',version='1.0.0',size=len(binary),
                    sha256=hashlib.sha256(binary).hexdigest(),published_by=actor)
                (programs/(str(artifact.pk)+'.zip')).write_bytes(binary)
                sale=create_sale(actor=actor,warehouse_id=warehouse.pk,price_type=Sale.PriceType.RETAIL,
                    sale_type=Sale.SaleType.RETAIL,payment_method=Sale.PaymentMethod.CASH_POSTPAY,
                    lines=[{'product_type':'cd','product_id':product.pk,'quantity':2}])
                mark_sale_paid(actor=actor,sale_id=sale.pk,cash_received_amount=200)
                IntegrationCredential.objects.create(provider='avito',encrypted_client_id=Fernet(key).encrypt(b'fake-client-id').decode(),
                    encrypted_client_secret=Fernet(key).encrypt(b'fake-client-secret').decode())
                # Копируется только test connection. Даже при memory test DB рабочая
                # SQLite не открывается; промежуточная БД становится отдельной WAL.
                database=root/'artificial.sqlite3'
                with closing(sqlite3.connect(database)) as copied:connection.connection.backup(copied)
                with closing(sqlite3.connect(database)) as wal:wal.execute('PRAGMA journal_mode=WAL')
                before=digest(database)
                files,encrypted=columns()
                private,public=generate_keys(b'owner-test-recovery-password')
                archive=root/'full.backup'
                create_bundle(database=database,media=media,secrets_loader=lambda:{
                    'SECRET_KEY':'synthetic-secret-key','INTEGRATION_ENCRYPTION_KEY':key,
                    'RESOURCE_TOKEN_ENCRYPTION_KEY':settings.RESOURCE_TOKEN_ENCRYPTION_KEY},
                    metadata={'environment':'artificial','dirty':True},public_key=public,destination=archive,
                    file_columns=files,encrypted_columns=encrypted,extra_roots={'client_applications':programs})
                destination=root/'restored'
                manifest=restore_bundle(archive,destination,private,b'owner-test-recovery-password')
                self.assertEqual(digest(database),before)
                # Отдельный процесс не получает рабочие ключи, БД или HTTP-worker.
                code='''
import django,io,json
from django.conf import settings
settings.DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DB_PATH}}
settings.MEDIA_ROOT=MEDIA_PATH
django.setup()
from django.core.management import call_command
from accounts.models import User
from catalog.models import CD
from sales.models import Sale
from warehouse.models import CDWarehouseStock,Warehouse
from cash.models import CashTransaction
assert User.objects.get(username='restored-synthetic-owner').check_password('Synthetic-only-strong-password')
assert CDWarehouseStock.objects.get(cd__sku='RESTORE-ONLY').quantity==8
assert Warehouse.objects.get(name='Synthetic restore warehouse').cash_register.balance==200
assert CashTransaction.objects.filter(operation_type='sale_payment').count()==1
assert Sale.objects.get(pk=SALE_ID).payment_status=='paid'
output=io.StringIO()
call_command('verify_inventory',stdout=output)
call_command('verify_cash',stdout=output)
call_command('migrate',check=True,stdout=output)
print(output.getvalue())
'''
                code='DB_PATH='+repr(str(destination/'database.sqlite3'))+'\nMEDIA_PATH='+repr(str(destination/'protected_media'))+'\nSALE_ID='+str(sale.pk)+'\n'+code
                result=subprocess.run([sys.executable,'-Xutf8','-c',code],cwd=settings.BASE_DIR,
                    env={**os.environ,'DJANGO_SETTINGS_MODULE':'deployment.ci_sqlite_settings'},capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                offline=subprocess.run([sys.executable,'-Xutf8','scripts/verify_restored_backup.py',str(destination)],
                    cwd=settings.BASE_DIR,capture_output=True,text=True,encoding='utf-8',timeout=60)
                self.assertEqual(offline.returncode,0,offline.stdout+offline.stderr)
                self.assertTrue(manifest['migrations'])
                output=Path(settings.BASE_DIR)/'outputs/local_agent_20261103'
                output.mkdir(parents=True,exist_ok=True)
                (output/'restore_business.json').write_text(json.dumps({'ok':True,'artificial_data_only':True,
                    'stock_after_sale':8,'cash_after_sale':'200.00','password_verified':True,
                    'media_verified':True,'encrypted_credentials_verified':True,
                    'verify_inventory':'ok','verify_cash':'ok','migrations_check':'ok',
                    'source_database_unchanged':True,'restored_file_count':len(manifest['files'])},indent=2),encoding='utf-8')
