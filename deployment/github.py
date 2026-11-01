"""Только API фиксированного репозитория. Запускается менеджером по заявке, не web-view."""
import json
from pathlib import Path
import re
import ssl
import urllib.error
import urllib.request

from . import CI_CONTEXT, IMAGE, REPOSITORY
from .store import UpdateError, now, sha


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UpdateError('Перенаправление GitHub API запрещено.')


class GitHub:
    def __init__(self, token_file=None):
        self.token_file = token_file

    def read(self, path):
        if not re.fullmatch(r'(/commits/(main|[a-f0-9]{40})(/statuses)?|/compare/[a-f0-9]{40}\.\.\.[a-f0-9]{40})', path):
            raise UpdateError('Запрос к непредусмотренному источнику запрещён.')
        headers = {'Accept':'application/vnd.github+json', 'User-Agent':'ReSOURCE-Manual-Updater/1',
                   'X-GitHub-Api-Version':'2026-03-10'}
        if self.token_file:
            headers['Authorization'] = 'Bearer '+Path(self.token_file).read_text('utf-8').strip()
        request = urllib.request.Request('https://api.github.com/repos/'+REPOSITORY+path, headers=headers)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context()), NoRedirect())
        try:
            with opener.open(request, timeout=20) as response:
                data = response.read(1024*1024+1)
                if len(data)>1024*1024:
                    raise UpdateError('Слишком большой ответ GitHub.')
                return json.loads(data)
        except (OSError, ValueError, urllib.error.URLError):
            raise UpdateError('GitHub недоступен или ответ не распознан. Предыдущие сведения сохранены.') from None

    def artifact(self, commit):
        statuses = self.read('/commits/'+sha(commit)+'/statuses')
        if not isinstance(statuses, list):
            raise UpdateError('Неверный ответ проверки CI.')
        # Первый статус контекста — последний. Старый success не перекрывает новый failure.
        status = next((row for row in statuses if isinstance(row,dict) and row.get('context')==CI_CONTEXT), {})
        digest = status.get('description', '')
        if (status.get('state')!='success' or status.get('creator',{}).get('login')!='github-actions[bot]'
                or not isinstance(digest,str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', digest)):
            return ''
        return IMAGE+'@'+digest

    def latest(self, current):
        commit = self.read('/commits/main')
        value = sha(commit.get('sha'))
        image = self.artifact(value)
        changes = []
        previous = current.get('sha','')
        if re.fullmatch('[a-f0-9]{40}',previous) and previous!=value:
            comparison = self.read('/compare/'+previous+'...'+value)
            changes = [{'sha':sha(row['sha']),'summary':str(row.get('commit',{}).get('message','')).split('\n')[0][:200]}
                       for row in comparison.get('commits',[])[:30]]
        return {'sha':value, 'image':image, 'approved':bool(image), 'checked_at':now(),
                'changes':changes,'compare_from':previous if re.fullmatch('[a-f0-9]{40}',previous) else '',
                'summary':str(commit.get('commit',{}).get('message','')).split('\n')[0][:400],
                'reason':'' if image else 'Нет успешного resource/deployment с digest образа для этого коммита.'}

    def verify(self, candidate):
        if not candidate.get('image') or self.artifact(candidate['sha'])!=candidate['image']:
            raise UpdateError('Подтверждение CI или digest версии изменились. Повторите ручную проверку.')
