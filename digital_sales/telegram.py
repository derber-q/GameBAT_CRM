"""Диалог сотрудников использует прежнюю привязку; черновик общий, не в Telegram."""
from datetime import timedelta
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from .models import DigitalOrder, Buyer, StaffConversation, RETAIL_LABEL
from .services import require, save_draft, select_buyer, confirm_order, _version, record_id, ignore_incoming_order
from telegram_bots.menu import DIGITAL


def card(order):
    if order.processing_stopped:
        text = f'⛔ Цифровой заказ №{order.pk} отменён.\nИсключён из обработки; повторные сообщения поставщика не возобновят оформление.'
        if order.sale_id:
            text += f'\n{order.sale.visible_id}'
        return {'text': text, 'reply_markup': {'inline_keyboard': []}}
    buyer = order.buyer
    text = (f'Цифровой заказ №{order.pk}: {order.get_state_display()}\n'
            f'Покупатель: {order.customer_display_name}\n'
            f'Цена: {order.price if order.price is not None else "не задана"} ₽\n'
            f'Себестоимость: {order.cost} ₽\n'
            + ('Оплата: банковская карта, без баланса\n' if order.is_retail else f'Баланс: {buyer.balance if buyer else "—"} ₽\n')
            + f'Прибыль: {order.price - order.cost if order.price is not None else "—"} ₽\n'
            f'Последнее изменение: {order.edited_by_id or "система"}\n'
            + ('\n'.join(f"• {row['name'][:120]} — {row['cost']} ₽" for row in order.items[:15]))
            )[:3900]
    if order.sale_id:
        text += f'\n{order.sale.visible_id}'
        text += f'\nВыдача: {order.sale.get_order_status_display()} · Оплата: {order.sale.get_payment_status_display()}'
    elif order.review_reason:
        text += f'\n\nТребуется проверка: {order.review_reason[:450]}\nПокупателя и цену можно заполнить заранее.'
    elif not order.checklist_received or not order.goods_received:
        text += '\n\nОжидается полный чек-лист или готовность товара. Покупателя и цену можно заполнить заранее.'
    buttons = [] if order.sale_id else [
        [{'text': 'Выбрать покупателя', 'callback_data': f'dg:{order.pk}:{order.revision}:buyers:0'}],
        [{'text': 'Указать цену продажи', 'callback_data': f'dg:{order.pk}:{order.revision}:price'}],
    ]
    if not order.sale_id:
        if order.is_retail:
            text += '\nПодтверждение сразу завершит продажу и отметит оплату картой.'
        elif order.buyer_id:
            text += '\nПодтверждение сразу завершит продажу и спишет оплату с баланса покупателя.'
        buttons.append([{'text': 'Создать продажу', 'callback_data': f'dg:{order.pk}:{order.revision}:confirm'}])
    buttons.append([{'text': 'Обновить', 'callback_data': f'dg:{order.pk}:{order.revision}:open'}])
    buttons.append([{'text': 'Отменить', 'callback_data': f'dg:{order.pk}:{order.revision}:ignore'}])
    return {'text': text[:3900], 'reply_markup': {'inline_keyboard': buttons}}


