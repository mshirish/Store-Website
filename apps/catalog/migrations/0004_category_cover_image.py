from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0003_cakeproduct_is_custom_cakeoptiongroup_cakeoptionchoice"),
    ]

    operations = [
        migrations.AddField(
            model_name="category",
            name="cover_image",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="categories/",
                help_text="Cover image shown on the homepage tile and the category listing header.",
            ),
        ),
    ]
