from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('reservations', '0012_alter_reservation_previous_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReservationArchiveSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('original_reservation_id', models.IntegerField(db_index=True)),
                ('data', models.JSONField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('note', models.TextField(blank=True)),
                ('created_by', models.ForeignKey(on_delete=models.PROTECT, related_name='reservation_snapshots', to='accounts.user', verbose_name='ایجاد کننده snapshot')),
            ],
            options={
                'verbose_name': 'نسخه آرشیوی رزرو',
                'verbose_name_plural': 'نسخه‌های آرشیوی رزرو',
                'ordering': ['-created_at'],
            },
        ),
    ]
