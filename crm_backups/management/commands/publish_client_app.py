from pathlib import Path
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from crm_backups.client_apps import publish


class Command(BaseCommand):
    help='Явная публикация проверенного ZIP администратором; не строит программу в HTTP.'
    def add_arguments(self,parser):
        parser.add_argument('kind',choices=['local_agent','opera']);parser.add_argument('file',type=Path)
        parser.add_argument('--actor-id',type=int,required=True);parser.add_argument('--notes',default='')
    def handle(self,**options):
        actor=get_user_model().objects.get(pk=options['actor_id'])
        result=publish(options['kind'],options['file'],actor,notes=options['notes'])
        self.stdout.write(f'{result.kind} {result.version} · {result.pk} · SHA-256 {result.sha256}')
