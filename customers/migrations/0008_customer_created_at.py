from django.db import migrations, models
from django.utils import timezone


def backfill_created_at(apps, schema_editor):
    Customer = apps.get_model('customers', 'Customer')
    Customer.objects.filter(created_at__isnull=True).update(created_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0007_preferred_consultant_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='created_at',
            field=models.DateTimeField(null=True, verbose_name='تاریخ ثبت در CRM'),
        ),
        migrations.RunPython(backfill_created_at, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='تاریخ ثبت در CRM'),
        ),
    ]
