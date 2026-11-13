"""Ограниченное скачивание XLSX: только file_path официального API, без редиректов."""
import re
import requests
from core.external_policy import require_live_operation
from telegram_bots.client import TelegramClient, TelegramError
from .documents import MAX_FILE


class WholesaleClient(TelegramClient):
    def download(self, file_id):
        require_live_operation('wholesale_file_download')
        metadata = self.call('getFile', {'file_id': file_id})
        path = metadata.get('file_path', '') if isinstance(metadata, dict) else ''
        size = metadata.get('file_size', 0) if isinstance(metadata, dict) else 0
        if (not isinstance(path, str) or not re.fullmatch(r'[A-Za-z0-9_/.-]{1,500}', path)
                or '..' in path or path.startswith('/') or type(size) is not int or not 0 <= size <= MAX_FILE):
            raise TelegramError('file_size_or_path')
        try:
            with self._session.get(f'https://api.telegram.org/file/bot{self._token}/{path}',
                    stream=True, timeout=(5, 30), allow_redirects=False) as response:
                if response.status_code != 200:
                    raise TelegramError('download_refused')
                content = bytearray()
                for chunk in response.iter_content(65536):
                    content.extend(chunk)
                    if len(content) > MAX_FILE:
                        raise TelegramError('file_too_large')
                return bytes(content)
        except requests.RequestException:
            raise TelegramError('download_network') from None
