"""Безопасный снимок для штатной страницы обработчиков, без Telegram ID и HTTP-вызовов."""
from django.db import OperationalError, ProgrammingError
from django.db.models import Max
from .models import StaffBot, StaffBotJob


ERROR_LABELS = {
    'unauthorized': 'Telegram отклонил токен. Проверки повторяются автоматически; проверьте сам токен.',
    'wrong_bot': 'Токен относится к другому боту. После исправления username/токена подключение восстановится автоматически.',
    'webhook': 'У бота настроен webhook. Проверки продолжаются; после отключения другого получателя бот подключится сам.',
    'conflict': 'Обнаружен другой получатель обновлений. После его остановки бот подключится автоматически.',
    'timeout': 'Telegram не ответил вовремя.', 'network': 'Соединение с Telegram недоступно.',
    'rate_limited': 'Telegram ограничил частоту запросов.',
    'executor': 'Исполнитель документов остановился. Контроллер восстанавливает работу.',
    'refused': 'Telegram временно отклонил запрос. Бот повторяет проверку связи автоматически.',
    'invalid_response': 'Ответ Telegram не удалось проверить. Бот автоматически повторяет запрос.',
}


def queue_snapshot():
    data = {'next_action': 'Ожидание запроса сотрудника', 'task_error': ''}
    try:
        bot = StaffBot.objects.filter(code='staff').first()
        if not bot:
            return data
        data['last_task_success_at'] = StaffBotJob.objects.filter(bot=bot, state='done').aggregate(at=Max('finished_at'))['at']
        data['task_error'] = ERROR_LABELS.get(bot.error_category, 'Ошибка Telegram. Проверьте настройки.' if bot.error_category else '')
        if bot.error_category in ('timeout', 'network', 'rate_limited', 'refused', 'invalid_response'):
            data['next_action'] = 'Восстановление связи с Telegram'
        job = StaffBotJob.objects.filter(bot=bot, state__in=['queued', 'generating', 'sending']).first()
        if job:
            data['next_action'] = ('Формирование PNG-прайсов GameBAT' if job.function == 'digital_price_images' else 'Формирование шаблонов поставщика' if job.function == 'supplier_price_templates'
                else 'Формирование оптового прайса') if job.state == 'queued' else job.get_state_display()
            data['next_at'] = job.created_at
            if job.state != 'queued':
                data['current_action'], data['current_started_at'] = job.get_state_display(), job.started_at
        if StaffBotJob.objects.filter(bot=bot, state__in=['error', 'uncertain', 'partial']).exists():
            data['task_error'] = data['task_error'] or 'Есть ошибки или неизвестные результаты отправки. Проверьте журнал Telegram-бота.'
    except (OperationalError, ProgrammingError):
        pass
    return data
