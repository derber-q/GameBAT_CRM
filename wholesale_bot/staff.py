"""Управление приёмом заказов через существующую привязку сотрудников CRM."""
from django.core.exceptions import ValidationError, PermissionDenied
from telegram_bots.access import check_function_access
from telegram_bots.menu import WHOLESALE_CONTROL
from .models import BotConfig
from .services import set_service_state


def panel():
    config = BotConfig.objects.filter(pk=1).first()
    if not config or not config.enabled:
        return {'text': 'Оптовый бот не подключён. Проверьте настройки в CRM.'}
    enabled = config.accepting_orders
    return {'text': ('🟢 Оптовый бот принимает заказы.' if enabled else '⏸ Приём заказов оптовым ботом выключен.')
        + '\nПри смене режима уведомление получат все авторизованные покупатели.',
        'reply_markup': {'inline_keyboard': [[{
            'text': '⏸ Выключить приём заказов' if enabled else '▶️ Включить приём заказов',
            'callback_data': f'optservice:{config.service_revision}:{"pause" if enabled else "resume"}'}],
            [{'text': 'Обновить', 'callback_data': 'optservice:open'}]]}}


def handle(access, message, callback):
    data = callback.get('data', '') if callback else ''
    opening = data == WHOLESALE_CONTROL.code or (not callback and message.get('text') == WHOLESALE_CONTROL.title)
    if not opening and not (isinstance(data, str) and data.startswith('optservice:')):
        return None
    user = check_function_access(access, WHOLESALE_CONTROL.code)
    try:
        if data and not opening and data != 'optservice:open':
            parts = data.split(':')
            if len(parts) != 3 or parts[2] not in ('pause', 'resume') or not parts[1].isascii() or not parts[1].isdecimal():
                raise ValidationError('Откройте актуальную панель управления оптовым ботом.')
            set_service_state(actor=user, accepting=parts[2] == 'resume', revision=parts[1])
        return panel()
    except ValidationError as exc:
        reply = panel()
        reply['text'] = '; '.join(exc.messages) + '\n\n' + reply['text']
        return reply
    except PermissionDenied:
        return {'text': 'Недостаточно прав для управления оптовым ботом.'}
