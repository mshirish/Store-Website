from django.http import HttpResponse


class HealthCheckMiddleware:
    """
    Answer the load balancer's health check before any other middleware runs.

    - Host validation is skipped: the ALB probes each instance by its private
      IP, which changes with every instance the ASG launches and is not in
      ALLOWED_HOSTS. (Django only validates the host when request.get_host()
      is called, which happens in later middleware.)
    - The database is not touched: an RDS failover must not make healthy
      instances look broken and get replaced.

    It reports only "this process is up and serving requests".
    """

    PATH = '/healthz/'

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == self.PATH:
            return HttpResponse('ok', content_type='text/plain')
        return self.get_response(request)
