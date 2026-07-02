import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0002_category_tax_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="cakeproduct",
            name="is_custom",
            field=models.BooleanField(
                default=False,
                help_text="Marks the single custom cake configurator product. Do not create more than one.",
            ),
        ),
        migrations.CreateModel(
            name="CakeOptionGroup",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("display_order", models.PositiveIntegerField(default=0)),
                (
                    "required",
                    models.BooleanField(
                        default=False,
                        help_text="If True, customer must select a choice for this group.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Cake Option Group",
                "verbose_name_plural": "Cake Option Groups",
                "ordering": ["display_order", "name"],
            },
        ),
        migrations.CreateModel(
            name="CakeOptionChoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(max_length=100)),
                ("display_order", models.PositiveIntegerField(default=0)),
                ("is_available", models.BooleanField(default=True)),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="choices",
                        to="catalog.cakeoptiongroup",
                    ),
                ),
            ],
            options={
                "ordering": ["display_order", "label"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="cakeoptionchoice",
            unique_together={("group", "label")},
        ),
    ]
