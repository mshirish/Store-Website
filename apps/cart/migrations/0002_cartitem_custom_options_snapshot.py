from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("cart", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="cartitem",
            name="custom_options_snapshot",
            field=models.TextField(
                blank=True,
                help_text="JSON list of {group, choice} dicts for custom cake orders.",
            ),
        ),
    ]
