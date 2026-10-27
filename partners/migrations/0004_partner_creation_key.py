import uuid
from django.db import migrations, models


def fill_keys(apps, schema_editor):
    Partner = apps.get_model('partners', 'Partner')
    for partner in Partner.objects.using(schema_editor.connection.alias).filter(creation_key__isnull=True).iterator():
        partner.creation_key = uuid.uuid4()
        partner.save(update_fields=('creation_key',))


class Migration(migrations.Migration):
    dependencies = [('partners', '0003_partner')]
    operations = [
        migrations.AddField(model_name='partner', name='creation_key', field=models.UUIDField(null=True, unique=True, editable=False)),
        migrations.RunPython(fill_keys, migrations.RunPython.noop),
        migrations.AlterField(model_name='partner', name='creation_key', field=models.UUIDField(default=uuid.uuid4, unique=True, editable=False)),
    ]
