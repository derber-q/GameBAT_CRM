"""Воспроизводимый справочник кода CRM без выгрузки записей рабочей БД.

Читает AST, URLResolver и метаданные моделей. Не запускает worker, API,
команды переноса данных или миграции. --check ничего не записывает.
"""
from __future__ import annotations

import argparse
import ast
import inspect
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / 'docs' / 'technical' / 'reference'
APPS = {'core', 'accounts', 'catalog', 'partners', 'warehouse', 'supplies', 'consignment',
        'pricing', 'sales', 'cash', 'creditors', 'price', 'orders', 'integrations',
        'yandex_market', 'resource_storefront'}
NOTICE = ('<!-- Сгенерировано scripts/build_technical_reference.py; не редактировать вручную. -->\n'
          '\nСправочник исходников и метаданных схемы, без рабочих записей/ключей. '
          'Перегенерация: `.venv/Scripts/python.exe scripts/build_technical_reference.py`.\n\n')


def paths():
    tracked = subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT)
    return sorted({p for p in tracked.decode('utf-8').split('\0') if p and (ROOT / p).is_file()})


def production(path):
    p = Path(path)
    return (p.suffix == '.py' and p.parts[0] in APPS and 'migrations' not in p.parts
            and not p.name.startswith('test') and 'browser' not in p.name
            and not p.name.endswith(('_test_helpers.py', '_settings.py')))


def clean(text):
    return str(text).replace('|', '\\|').replace('\n', ' ')


def functions(node, prefix=''):
    for child in node.body:
        if isinstance(child, ast.ClassDef):
            yield from functions(child, prefix + child.name + '.')
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield prefix + child.name, child


def python_reference(files):
    result = ['# Python-модули, функции и методы\n\n', NOTICE,
              'Вложенные функции, миграции и тесты не включены в этот индекс; '
              'их отдельная карта находится ниже в справочнике UI/проверок. '
              'Декораторы, docstring и вызываемые символы описывают контракт/зависимости, '
              'но не заменяют чтение тела перед изменением.\n\n']
    count = 0
    for path in filter(production, files):
        text = (ROOT / path).read_text(encoding='utf-8-sig')
        tree = ast.parse(text)
        if not tree.body:
            continue
        result.extend([f'## `{path}`\n\n', (ast.get_docstring(tree) or 'Назначение уточнять по экспортируемым символам.') + '\n\n'])
        imports = sorted({n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module})
        if imports:
            result.append('Импорты: ' + ', '.join('`' + i + '`' for i in imports) + '.\n\n')
        for name, node in functions(tree):
            count += 1
            result.extend([f'### `{name}({ast.unparse(node.args)})`\n\n', f'Исходник: `{path}:{node.lineno}`.\n\n'])
            if node.decorator_list:
                result.append('Декораторы: ' + '; '.join('`' + ast.unparse(d) + '`' for d in node.decorator_list) + '.\n\n')
            result.append((ast.get_docstring(node) or 'Подробности реализации — в исходнике; бизнес-сценарий определяет модуль и вызывающий сервис.') + '\n\n')
            calls = sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)})
            if calls:
                result.append('Статические вызовы: ' + ', '.join('`' + c + '`' for c in calls) + '.\n\n')
    result.insert(2, f'Функций/методов: **{count}**.\n\n')
    return ''.join(result)


def unwrap(callback):
    seen = set()
    while callable(callback) and id(callback) not in seen:
        seen.add(id(callback))
        if hasattr(callback, '__wrapped__'):
            callback = callback.__wrapped__
        elif inspect.isfunction(callback) and '<locals>' in callback.__qualname__:
            candidates = [v for v in inspect.getclosurevars(callback).nonlocals.values()
                          if inspect.isfunction(v) and v.__module__.split('.')[0] in APPS]
            if len(candidates) != 1:
                break
            callback = candidates[0]
        else:
            break
    return callback


