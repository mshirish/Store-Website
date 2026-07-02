from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0002_order_tax_amount_orderitem_product_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="custom_options_snapshot",
            field=models.TextField(
                blank=True,
                help_text="JSON list of {group, choice} dicts for custom cake orders.",
            ),
        ),
    ]
