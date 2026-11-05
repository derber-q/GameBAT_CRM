"""Исторические минимумы переходят в РФ без изменения сумм, дат и авторов."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ManualPriceMigrationTests(TransactionTestCase):
    before=[('integrations','0010_alter_workercommand_service_alter_workerservice_code')]
    after=[('integrations','0011_avito_manual_price_scopes')]

    def test_existing_minima_are_russia_and_rostov_stays_empty(self):
        from accounts.models import User
        from catalog.models import CD,Platform
        from integrations.models import AvitoProductProfile
        # Остальные приложения остаются на актуальной схеме; откатываем только integrations.
        user=User.objects.create(username='legacy-manual-price')
        platform=Platform.objects.create(name='Legacy PS5')
        cd=CD.objects.create(name='Legacy title',platform=platform)
        profile=AvitoProductProfile.objects.create(cd=cd)
        executor=MigrationExecutor(connection)
        executor.migrate(self.before)
        try:
            old=executor.loader.project_state(self.before).apps
            model=old.get_model('integrations','AvitoManualPrice')
            model.objects.create(profile_id=profile.pk,price='1234.56',recorded_at=timezone.now(),recorded_by_id=user.pk)
            fields=['id','profile_id','price','recorded_at','recorded_by_id']
            snapshot=list(model.objects.order_by('pk').values(*fields))
            executor=MigrationExecutor(connection)
            executor.migrate(self.after)
            new=executor.loader.project_state(self.after).apps.get_model('integrations','AvitoManualPrice')
            self.assertEqual(list(new.objects.order_by('pk').values(*fields)),snapshot)
            self.assertEqual(set(new.objects.values_list('scope',flat=True)),{'russia'})
            self.assertFalse(new.objects.filter(scope='rostov').exists())
            new.objects.create(profile_id=profile.pk,scope='rostov',price=1200,
                recorded_at=timezone.now(),recorded_by_id=user.pk)
            self.assertEqual(new.objects.filter(profile_id=profile.pk).count(),2)
        finally:
            MigrationExecutor(connection).migrate(self.after)