def routes_reference():
    from django.urls import get_resolver, URLResolver
    result = ['# Маршруты, обработчики и HTTP-проверки\n\n', NOTICE,
              'Admin свёрнут в один вход. URL включает HTML, JSON, команды и файлы; '
              'не каждый маршрут является страницей. Проверки внутри сервиса/формы '
              'дополняют показанные декораторы.\n\n']
    entries = []

    def walk(patterns, prefix='', namespace=''):
        for item in patterns:
            path = prefix + str(item.pattern)
            if isinstance(item, URLResolver):
                ns = namespace + (item.namespace + ':' if item.namespace else '')
                if path == 'crm/admin/':
                    entries.append(('/' + path, ns + 'index', None))
                else:
                    walk(item.url_patterns, path, ns)
            else:
                entries.append(('/' + path, namespace + (item.name or ''), unwrap(item.callback)))
    walk(get_resolver().url_patterns)
    for path, name, callback in entries:
        result.append(f'## `{path}`\n\nИмя: `{name}`.\n\n')
        if callback is None:
            result.append('Встроенное дерево Django Admin; вход дополнительно защищён `core.access_admin_panel`/superuser.\n\n')
            continue
        result.append('Обработчик: `' + callback.__module__ + '.' + callback.__qualname__ + '`.\n\n')
        try:
            location = Path(inspect.getsourcefile(callback)).resolve()
            if not location.is_relative_to(ROOT) or '.venv' in location.parts:
                continue
            lines, first = inspect.getsourcelines(callback)
            result.append(f'Исходник: `{location.relative_to(ROOT).as_posix()}:{first}`.\n\n')
            tree = ast.parse(inspect.cleandoc(''.join(lines)) if lines[0].startswith(' ') else ''.join(lines))
            node = tree.body[0]
            decorators = [ast.unparse(d) for d in getattr(node, 'decorator_list', [])]
            templates = sorted({n.value for n in ast.walk(node) if isinstance(n, ast.Constant)
                                and isinstance(n.value, str) and n.value.endswith('.html')})
            if decorators:
                result.append('Декораторы: ' + '; '.join('`' + d + '`' for d in decorators) + '.\n\n')
            if templates:
                result.append('Прямые шаблоны: ' + ', '.join('`' + t + '`' for t in templates) + '.\n\n')
        except (OSError, TypeError, SyntaxError, IndentationError):
            result.append('Детали находятся в framework-обёртке или динамическом обработчике.\n\n')
    result.insert(2, f'Записей URL: **{len(entries)}**.\n\n')
    return ''.join(result)


def schema_reference():
    from django.apps import apps
    result = ['# Схема собственных приложений\n\n', NOTICE,
              'Метаданные моделей не показывают значения записей. `blank/null/editable` '
              'не заменяют ограничения формы, permissions и проверки сервиса. '
              '`on_delete=CASCADE` не означает разрешённое пользовательское удаление документа.\n\n']
    models = [m for m in apps.get_models() if m._meta.app_label in APPS]
    for model in models:
        meta = model._meta
        result.append(f'## `{meta.label}` — {meta.verbose_name}\n\n')
        result.append((model.__doc__ or '').strip() + '\n\n')
        result.append(f'Таблица `{meta.db_table}`; порядок `{meta.ordering}`.\n\n')
        result.append('| Поле | Тип/параметры | Назначение/связь |\n| --- | --- | --- |\n')
        for field in [*meta.fields, *meta.many_to_many]:
            options = [field.get_internal_type(), f'null={field.null}', f'blank={field.blank}', f'editable={field.editable}']
            for attr in ('max_length', 'max_digits', 'decimal_places'):
                value = getattr(field, attr, None)
                if value is not None:
                    options.append(f'{attr}={value}')
            meaning = str(field.verbose_name)
            if field.is_relation and field.related_model:
                meaning += ' → ' + field.related_model._meta.label
                deletion = getattr(field.remote_field, 'on_delete', None)
                if deletion:
                    meaning += '; on_delete=' + deletion.__name__
            if field.choices:
                meaning += '; choices: ' + '; '.join(str(v) + ' → ' + str(l) for v, l in field.flatchoices)
            result.append(f'| `{field.name}` | {clean("; ".join(options))} | {clean(meaning)} |\n')
        result.append('\nPermissions: ' + clean(repr(meta.permissions)) + '. Стандартные: ' + clean(repr(meta.default_permissions)) + '.\n\n')
        result.append('Ограничения: `' + clean(repr(meta.constraints)) + '`; unique_together: `' + clean(repr(meta.unique_together)) + '`.\n\n')
    result.insert(2, f'Конкретных собственных моделей: **{len(models)}**.\n\n')
    return ''.join(result)


