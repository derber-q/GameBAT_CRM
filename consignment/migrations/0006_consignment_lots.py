from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('consignment', '0005_consignmentactionreceipt')]
    operations = []
    for kind in ('cd', 'tech'):
        operations.extend([
            migrations.AddField(model_name=f'{kind}consignmentstock', name='lot_key',
                field=models.CharField('Партия', max_length=100, blank=True, default='', editable=False)),
            migrations.RemoveConstraint(model_name=f'{kind}consignmentstock', name=f'unique_{kind}_platform_warehouse_stock'),
            migrations.AddConstraint(model_name=f'{kind}consignmentstock', constraint=models.UniqueConstraint(
                fields=('platform', 'warehouse', kind, 'lot_key'), name=f'unique_{kind}_platform_warehouse_lot')),
        ])
