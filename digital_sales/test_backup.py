"""Полный архив проверяется восстановлением отдельной синтетической SQLite."""
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase
from catalog.models import SystemProduct
from crm_backups.configuration import columns
from crm_backups.snapshot import create_bundle, restore_bundle
from crm_backups.crypto import generate_keys
from .models import Supplier, Buyer
from .services import manual_sale, move_balance, complete_sale


class DigitalRestoreTests(TransactionTestCase):
    def test_separate_database_restores_balances_sale_and_encrypted_goods(self):
        key = Fernet.generate_key()
        with TemporaryDirectory() as folder, patch('digital_sales.crypto.cipher', return_value=Fernet(key)):
            root = Path(folder)
            media = root / 'media'
            media.mkdir()
            SystemProduct.objects.get_or_create(kind='DIGITAL_PRODUCT')
            user = get_user_model().objects.create_superuser(username='digital-restore')
            supplier = Supplier.objects.create(name='Restore Supplier')
            buyer = Buyer.objects.create(name='Restore Buyer')
            move_balance(actor=user, buyer_id=buyer.pk, amount=1000, kind='opening', reason='Synthetic')
            sale = manual_sale(actor=user, supplier_id=supplier.pk, buyer_id=buyer.pk,
                items=[{'name': 'Synthetic Backup', 'cost': '200'}], price=300,
                creation_key=uuid.uuid4(), secret='SYNTHETIC-RESTORE-SECRET')
            complete_sale(actor=user, sale_id=sale.pk)
            database = root / 'artificial.sqlite3'
            with closing(sqlite3.connect(database)) as copied:
                connection.connection.backup(copied)
            file_columns, encrypted_columns = columns()
            self.assertIn(('digital_sales_suppliermessage', 'encrypted_payload', 'DIGITAL_SALES_KEY'), encrypted_columns)
            private, public = generate_keys(b'synthetic-recovery-password')
            archive = root / 'digital.backup'
            create_bundle(database=database, media=media,
                secrets_loader=lambda: {'DIGITAL_SALES_KEY': key.decode()}, metadata={'environment': 'synthetic'},
                public_key=public, destination=archive, file_columns=file_columns, encrypted_columns=encrypted_columns)
            restored = root / 'restored'
            restore_bundle(archive, restored, private, b'synthetic-recovery-password')
            # Проверяем именно восстановленный файл, а не исходное соединение Django.
            with closing(sqlite3.connect(restored / 'database.sqlite3')) as copied:
                encrypted = copied.execute('SELECT encrypted_payload FROM digital_sales_suppliermessage').fetchone()[0]
                self.assertEqual(json.loads(Fernet(key).decrypt(encrypted.encode()))['text'], 'SYNTHETIC-RESTORE-SECRET')
                self.assertEqual(copied.execute('SELECT SUM(delta) FROM digital_sales_balancemovement WHERE buyer_id=?', [buyer.pk]).fetchone()[0], 700)
                self.assertEqual(copied.execute('SELECT payment_status FROM sales_sale WHERE id=?', [sale.pk]).fetchone()[0], 'paid')
