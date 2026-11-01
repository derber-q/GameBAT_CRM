"""Режим для HTML задаётся сервером и не читается из GET/cookie/JavaScript."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import JsonResponse


def environment(request):
    return {'gamebat_environment':settings.GAMEBAT_ENV, 'is_local_test':settings.GAMEBAT_ENV == 'local_test'}


class TestEnvironmentMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Только тестовая конфигурация подключает этот middleware.
        response['X-GameBAT-Environment'] = 'local_test'
        response['Content-Security-Policy'] = (
            "default-src 'self'; connect-src 'self'; img-src 'self' data: blob:; "
            "media-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "font-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        return response

    def process_exception(self, request, exception):
        if isinstance(exception, ValidationError) and getattr(exception, 'code', None) == 'test_environment_blocked':
            return JsonResponse({'error': ' '.join(exception.messages), 'environment':'local_test'}, status=403)
