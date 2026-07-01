from decimal import Decimal

from django.db import models


# ── Site configuration (singleton) ───────────────────────────────────────────

class SiteConfiguration(models.Model):
    site_name = models.CharField(max_length=200, default='Our Store')
    advance_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('50.00'),
        help_text='Percentage of the order total charged as the advance payment (0–100).',
    )

    class Meta:
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configuration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Singleton must not be deleted.
        pass

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return self.site_name


# ── Store hours ───────────────────────────────────────────────────────────────

WEEKDAY_CHOICES = [
    (0, 'Monday'),
    (1, 'Tuesday'),
    (2, 'Wednesday'),
    (3, 'Thursday'),
    (4, 'Friday'),
    (5, 'Saturday'),
    (6, 'Sunday'),
]


class StoreHours(models.Model):
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES, unique=True)
    open_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Leave blank when is_closed is checked.',
    )
    close_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Leave blank when is_closed is checked.',
    )
    is_closed = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Store Hours'
        verbose_name_plural = 'Store Hours'
        ordering = ['weekday']

    def __str__(self):
        day = dict(WEEKDAY_CHOICES)[self.weekday]
        if self.is_closed:
            return f'{day}: Closed'
        return f'{day}: {self.open_time:%I:%M %p} – {self.close_time:%I:%M %p}'


class StoreClosure(models.Model):
    """
    A row with no special times = full closure for that date.
    A row with special_open_time and special_close_time = overridden hours for that date.
    """
    date = models.DateField(unique=True)
    note = models.CharField(max_length=255, blank=True)
    special_open_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Set for a partial-day override; leave blank for a full closure.',
    )
    special_close_time = models.TimeField(
        null=True,
        blank=True,
        help_text='Set for a partial-day override; leave blank for a full closure.',
    )

    class Meta:
        verbose_name = 'Store Closure / Special Hours'
        verbose_name_plural = 'Store Closures / Special Hours'
        ordering = ['date']

    @property
    def is_full_closure(self):
        return self.special_open_time is None

    def __str__(self):
        if self.is_full_closure:
            return f'{self.date}: Closed — {self.note}' if self.note else f'{self.date}: Closed'
        return (
            f'{self.date}: {self.special_open_time:%I:%M %p} – {self.special_close_time:%I:%M %p}'
            + (f' ({self.note})' if self.note else '')
        )
