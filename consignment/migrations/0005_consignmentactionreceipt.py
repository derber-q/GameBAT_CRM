from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('consignment', '0004_alter_cdconsignmentstock_options'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [migrations.CreateModel(
        name='ConsignmentActionReceipt',
        fields=[
            ('key', models.UUIDField(editable=False, primary_key=True, serialize=False)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('product_kind', models.CharField(max_length=8)),
            ('stock_id', models.PositiveIntegerField()),
            ('action', models.CharField(max_length=8)),
            ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
        ],
    )]