def ui_reference(files):
    result = ['# Шаблоны, клиентские модули, миграции и проверки\n\n', NOTICE]
    for title, selected in [
        ('HTML-шаблоны', [p for p in files if p.endswith('.html')]),
        ('JavaScript и CSS', [p for p in files if p.endswith(('.js', '.css'))]),
        ('Тесты Python/CJS и браузерные проверки', [p for p in files if (Path(p).name.startswith('test') and p.endswith(('.py','.cjs'))) or p.endswith('_browser_checks.py') or 'browser_settings.py' in p]),
        ('Миграции', [p for p in files if '/migrations/' in p and p.endswith('.py') and not p.endswith('__init__.py')]),
        ('Management commands', [p for p in files if '/management/commands/' in p and p.endswith('.py') and not p.endswith('__init__.py')]),
    ]:
        result.append(f'## {title} ({len(selected)})\n\n')
        for path in selected:
            result.append(f'### `{path}`\n\n')
            text = (ROOT / path).read_text(encoding='utf-8-sig')
            if path.endswith('.html'):
                for label, pattern in [('Базовый шаблон', r'{%\s*extends\s+[\'"]([^\'"]+)'),
                                       ('Части', r'{%\s*include\s+[\'"]([^\'"]+)'),
                                       ('Именованные действия', r'{%\s*url\s+[\'"]([^\'"]+)')]:
                    values = sorted(set(re.findall(pattern, text)))
                    if values:
                        result.append(label + ': ' + ', '.join('`' + v + '`' for v in values) + '.\n\n')
            elif path.endswith(('.js', '.css')):
                first = re.match(r'/\*(.*?)\*/', text, re.S)
                if first:
                    result.append(first[1].strip() + '\n\n')
            elif path.endswith('.py'):
                tree = ast.parse(text)
                if ast.get_docstring(tree):
                    result.append(ast.get_docstring(tree) + '\n\n')
                if '/migrations/' in path:
                    for n in ast.walk(tree):
                        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'dependencies' for t in n.targets):
                            result.append('Зависимости: `' + ast.unparse(n.value) + '`.\n\n')
                    funcs = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
                    if funcs:
                        result.append('Преобразования данных: ' + ', '.join('`' + f + '`' for f in funcs) + '. Не удалять только по возрасту файла.\n\n')
    return ''.join(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GameBAT_CRM.settings')
    import django
    django.setup()
    files = paths()
    documents = {'python.md': python_reference(files), 'routes.md': routes_reference(),
                 'models.md': schema_reference(), 'ui_and_migrations.md': ui_reference(files)}
    mismatches = []
    for name, text in documents.items():
        text = text.rstrip('\n') + '\n'
        target = OUTPUT / name
        if args.check:
            if not target.exists() or target.read_text(encoding='utf-8') != text:
                mismatches.append(name)
        else:
            OUTPUT.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding='utf-8', newline='\n')
    if mismatches:
        print('Справочник требует обновления: ' + ', '.join(mismatches))
        return 1
    print('Технический справочник: ' + ('актуален' if args.check else 'обновлён') + ', файлов: ' + str(len(documents)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
