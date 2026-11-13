"""Минимальный Bot API без повторов отправки и без исключений с URL/токеном."""
import json
from pathlib import Path
import requests
from django.conf import settings
from core.external_policy import require_live_operation


class TelegramError(Exception):
    def __init__(self, category, *, uncertain=False):
        self.category, self.uncertain = category, uncertain
        super().__init__('Telegram: ' + category)


class TelegramClient:
    METHODS = frozenset(['getMe', 'getWebhookInfo', 'getUpdates', 'sendMessage', 'sendDocument', 'sendPhoto', 'answerCallbackQuery', 'editMessageText', 'editMessageCaption', 'editMessageReplyMarkup', 'getFile', 'getChatMember', 'getChat', 'pinChatMessage', 'unpinChatMessage', 'deleteMessage'])

    def __init__(self, token, session=None):
        require_live_operation('telegram_client')
        self._token = token
        self._session = session or requests.Session()

    def call(self, method, data=None, *, files=None):
        require_live_operation('telegram_api')
        if method not in self.METHODS:
            raise ValueError('Недопустимый метод Telegram')
        sending = method in ('sendDocument', 'sendPhoto')
        try:
            response = self._session.post(f'https://api.telegram.org/bot{self._token}/{method}',
                json=data if files is None else None, data=data if files else None, files=files,
                timeout=(5, 65 if sending else 30 if method == 'getUpdates' else 12), allow_redirects=False)
            payload = response.json()
        except requests.Timeout:
            raise TelegramError('timeout', uncertain=sending) from None
        except (requests.RequestException, ValueError):
            raise TelegramError('network', uncertain=sending) from None
        if not isinstance(payload, dict) or not payload.get('ok'):
            if (method == 'unpinChatMessage' and isinstance(payload, dict) and payload.get('error_code') == 400
                    and any(reason in str(payload.get('description', '')).lower()
                            for reason in ('message to unpin not found', 'message is not pinned', 'message not found'))):
                return True  # Известного закрепа уже нет: повтор завершает то же действие.
            editing = method in ('editMessageText', 'editMessageCaption', 'editMessageReplyMarkup')
            if (editing and isinstance(payload, dict) and payload.get('error_code') == 400
                    and any(reason in str(payload.get('description', '')).lower()
                            for reason in ('message to edit not found', "message can't be edited"))):
                raise TelegramError('message_missing') from None
            if (editing and isinstance(payload, dict)
                    and payload.get('error_code') == 400 and 'message is not modified' in str(payload.get('description', '')).lower()):
                return {'message_id': data['message_id']}
            code = payload.get('error_code', response.status_code) if isinstance(payload, dict) else response.status_code
            category = {401: 'unauthorized', 403: 'forbidden', 409: 'conflict', 429: 'rate_limited'}.get(code, 'refused')
            raise TelegramError(category, uncertain=sending and (not isinstance(code, int) or code >= 500))
        if not 200 <= response.status_code < 300 or 'result' not in payload:
            raise TelegramError('invalid_response', uncertain=sending)
        return payload['result']

    def message(self, chat_id, text, reply_markup=None):
        data = {'chat_id': chat_id, 'text': text}
        if reply_markup:
            data['reply_markup'] = reply_markup
        return self.call('sendMessage', data)

    def document(self, chat_id, filename, content):
        return self.call('sendDocument', {'chat_id': chat_id},
            files={'document': (filename, content, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')})

    def menu_photo(self, chat_id, caption, reply_markup):
        """Отправляет баннер сразу с inline-кнопками одним запросом Telegram."""
        content = (Path(settings.BASE_DIR) / 'static/img/staff-bot-logo.png').read_bytes()
        return self.call('sendPhoto', {'chat_id': chat_id, 'caption': caption,
            'reply_markup': json.dumps(reply_markup)},
            files={'photo': ('resource-logo.png', content, 'image/png')})

    def photo(self, chat_id, filename, content, *, caption=''):
        if type(chat_id) is not int or chat_id <= 0 or not bytes(content).startswith(b'\x89PNG\r\n\x1a\n') or len(content) >= 10*1024*1024:
            raise ValueError('Требуется личный получатель и PNG допустимого размера')
        data = {'chat_id': chat_id}
        if caption:
            data['caption'] = caption
        return self.call('sendPhoto', data, files={'photo': (filename, content, 'image/png')})

    def image_document(self, chat_id, filename, content, *, caption=''):
        """Высокий PNG без ограничения размеров фотографии и без перекодирования."""
        if type(chat_id) is not int or chat_id <= 0 or not bytes(content).startswith(b'\x89PNG\r\n\x1a\n') or len(content) >= 50*1024*1024:
            raise ValueError('Требуется личный получатель и PNG допустимого размера')
        data = {'chat_id': chat_id}
        if caption:
            data['caption'] = caption
        return self.call('sendDocument', data, files={'document': (filename, content, 'image/png')})

    def close(self):
        self._session.close()
