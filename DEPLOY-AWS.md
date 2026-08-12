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
# Include the ALB DNS name and the EC2 instance's private IP.
# The ALB health-check probe comes from the private IP, so it must be listed.
ALLOWED_HOSTS=localhost,127.0.0.1,<alb-dns-name>,<ec2-private-ip>
# Example:
# ALLOWED_HOSTS=localhost,127.0.0.1,my-alb-123456789.us-east-1.elb.amazonaws.com,10.0.1.42

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

WhiteNoise is configured and active (`STATICFILES_STORAGE = CompressedManifestStaticFilesStorage`).
Gunicorn serves compressed, content-hashed static files directly — no nginx or S3 needed for this lab.

The `collectstatic` step (automatic on start) writes files into `/app/staticfiles/` inside the container. WhiteNoise picks them up transparently. Nothing extra to configure.

---

## 4. Stripe webhook — action required

The local `stripe listen` tunnel **does not exist** on AWS. After the Stripe checkout session completes, Stripe tries to POST to your webhook URL to confirm the payment. Without a registered endpoint, the webhook never fires and orders will stay in **Awaiting Payment** status even after the card is charged.

**To fix this for the lab:**

1. Go to [https://dashboard.stripe.com/test/webhooks](https://dashboard.stripe.com/test/webhooks)
2. Click **Add endpoint**
3. Endpoint URL: `http://<alb-dns-name>/webhook/stripe/`
   *(trailing slash required)*
4. Events to send: select `checkout.session.completed`
5. After saving, copy the **Signing secret** (`whsec_...`) shown on the endpoint page
6. Set that value as `STRIPE_WEBHOOK_SECRET` in your `.env` on the instance and restart the container:
   ```bash
   docker restart store
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
