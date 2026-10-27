"""Каналы меняют видимость таблиц, сохраняя типы и исторические документы."""
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from warehouse.models import Warehouse
from .models import Sale


class SalesChannelsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('channels-admin')
        self.warehouse = Warehouse.objects.create(name='Каналы продаж')
        self.client.force_login(self.user)

    def sale(self, kind, completed=False):
        return Sale.objects.create(warehouse=self.warehouse, created_by=self.user, sale_type=kind,
            price_type='retail', payment_method='bank_transfer_postpay',
            order_status='delivered' if completed else 'created', payment_status='paid' if completed else 'unpaid')

    def test_order_empty_sections_and_consignment_for_both_pages(self):
        for completed, name in [(False, 'incomplete'), (True, 'completed')]:
            for kind in ('retail', 'avito', 'wholesale', 'yandex_market', 'consignment'):
                self.sale(kind, completed)
            response = self.client.get(reverse(f'sales:{name}'))
            expected = (['yandex_market', 'wholesale', 'avito', 'retail', 'consignment'] if completed else ['wholesale', 'avito', 'yandex_market', 'retail'])
            self.assertEqual([group['kind'] for group in response.context['groups']], expected)
            html = response.content.decode()
            labels = ['Все</button>', 'Яндекс Маркет</button>', 'Опт</button>', 'Авито</button>', 'Розница</button>']
            positions = [html.index(label) for label in labels]
            self.assertEqual(positions, sorted(positions))
            self.assertContains(response, 'data-sales-channel="all" aria-pressed="true"')
            self.assertContains(response, 'data-sales-channel="wholesale" aria-pressed="false"')
        self.assertEqual(Sale.objects.filter(sale_type='consignment').count(), 2)

    def test_empty_retail_and_other_tables_are_not_rendered(self):
        response = self.client.get(reverse('sales:incomplete'))
        self.assertEqual(response.context['groups'], [])
        self.assertNotContains(response, 'id="group-retail"')
        self.assertNotContains(response, 'id="group-consignment"')
        self.assertContains(response, 'data-sales-channel-empty')
        self.assertContains(response, 'data-sales-channel="retail"')

    def test_legacy_wholesale_kinds_share_channel_without_rewriting(self):
        records = [self.sale(kind) for kind in ('wholesale', 'wholesale_pickup', 'wholesale_delivery')]
        response = self.client.get(reverse('sales:incomplete'))
        self.assertEqual(len(response.context['groups']), 1)
        group = response.context['groups'][0]
        self.assertEqual(group['kind'], 'wholesale')
        self.assertEqual({row['sale'].pk for row in group['rows']}, {row.pk for row in records})
        self.assertTrue(all(row['is_wholesale'] for row in group['rows']))
        self.assertEqual(set(Sale.objects.values_list('sale_type', flat=True)), {'wholesale', 'wholesale_pickup', 'wholesale_delivery'})
