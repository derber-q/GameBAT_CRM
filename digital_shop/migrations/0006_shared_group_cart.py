"""Объединение только неподтверждённых черновиков; закупки и деньги сохраняются."""
import uuid
from django.db import migrations, models


def merge_drafts(apps, schema_editor):
    Cart = apps.get_model('digital_shop', 'Cart')
    Line = apps.get_model('digital_shop', 'CartLine')
    Intent = apps.get_model('digital_shop', 'PurchaseIntent')
    Audit = apps.get_model('digital_shop', 'AuditEvent')
    alias = schema_editor.connection.alias
    groups = list(Cart.objects.using(alias).exclude(state='closed').values_list('buyer_id', 'chat_id').distinct())
    for buyer_id, chat_id in groups:
        drafts = list(Cart.objects.using(alias).filter(buyer_id=buyer_id, chat_id=chat_id)
                      .exclude(state='closed').order_by('-updated_at', '-id'))
        ids = [row.pk for row in drafts]
        if Intent.objects.using(alias).filter(cart_id__in=ids).exists():
            raise RuntimeError('У открытого черновика есть закупка. Требуется сверка перед объединением корзин.')
        lines = list(Line.objects.using(alias).filter(cart_id__in=ids).order_by('pk'))
        if len(lines) > 30 or sum(row.quantity for row in lines) > 50 or sum(bool(row.account_key) for row in lines) > 20:
            raise RuntimeError('Общий черновик превышает лимит корзины. Состав сохранён, объединение отменено.')
        keeper = drafts[0]
        menus = [row.menu_message_id for row in drafts if row.menu_message_id]
        for row in drafts:
            row.state = 'open' if row.pk == keeper.pk else 'closed'
            row.revision += 1
            row.encrypted_credentials = ''
            row.credential_groups, row.price_snapshot, row.quote_body = [], {}, {}
            row.quote_id, row.quote_expires_at, row.quote_revision = '', None, None
            row.quoted_total, row.client_total = None, None
            row.prompt_message_id, row.input_product_id = None, None
            row.input_kind, row.input_mode, row.input_account = '', '', ''
            row.search_query, row.search_product_ids = '', []
            if row.pk == keeper.pk:
                row.menu_message_id = menus[0] if menus else None
            row.save(using=alias)
        for line in lines:
            line.cart_id = keeper.pk
            if line.account_key:
                line.account_key = 'a' + uuid.uuid4().hex[:10]
            line.save(using=alias, update_fields=['cart', 'account_key'])
        Audit.objects.using(alias).create(kind='group_cart_migrated', detail={
            'buyer': buyer_id, 'chat': chat_id, 'cart': str(keeper.pk),
            'merged_carts': [str(pk) for pk in ids], 'lines_preserved': len(lines)})


class Migration(migrations.Migration):
    dependencies = [('digital_shop', '0005_resultdelivery_message_ids_and_more')]
    operations = [
        migrations.RemoveConstraint(model_name='cart', name='shop_personal_active_cart'),
        migrations.RunPython(merge_drafts, migrations.RunPython.noop),
        migrations.AddConstraint(model_name='cart', constraint=models.UniqueConstraint(
            fields=('buyer', 'chat'), condition=~models.Q(state='closed'), name='shop_group_active_cart')),
    ]
