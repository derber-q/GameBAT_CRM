from django.conf import settings
from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("sales", "0001_initial"),
        ("warehouse", "0003_transfers"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="CashRegister",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("balance", models.DecimalField(decimal_places=2, default=0, max_digits=20, validators=[django.core.validators.MinValueValidator(0)], verbose_name="Остаток наличных")),
                ("warehouse", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="cash_register", to="warehouse.warehouse", verbose_name="Склад")),
            ],
            options={
                "verbose_name": "касса", "verbose_name_plural": "кассы",
                "permissions": [("view_cash_register", "Может просматривать остаток кассы"), ("view_cash_history", "Может просматривать историю кассы"), ("deposit_cash", "Может вносить наличные"), ("collect_cash", "Может инкассировать наличные")],
            },
        ),
        migrations.CreateModel(
            name="CashTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("operation_type", models.CharField(choices=[("deposit", "Внесение наличных"), ("collection", "Инкассация"), ("sale_payment", "Оплата продажи")], max_length=24, verbose_name="Операция")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=20, validators=[django.core.validators.MinValueValidator(0.01)], verbose_name="Сумма")),
                ("comment", models.TextField(verbose_name="Комментарий")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Проведена")),
                ("cash_register", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="transactions", to="cash.cashregister", verbose_name="Касса")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cash_transactions", to=settings.AUTH_USER_MODEL, verbose_name="Провёл")),
                ("sale", models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cash_transaction", to="sales.sale", verbose_name="Продажа")),
            ],
            options={"verbose_name": "кассовая операция", "verbose_name_plural": "кассовые операции", "ordering": ("-created_at", "-id")},
        ),
        migrations.AddConstraint(model_name="cashregister", constraint=models.CheckConstraint(condition=models.Q(("balance__gte", 0)), name="cash_register_balance_nonnegative")),
        migrations.AddConstraint(model_name="cashtransaction", constraint=models.CheckConstraint(condition=models.Q(("amount__gt", 0)), name="cash_transaction_amount_positive")),
    ]
