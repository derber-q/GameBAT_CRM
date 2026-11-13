from django.db import OperationalError, ProgrammingError


def queue_snapshot():
    from .models import BotConfig, Event, Delivery
    result = {'next_action': 'Ожидание оптовых заявок Telegram', 'task_error': ''}
    try:
        bot = BotConfig.objects.filter(pk=1).first()
        result['last_task_success_at'] = bot.last_success_at if bot else None
        if Event.objects.filter(state='pending').exists():
            result['next_action'] = 'Проверка входящего заказа'
        elif Delivery.objects.filter(state='pending').exists():
            result['next_action'] = 'Доставка прайса или накладной'
        if (bot and bot.error_category or Event.objects.filter(state='error').exists()
                or Delivery.objects.filter(state__in=['error', 'uncertain']).exists()):
            result['task_error'] = 'Есть ошибка оптового бота. Проверьте Telegram-покупателей в Прайсы / Наличие.'
    except (OperationalError, ProgrammingError):
        result['task_error'] = 'Оптовые таблицы ещё не установлены.'
    return result
