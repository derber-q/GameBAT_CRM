"""CI не допускает образ к установке, пока production действительно не реализован."""
import os


def main():
    os.environ.update(GAMEBAT_ENV='production',DJANGO_SETTINGS_MODULE='GameBAT_CRM.settings',DJANGO_DEBUG='0',
        DJANGO_SECRET_KEY='ci-production-validation-only-not-real-'+'x'*64,
        INTEGRATION_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
        RESOURCE_TOKEN_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
        DATABASE_URL='postgresql://resource_ci:ci-only@127.0.0.1:5432/resource_ci',
        GAMEBAT_MEDIA_ROOT='/tmp/resource-ci-production-media',DJANGO_ALLOWED_HOSTS='ci.example.invalid')
    import django
    django.setup()
    from django.conf import settings
    if settings.GAMEBAT_ENV!='production' or settings.DEBUG or settings.DATABASES['default']['ENGINE']!='django.db.backends.postgresql':
        raise SystemExit('Production/PostgreSQL ещё не готовы. Публикация допуска установки запрещена.')
    from django.core.management import call_command
    call_command('check',deploy=True,fail_level='WARNING')


if __name__=='__main__':main()
