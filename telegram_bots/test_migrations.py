"""Расширение очереди сохраняет прежние задания и привязки; только тестовая SQLite."""
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SupplierTemplateMigrationTests(TransactionTestCase):
    before = [('telegram_bots', '0001_initial')]
    after = [('telegram_bots', '0002_staffbotjobdocument_staffbotjob_function_and_more')]

    def test_existing_jobs_and_link_survive_with_wholesale_default(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        try:
            old = executor.loader.project_state(self.before).apps
            user = old.get_model('accounts', 'User').objects.create(username='legacy-bot-user')
            bot = old.get_model('telegram_bots', 'StaffBot').objects.create(code='staff', next_update_id=701)
            access = old.get_model('telegram_bots', 'StaffBotAccess').objects.create(
                bot=bot, user=user, allowed=True, telegram_user_id=123)
            Job = old.get_model('telegram_bots', 'StaffBotJob')
            for index, state in enumerate(['queued', 'done', 'error', 'uncertain'], 1):
                receipt = old.get_model('telegram_bots', 'StaffBotUpdate').objects.create(bot=bot, update_id=index)
                Job.objects.create(bot=bot, access=access, update=receipt, chat_id=123, state=state,
                    telegram_message_id=456 if state == 'done' else None)
            fields = ['id', 'bot_id', 'access_id', 'update_id', 'chat_id', 'warehouse_id',
                'state', 'telegram_message_id', 'created_at', 'started_at', 'finished_at', 'error_category']
            snapshot = list(Job.objects.order_by('created_at', 'pk').values(*fields))
            executor = MigrationExecutor(connection)
            executor.migrate(self.after)
            new = executor.loader.project_state(self.after).apps
            NewJob = new.get_model('telegram_bots', 'StaffBotJob')
            self.assertEqual(list(NewJob.objects.order_by('created_at', 'pk').values(*fields)), snapshot)
            self.assertEqual(set(NewJob.objects.values_list('function', flat=True)), {'wholesale_stock_price'})
            self.assertFalse(NewJob.objects.filter(supplier__isnull=False).exists())
            self.assertEqual(new.get_model('telegram_bots', 'StaffBotJobDocument').objects.count(), 0)
            self.assertEqual(new.get_model('telegram_bots', 'StaffBot').objects.get(pk=bot.pk).next_update_id, 701)
            self.assertEqual(new.get_model('telegram_bots', 'StaffBotAccess').objects.get(pk=access.pk).telegram_user_id, 123)
        finally:
            MigrationExecutor(connection).migrate(self.after)
