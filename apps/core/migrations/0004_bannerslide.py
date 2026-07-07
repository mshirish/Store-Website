from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0003_siteconfiguration_contact_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="BannerSlide",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to="banners/")),
                ("headline", models.CharField(blank=True, max_length=120)),
                ("subtext", models.CharField(blank=True, max_length=255)),
                ("link_url", models.URLField(blank=True, help_text="URL the button links to.")),
                ("button_label", models.CharField(blank=True, help_text="Button text; shown only when a link URL is set.", max_length=60)),
                ("order", models.PositiveSmallIntegerField(default=0, help_text="Lower numbers appear first.")),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Banner Slide",
                "verbose_name_plural": "Banner Slides",
                "ordering": ["order"],
            },
        ),
    ]
