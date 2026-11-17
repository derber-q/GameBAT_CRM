"""Два подтверждения общей корзины; только на изолированной тестовой SQLite."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from django.db import close_old_connections, connections
from django.test import TransactionTestCase
from digital_sales.services import move_balance
from .test_checkout import ShopFixture
from .models import BalanceHold
from .access import Access
from . import services


class ReservationConcurrencyTests(ShopFixture, TransactionTestCase):

    def test_two_members_confirm_one_shared_cart_only_once(self):
        move_balance(actor=self.user, buyer_id=self.buyer.pk, amount='-400', kind='adjustment', reason='Синтетический долг')
        cart = self.prepared(11)
        def submit(user_id):
            close_old_connections()
            try:
                return services.confirm(Access(cart.chat_id, cart.buyer_id, user_id), cart.pk, cart.revision).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(submit, [11, 22]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(BalanceHold.objects.count(), 1)
        self.assertEqual(services.available_balance(self.buyer), Decimal('-220'))
