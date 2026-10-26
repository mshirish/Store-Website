# AWS EC2 Deploy Guide (HTTP, ALB + RDS)

Short-lived lab deploy: EC2 instance behind an Application Load Balancer,
RDS Postgres, test-mode Stripe. HTTP only (no custom domain, no HTTPS).

---

## 1. Required environment variables

Create `/opt/app/.env` on the instance (or inject via ECS task environment /
AWS Systems Manager Parameter Store — never bake secrets into the image).

```dotenv
# ── Core ──────────────────────────────────────────────────────────────────────
SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_urlsafe(50))">
DEBUG=false

# ── Hosts & CSRF ──────────────────────────────────────────────────────────────
# Include the ALB DNS name. The instance's private IP is NOT needed: set the
# target group health-check path to /healthz/, which answers before Django
# validates the Host header (and never touches the database).
ALLOWED_HOSTS=localhost,127.0.0.1,<alb-dns-name>
# Example:
# ALLOWED_HOSTS=localhost,127.0.0.1,my-alb-123456789.us-east-1.elb.amazonaws.com

# Full scheme+host origins that may POST forms through the ALB.
# HTTP lab: scheme is http, host is the ALB DNS name only.
CSRF_TRUSTED_ORIGINS=http://<alb-dns-name>
# Example:
# CSRF_TRUSTED_ORIGINS=http://my-alb-123456789.us-east-1.elb.amazonaws.com

# ── Reverse-proxy ─────────────────────────────────────────────────────────────
# Enable so Django uses X-Forwarded-Host from the ALB for URL generation.
USE_X_FORWARDED_HOST=true

# HTTP lab — leave all three of these at false (or omit them entirely).
# Flip to true later when you add HTTPS alongside HTTPS_PROXY=true.
SECURE_SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
# HTTPS_PROXY=false   ← omit or set false; do NOT enable for HTTP-only lab

# ── Database (RDS) ────────────────────────────────────────────────────────────
# Full Postgres URL pointing at your RDS endpoint.
# Format: postgres://<user>:<password>@<rds-endpoint>:<port>/<db-name>
DATABASE_URL=postgres://store_user:CHANGEME@store.cxyz.us-east-1.rds.amazonaws.com:5432/store_db

# ── Stripe (test mode) ────────────────────────────────────────────────────────
# Use test keys only — pk_test_... and sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
# See section 4 (Stripe webhook) below before setting this.
STRIPE_WEBHOOK_SECRET=whsec_...

# ── Auth ──────────────────────────────────────────────────────────────────────
# 'none' skips email verification (fine for lab; no SMTP needed).
# 'mandatory' requires it — needs EMAIL_HOST configured.
ACCOUNT_EMAIL_VERIFICATION=none

# ── Email (optional) ──────────────────────────────────────────────────────────
# Leave EMAIL_HOST blank to log emails to the container stdout instead.
EMAIL_HOST=
EMAIL_PORT=587
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=true
DEFAULT_FROM_EMAIL=Our Store <noreply@example.com>
```

---

## 2. On-instance command sequence

### Build and start the container

```bash
# On the EC2 instance — adjust image name/tag to match your build/pull step.

docker run -d \
  --name store \
  --env-file /opt/app/.env \
  -p 8000:8000 \
  --restart unless-stopped \
  store-app:latest
```

What happens automatically on container start (see `entrypoint.sh` + `Dockerfile CMD`):

1. `python manage.py migrate --noinput` — applies all pending migrations
2. `python manage.py collectstatic --noinput` — writes fingerprinted static files to `/app/staticfiles/`
3. `gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2` — starts the app

You do **not** need to run migrate or collectstatic manually — they run every time the container starts. If you ever want to run them explicitly (e.g. to check output):

```bash
# Run migrations manually (safe to run again — idempotent):
docker exec store python manage.py migrate --noinput

# Run collectstatic manually:
docker exec store python manage.py collectstatic --noinput
```

### Create the superuser (once, first deploy only)

```bash
docker exec -it store python manage.py createsuperuser
```

Admin is at `http://<alb-dns-name>/admin/`.

### Seed initial data (if your project has fixtures)

```bash
# Example — adjust fixture name to match yours:
docker exec store python manage.py loaddata initial_data.json
```

### View logs

```bash
docker logs -f store
```

---

## 3. Static files

WhiteNoise is configured and active (`STORAGES['staticfiles']` = `CompressedManifestStaticFilesStorage`).
Gunicorn serves compressed, content-hashed static files directly — no nginx or S3 needed for this lab.

The `collectstatic` step (automatic on start) writes files into `/app/staticfiles/` inside the container. WhiteNoise picks them up transparently. Nothing extra to configure.

---

## 4. Stripe webhook (recommended backup)

Orders are confirmed when the customer returns from Stripe: the success page asks Stripe directly whether the Checkout Session is paid. That works with no webhook at all. The webhook is a **backup** for customers who close the tab before the redirect. Without it, those orders stay hidden until `reconcile_stripe_orders` runs (see below). Both paths share one idempotent confirm function, so an order is never confirmed or emailed twice.

**To fix this for the lab:**

1. Go to [https://dashboard.stripe.com/test/webhooks](https://dashboard.stripe.com/test/webhooks)
2. Click **Add endpoint**
3. Endpoint URL: `http://<alb-dns-name>/webhook/stripe/`
   *(trailing slash required)*
4. Events to send: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `checkout.session.expired`
5. After saving, copy the **Signing secret** (`whsec_...`) shown on the endpoint page
6. Set that value as `STRIPE_WEBHOOK_SECRET` in your `.env` on the instance and restart the container:
   ```bash
   docker restart store
   ```

**Reconcile / cleanup job.** Schedule this on the instance (e.g. cron every 15 minutes). It confirms any paid checkout that both the redirect and the webhook missed, and deletes abandoned unpaid ones. It is safe to run any time:

```bash
docker exec store python manage.py reconcile_stripe_orders
# add --dry-run to preview, --audit to list paid Stripe sessions never applied to an order (refund candidates)
```

---

## 5. When you later add HTTPS

Flip these vars in your env (do **not** change the image or code):

```dotenv
HTTPS_PROXY=true
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
CSRF_TRUSTED_ORIGINS=https://<your-domain-or-alb-dns>
```

`SECURE_PROXY_SSL_HEADER` is already wired in `settings.py` — it activates automatically when `HTTPS_PROXY=true`.

---

## 6. Checklist before hitting the ALB URL

- [ ] Security group on EC2 allows inbound TCP 8000 from the ALB security group
- [ ] Security group on RDS allows inbound TCP 5432 from the EC2 security group
- [ ] ALB target group health check: HTTP, path `/`, port 8000
- [ ] `ALLOWED_HOSTS` includes the ALB DNS name **and** the EC2 private IP (health checks come from the private IP)
- [ ] `CSRF_TRUSTED_ORIGINS` includes `http://<alb-dns-name>` (no trailing slash)
- [ ] `DATABASE_URL` points at the RDS endpoint, not `localhost` or `db`
- [ ] Container is running: `docker ps`
- [ ] No startup errors: `docker logs store`
