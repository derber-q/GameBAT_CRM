"""Read-only сверка схемы работающего production перед подготовкой обновления."""
import os


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','GameBAT_CRM.settings')
    import django
    django.setup()
    from django.conf import settings
    from django.db import connection
    from django.db.migrations.loader import MigrationLoader
    if settings.GAMEBAT_ENV!='production' or connection.vendor!='postgresql':
        raise SystemExit('Нужна проверенная production PostgreSQL.')
    loader=MigrationLoader(connection)
    loader.check_consistent_history(connection)
    if set(loader.disk_migrations)!=set(loader.applied_migrations):
        raise SystemExit('Фактическая схема не совпадает с кодом. Установка обновления запрещена.')


if __name__=='__main__':main()
