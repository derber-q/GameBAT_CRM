import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from integrations.services import save_avito_credentials


class Command(BaseCommand):
    help = "Импортирует client_id/client_secret из локального файла в зашифрованное хранилище."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True)

    def handle(self, *args, **options):
        path = Path(options["file"])
        if not path.is_file():
            raise CommandError("Файл не найден.")
        text = path.read_text(encoding="utf-8-sig")
        values = {}
        for key in ("client_id", "client_secret"):
            match = re.search(rf"(?im)^\s*{key}\s*[:=]\s*(\S+)\s*$", text)
            if not match:
                raise CommandError(f"В файле нет поля {key}.")
            values[key] = match.group(1)
        credential = save_avito_credentials(**values)
        self.stdout.write(self.style.SUCCESS(
            f"Avito подключён; account_id={credential.account_id}. Секреты сохранены зашифрованно."
        ))
