from django.test import TestCase, override_settings


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
