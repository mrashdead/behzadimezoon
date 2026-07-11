from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customers', '0006_customer_city'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='preferred_consultant_name',
            field=models.CharField(blank=True, default='', max_length=100, verbose_name='نام مشاور ترجیحی'),
            preserve_default=False,
        ),
    ]
