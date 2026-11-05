"""Явные начальные правила платформ, без классификации по подстроке названия."""
from django.core.management.base import BaseCommand,CommandError
from django.contrib.auth import get_user_model
from django.db import transaction
from catalog.models import Platform
from orders.customs_models import CustomsGroup,CustomsEvent
from orders.customs_service import require

# Только точные распространённые обозначения; неоднозначность требует ручной привязки.
PRESETS=(
    (('PS4','PlayStation 4'),'Игровые диски для PS4','disc'),
    (('PS5','PlayStation 5'),'Игровые диски для PS5','disc'),
    (('NS','Nintendo Switch','Switch'),'Игровые картриджи для Nintendo Switch','cartridge'),
    (('NS2','Nintendo Switch 2','Switch 2'),'Игровые картриджи для Nintendo Switch 2','cartridge'),
)


class Command(BaseCommand):
    help='Создать отсутствующие явные таможенные группы PS4/PS5/Switch/Switch 2, без изменения товаров и старых документов.'
    def add_arguments(self,parser):parser.add_argument('--actor-id',type=int,required=True)
    @transaction.atomic
    def handle(self,**options):
        actor=get_user_model().objects.get(pk=options['actor_id']);require(actor,'rules')
        platforms=list(Platform.objects.all());created=0
        for aliases,label,medium in PRESETS:
            matches=[p for p in platforms if p.name.casefold() in {a.casefold() for a in aliases}]
            if len(matches)!=1:
                self.stdout.write(f'{label}: требуется ручной выбор платформы ({len(matches)} точных совпадений).');continue
            platform=matches[0]
            if CustomsGroup.objects.filter(platform=platform).exists():continue
            group=CustomsGroup(name=label,ru_description=label,medium=medium,platform=platform,updated_by=actor)
            group.full_clean();group.save();created+=1
            CustomsEvent.objects.create(actor=actor,action='group_seeded',details={'group_id':group.pk,'platform_id':platform.pk})
        self.stdout.write(f'Создано начальных групп: {created}. Коды и изготовители автоматически не назначались.')
