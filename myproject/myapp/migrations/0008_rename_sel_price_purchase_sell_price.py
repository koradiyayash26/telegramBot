# Generated by Django 5.0.7 on 2024-07-29 16:39

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0007_rename_sell_price_purchase_sel_price'),
    ]

    operations = [
        migrations.RenameField(
            model_name='purchase',
            old_name='sel_price',
            new_name='sell_price',
        ),
    ]
