from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_remove_siteconfiguration_tax_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="siteconfiguration",
            name="contact_phone",
            field=models.CharField(blank=True, default="(508) 796-5365", max_length=50),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="contact_email",
            field=models.EmailField(blank=True, default="info@bahnans.com", max_length=254),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="contact_address",
            field=models.CharField(
                blank=True,
                default="344 Pleasant Street, Worcester, MA",
                help_text="Plain text address used in footer and Google Maps embed.",
                max_length=255,
            ),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="facebook_url",
            field=models.URLField(blank=True, help_text="Full URL including https://"),
        ),
        migrations.AddField(
            model_name="siteconfiguration",
            name="instagram_url",
            field=models.URLField(blank=True, help_text="Full URL including https://"),
        ),
    ]
