"""Безопасный снимок для штатной страницы обработчиков, без Telegram ID и HTTP-вызовов."""
from django.db import OperationalError, ProgrammingError
from django.db.models import Max
from .models import StaffBot, StaffBotJob


ERROR_LABELS = {
    'unauthorized': 'Telegram отклонил токен. Проверьте настройки и выключите/включите бота.',
    'wrong_bot': 'Токен относится к другому боту. Проверьте username.',
    'webhook': 'У бота настроен webhook. Сначала согласуйте отключение старого получателя.',
    'conflict': 'Обнаружен другой получатель обновлений. Остановите его перед включением этого.',
    'timeout': 'Telegram не ответил вовремя.', 'network': 'Соединение с Telegram недоступно.',
    'rate_limited': 'Telegram ограничил частоту запросов.',
    'executor': 'Исполнитель документов остановился. Выключите и включите бота.',
}


def queue_snapshot():
    data = {'next_action': 'Ожидание запроса сотрудника', 'task_error': ''}
    try:
        bot = StaffBot.objects.filter(code='staff').first()
        if not bot:
            return data
        data['last_task_success_at'] = StaffBotJob.objects.filter(bot=bot, state='done').aggregate(at=Max('finished_at'))['at']
        data['task_error'] = ERROR_LABELS.get(bot.error_category, 'Ошибка Telegram. Проверьте настройки.' if bot.error_category else '')
        job = StaffBotJob.objects.filter(bot=bot, state__in=['queued', 'generating', 'sending']).first()
        if job:
            data['next_action'] = 'Формирование оптового прайса' if job.state == 'queued' else job.get_state_display()
            data['next_at'] = job.created_at
            if job.state != 'queued':
                data['current_action'], data['current_started_at'] = job.get_state_display(), job.started_at
        if StaffBotJob.objects.filter(bot=bot, state__in=['error', 'uncertain']).exists():
            data['task_error'] = data['task_error'] or 'Есть ошибки или неизвестные результаты отправки. Проверьте журнал Telegram-бота.'
    except (OperationalError, ProgrammingError):
        pass
    return data
