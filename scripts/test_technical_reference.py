"""Справочник маршрутов одинаков для локального DEBUG и CI."""
from django.http import HttpResponse
from django.test import SimpleTestCase, override_settings
from django.urls import path, re_path
from django.views.static import serve

from scripts.build_technical_reference import routes_reference


def example_page(request):
    return HttpResponse('example')


urlpatterns = [
    path('example/', example_page, name='example'),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': '/unused'}, name='development-static'),
]


@override_settings(ROOT_URLCONF=__name__)
class TechnicalReferenceTests(SimpleTestCase):
    def test_development_static_is_excluded_without_hiding_application_routes(self):
        outputs = []
        for debug in (True, False):
            with self.settings(DEBUG=debug):
                text = routes_reference()
            self.assertIn('`/example/`', text)
            self.assertNotIn('development-static', text)
            self.assertIn('Записей URL: **1**', text)
            outputs.append(text)
        self.assertEqual(*outputs)
