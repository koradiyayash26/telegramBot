# Generated by Django 5.0.7 on 2024-07-29 15:33

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0003_alter_purchase_user'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='purchase',
            name='user',
        ),
    ]