def handle(access, user, message, callback):
    data = callback.get('data', '') if callback else ''
    text = message.get('text', '')
    pending = StaffConversation.objects.filter(access=access, expires_at__gt=timezone.now()).first()
    if not callback and pending and text in ('/menu', '/start', '/help', '/cancel', 'Отмена', 'Цифровые продажи'):
        pending.delete()
        pending = None
        if text in ('/cancel', 'Отмена'):
            return {'text': 'Ввод отменён. Откройте «Цифровые продажи», чтобы продолжить оформление.'}
    opening = data == DIGITAL.code or (not callback and text == DIGITAL.title)
    relevant = opening or (isinstance(data, str) and data.startswith('dg:')) or (not callback and pending)
    if not relevant:
        return None
    try:
        user = require(user, 'digital_sales.telegram_digital_sales', 'digital_sales.create_digital_sales', 'sales.create_sale')
        if callback:
            StaffConversation.objects.filter(access=access).delete()
        if opening:
            orders = DigitalOrder.objects.filter(state__in=['ready', 'review', 'goods', 'checklist']).order_by('-pk')[:15]
            return {'text': 'Цифровые заказы. Общие данные хранятся в CRM.', 'reply_markup': {'inline_keyboard': [
                [{'text': f'№{row.pk} · {row.get_state_display()}', 'callback_data': f'dg:{row.pk}:{row.revision}:open'}]
                for row in orders]}}
        if pending and not callback:
            order = DigitalOrder.objects.select_for_update().get(pk=pending.order_id)
            if order.sale_id or order.processing_stopped or order.revision != pending.revision:
                pending.delete()
                reply = card(order)
                reply['text'] = 'Заказ уже изменён. Открыта актуальная карточка.\n\n' + reply['text']
                return reply
            if pending.field == 'price':
                order = save_draft(actor=user, order_id=order.pk, revision=pending.revision,
                                   buyer_id=order.buyer_id, price=text, is_retail=order.is_retail)
            elif pending.field == 'new_buyer':
                # Старый диалог после обновления не должен создавать покупателя.
                pending.delete()
                reply = card(order)
                reply['text'] = 'Создание покупателей через бота отключено. Выберите покупателя.\n\n' + reply['text']
                return reply
            pending.delete()
            return card(order)
        parts = data.split(':')
        if len(parts) not in (4, 5) or not parts[1].isdecimal() or not parts[2].isdecimal():
            raise ValidationError('Откройте актуальную карточку заказа.')
        order = DigitalOrder.objects.select_for_update().get(pk=record_id(parts[1]))
        action = parts[3]
        if action == 'open':
            return card(order)
        if order.processing_stopped:
            return card(order)
        if action == 'ignore':
            if order.sale_id:
                require(user, 'digital_sales.cancel_digital_sales', 'sales.cancel_sale')
                _version(order, parts[2])
                return {'text': f'Отменить продажу {order.sale.visible_id}?\n'
                    'Она будет исключена из действующих продаж. Проведённые списания цифровых балансов будут возвращены штатным сторно.\n'
                    'Новые сообщения поставщика не возобновят оформление. Отмена в CRM не означает возврат денег самим поставщиком.',
                    'reply_markup': {'inline_keyboard': [
                        [{'text': 'Подтвердить отмену продажи', 'callback_data': f'dg:{order.pk}:{order.revision}:cancel_sale'}],
                        [{'text': 'Назад', 'callback_data': f'dg:{order.pk}:{order.revision}:open'}]]}}
            order = ignore_incoming_order(actor=user, order_id=order.pk, revision=parts[2])
            return card(order)
        if action == 'cancel_sale':
            require(user, 'digital_sales.cancel_digital_sales', 'sales.cancel_sale')
            _version(order, parts[2])
            if not order.sale_id:
                raise ValidationError('Продажа ещё не создана. Используйте отмену входящего заказа.')
            from sales.services import cancel_sale
            cancel_sale(actor=user, sale_id=order.sale_id, comment='Отмена цифровой продажи подтверждена в CRM-боте')
            order.refresh_from_db()
            return card(order)
        _version(order, parts[2])
        if order.sale_id:
            return card(order)
        if action == 'buyers':
            offset = int(parts[4]) if len(parts) == 5 and parts[4].isdecimal() else 0
            if offset > 1_000_000:
                raise ValidationError('Откройте список покупателей заново.')
            buyers = list(Buyer.objects.order_by('name', 'pk')[offset:offset + 20])
            buttons = [[{'text': RETAIL_LABEL, 'callback_data': f'dg:{order.pk}:{order.revision}:retail'}]]
            buttons += [[{'text': row.name[:60], 'callback_data': f'dg:{order.pk}:{order.revision}:buyer:{row.pk}'}] for row in buyers]
            if len(buyers) == 20:
                buttons.append([{'text': 'Следующие', 'callback_data': f'dg:{order.pk}:{order.revision}:buyers:{offset + 20}'}])
            return {'text': 'Выберите цифрового покупателя:', 'reply_markup': {'inline_keyboard': buttons}}
        if action == 'retail' or (action == 'buyer' and len(parts) == 5 and parts[4].isdecimal()):
            order = select_buyer(actor=user, order_id=order.pk, revision=parts[2],
                                 is_retail=action == 'retail',
                                 buyer_id=record_id(parts[4]) if action == 'buyer' else None)
            StaffConversation.objects.filter(access=access).delete()
            return card(order)
        if action == 'newbuyer':
            raise ValidationError('Создание покупателей через бота отключено. Выберите покупателя из базы или розничного покупателя.')
        if action == 'price':
            StaffConversation.objects.update_or_create(access=access, defaults={'order': order,
                'revision': order.revision, 'field': 'price',
                'expires_at': timezone.now() + timedelta(minutes=10)})
            return {'text': 'Пришлите общую окончательную цену в рублях (до копейки).'}
        if action == 'confirm':
            confirm_order(actor=user, order_id=order.pk, revision=parts[2], complete_immediately=True)
            order.refresh_from_db()
            return card(order)
        raise ValidationError('Неизвестное действие цифрового заказа.')
    except ValidationError as exc:
        if 'order' in locals():
            order.refresh_from_db()
            reply = card(order)
            reply['text'] = '; '.join(exc.messages) + '\n\n' + reply['text']
            return reply
        return {'text': '; '.join(exc.messages)}
    except PermissionDenied as exc:
        return {'text': '; '.join(getattr(exc, 'messages', [])) or 'Доступ закрыт. Проверьте актуальные права в CRM.'}
    except (DigitalOrder.DoesNotExist, Buyer.DoesNotExist, ValueError):
        return {'text': 'Заказ или покупатель не найден. Откройте актуальную карточку.'}
