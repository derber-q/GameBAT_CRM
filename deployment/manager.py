"""Операция существует только после ручного POST. Idle никогда не обращается к GitHub."""
from .store import UpdateError, now, sha


class Manager:
    def __init__(self, store, github, backend):
        self.store, self.github, self.backend = store, github, backend

    def tick(self):
        self.store.set('heartbeat', {'at': now(), 'protocol': 1})
        if self.store.get('recovery_required'):
            return
        operation = self.store.queued()
        if operation is None:
            return
        self.run(operation)

    def run(self, operation):
        current = self.store.get('current', {})
        stopped = False
        backup = {}
        try:
            self.store.stage(operation, 'checking', 'Проверка запроса и версии.')
            sha(current.get('sha'))
            if operation['action'] == 'check':
                latest = self.github.latest(current)
                self.store.set('latest', latest)
                self.store.stage(operation, 'done', 'Проверка завершена. Установка не выполнялась.', finished=True)
                return
            key = {'install': 'latest', 'rollback': 'rollback'}.get(operation['action'])
            if key is None:
                raise UpdateError('Операция запрещена.')
            candidate = self.store.get(key, {})
            if not candidate.get('approved') or candidate.get('sha') != sha(operation['target']):
                raise UpdateError('Установка непроверенной или подменённой версии запрещена.')
            if candidate['sha'] == current['sha']:
                raise UpdateError('Эта версия уже установлена.')
            if operation['action'] == 'install':
                self.github.verify(candidate)
            self.store.stage(operation, 'preparing', 'Подготовка отдельной версии программы.')
            release = self.backend.prepare(candidate, current, rollback=operation['action']=='rollback')
            self.store.stage(operation, 'validating', 'Изолированные проверки кандидата.')
            self.backend.preflight(release)
            self.store.stage(operation, 'stopping', 'Остановка пишущих процессов перед резервированием.',
                             result={'source': current['sha'], 'target': release['sha']})
            stopped = True
            self.backend.stop()
            self.store.stage(operation, 'backup', 'Согласованное резервирование PostgreSQL, файлов и ключей.')
            backup = self.backend.backup(operation['id'])
            if backup.get('verified') is not True:
                raise UpdateError('Резервная копия не подтверждена.')
            self.store.stage(operation, 'switching', 'Переключение на подготовленный образ.', result={'backup': backup})
            self.backend.activate(release)
            self.store.stage(operation, 'health', 'Проверка версии, БД и обработчиков после запуска.')
            self.backend.health(release)
            release.update(installed_at=now(), approved=True)
            self.store.set('current', release)
            self.store.set('rollback', {**current, 'approved': True})
            self.store.stage(operation, 'done', 'Версия установлена, работа подтверждена.', finished=True,
                             result={'source': current['sha'], 'target': release['sha'], 'backup': backup})
        except Exception as error:
            message = str(error) if isinstance(error, UpdateError) else 'Операция остановлена из-за внутренней ошибки. Проверьте состояние сервера.'
            recovered = False
            if stopped:
                self.store.stage(operation, 'restoring', 'Возврат прежнего образа без восстановления старой БД.')
                try:
                    self.backend.activate(current)
                    self.backend.health(current)
                    self.store.set('current', current)
                    recovered = True
                except Exception:
                    self.store.set('recovery_required', {'operation': operation['id'], 'at': now()})
                    message += ' Восстановление запуска не подтверждено; требуется проверка сервера.'
            self.store.stage(operation, 'error', message, finished=True,
                             result={'source': current.get('sha'), 'target': operation['target'],
                                     'backup': backup, 'recovered': recovered})
