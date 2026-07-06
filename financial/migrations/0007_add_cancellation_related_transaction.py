from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('financial', '0006_enhance_financial_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='cancellationrecord',
            name='related_transaction',
            field=models.ForeignKey(
                to='financial.transaction',
                null=True,
                blank=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='cancellation_records',
                verbose_name='تراکنش مرتبط'
            ),
        ),
    ]
