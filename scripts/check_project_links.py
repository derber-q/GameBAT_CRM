"""Проверяет локальные ссылки документации, шаблоны, static и имена URL.

Только чтение исходников/метаданных: не рендерит рабочие документы, не делает
API-запросы и не запускает интеграции. Динамические ссылки проверяются тестами
соответствующего сценария, а не считаются гарантированно корректными здесь.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GameBAT_CRM.settings')
    import django
    django.setup()
    from django.contrib.staticfiles import finders
    from django.template.loader import get_template
    from django.urls import get_resolver, URLResolver
    files = sorted({p for p in subprocess.check_output(['git', 'ls-files', '-co', '--exclude-standard', '-z'], cwd=ROOT).decode('utf-8').split('\0') if p and (ROOT / p).is_file()})
    names = set()

    def routes(patterns, namespace=''):
        for item in patterns:
            if isinstance(item, URLResolver):
                routes(item.url_patterns, namespace + (item.namespace + ':' if item.namespace else ''))
            elif item.name:
                names.add(namespace + item.name)
    routes(get_resolver().url_patterns)
    errors = []
    templates = 0
    local_links = 0
    assets = set()
    for path in files:
        p = ROOT / path
        if p.suffix not in {'.md', '.html'}:
            continue
        text = p.read_text(encoding='utf-8-sig')
        if p.suffix == '.md':
            # Примеры внутри fenced code не являются настоящими ссылками документа.
            text = re.sub(r'```.*?```', '', text, flags=re.S)
            for target in re.findall(r'\[[^\]]*\]\(([^\s)]+)\)', text):
                url = urlparse(target)
                if url.scheme or url.netloc or not url.path:
                    continue
                resolved = (p.parent / unquote(url.path)).resolve()
                local_links += 1
                if not resolved.exists():
                    errors.append(f'{path}: отсутствует ссылка {target}')
            continue
        templates += 1
        template_name = path.split('/templates/', 1)[1] if '/templates/' in path else path.removeprefix('templates/')
        try:
            get_template(template_name)
        except Exception as exc:
            errors.append(f'{path}: шаблон не компилируется: {type(exc).__name__}: {exc}')
        for template in re.findall(r'{%\s*(?:extends|include)\s+[\'"]([^\'"]+)', text):
            try:
                get_template(template)
            except Exception as exc:
                errors.append(f'{path}: недоступна часть {template}: {type(exc).__name__}')
        for asset in re.findall(r'{%\s*static\s+[\'"]([^\'"]+)', text):
            assets.add(asset)
            if not finders.find(asset):
                errors.append(f'{path}: отсутствует static {asset}')
        for name in re.findall(r'{%\s*url\s+[\'"]([^\'"]+)', text):
            if name not in names:
                errors.append(f'{path}: неизвестное имя URL {name}')
    for error in errors:
        print(error)
    print(f'Шаблонов: {templates}; static-ссылок: {len(assets)}; локальных ссылок документации: {local_links}; ошибок: {len(errors)}.')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
