"""Диагностика приёма без раскрытия сообщений, цифровых данных и токена."""
from django.db import OperationalError, ProgrammingError
from .models import DigitalBot, SupplierMessage


def queue_snapshot():
    data = {'next_action': 'Ожидание событий цифрового поставщика', 'task_error': ''}
    try:
        bot = DigitalBot.objects.filter(pk=1).first()
        if bot:
            data['last_task_success_at'] = bot.last_success_at
            if bot.error_category:
                data['task_error'] = 'Ошибка приёма Telegram: ' + bot.error_category + '. Проверьте страницу цифрового бота.'
        if SupplierMessage.objects.filter(attachment_state='pending').exists():
            data['next_action'] = 'Сохранение защищённого вложения'
        if SupplierMessage.objects.filter(attachment_state='error').exists():
            data['task_error'] = 'Есть несохранённое вложение цифрового товара; требуется проверка.'
    except (OperationalError, ProgrammingError):
        data['task_error'] = 'Цифровые таблицы ещё не установлены.'
    return data
