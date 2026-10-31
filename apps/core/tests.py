import datetime
from unittest import mock

from django.test import TestCase, override_settings

from .models import StoreHours
from .utils import READINESS_FLOOR, get_next_open_day, get_pickup_window


@override_settings(TIME_ZONE='America/New_York')
class PickupWindowTimezoneTests(TestCase):
    # 2026-11-03 03:30 UTC is still Monday 2026-11-02, 10:30 PM in New York.
    LATE_EVENING_UTC = datetime.datetime(2026, 11, 3, 3, 30, tzinfo=datetime.timezone.utc)

    def setUp(self):
        for weekday in range(7):
            StoreHours.objects.create(
                weekday=weekday, open_time=datetime.time(8, 30), close_time=datetime.time(19, 0),
            )

    def test_today_is_the_store_date_not_the_utc_date(self):
        with mock.patch('django.utils.timezone.now', return_value=self.LATE_EVENING_UTC):
            self.assertEqual(get_next_open_day(), datetime.date(2026, 11, 3))
            # Tuesday is the next open day in New York, so the readiness floor applies.
            window = get_pickup_window(datetime.date(2026, 11, 3))
        self.assertEqual(window, (READINESS_FLOOR, datetime.time(19, 0)))

    def test_day_after_next_open_day_keeps_normal_hours(self):
        with mock.patch('django.utils.timezone.now', return_value=self.LATE_EVENING_UTC):
            window = get_pickup_window(datetime.date(2026, 11, 4))
        self.assertEqual(window, (datetime.time(8, 30), datetime.time(19, 0)))


@override_settings(ALLOWED_HOSTS=['store.example.com'])
class HealthCheckTests(TestCase):
    def test_healthz_ok_for_unlisted_host_without_db(self):
        # The ALB probes by private IP, which is not in ALLOWED_HOSTS.
        with self.assertNumQueries(0):
            response = self.client.get('/healthz/', HTTP_HOST='10.0.1.42')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_other_paths_still_enforce_allowed_hosts(self):
        response = self.client.get('/', HTTP_HOST='10.0.1.42')
        self.assertEqual(response.status_code, 400)
