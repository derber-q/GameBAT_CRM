"""Предварительные проверки в контейнере без сети, данных CRM и рабочих ключей."""
import os


def main():
    if not os.path.isfile('/.dockerenv'):
        raise SystemExit('Кандидат проверяется только в изолированном контейнере.')
    # Публичные искусственные значения; реальные секреты сюда не передаются.
    os.environ.update(GAMEBAT_ENV='local_live', DJANGO_SECRET_KEY='candidate-only-not-a-production-secret',
        INTEGRATION_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
        RESOURCE_TOKEN_ENCRYPTION_KEY='MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=',
        DJANGO_SETTINGS_MODULE='deployment.candidate_settings')
    import django
    django.setup()
    from django.core.management import call_command
    call_command('check')
    call_command('makemigrations',check=True,dry_run=True,interactive=False)


if __name__=='__main__':
    main()
