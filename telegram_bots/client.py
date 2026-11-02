"""Минимальный Bot API без повторов отправки и без исключений с URL/токеном."""
import requests
from core.external_policy import require_live_operation


class TelegramError(Exception):
    def __init__(self, category, *, uncertain=False):
        self.category, self.uncertain = category, uncertain
        super().__init__('Telegram: ' + category)


class TelegramClient:
    METHODS = frozenset(['getMe', 'getWebhookInfo', 'getUpdates', 'sendMessage', 'sendDocument', 'answerCallbackQuery'])

    def __init__(self, token, session=None):
        require_live_operation('telegram_client')
        self._token = token
        self._session = session or requests.Session()

    def call(self, method, data=None, *, files=None):
        require_live_operation('telegram_api')
        if method not in self.METHODS:
            raise ValueError('Недопустимый метод Telegram')
        sending = method == 'sendDocument'
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

    def close(self):
        self._session.close()
