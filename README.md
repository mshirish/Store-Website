# Store Website

Django + PostgreSQL web app for a grocery/bakery/meat store.

## Prerequisites

- Python 3.11+
- PostgreSQL 15+

---

## Setup

### 1. Clone & create a virtual environment

```bash
git clone <repo-url>
cd store-website

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Create the PostgreSQL database

```sql
CREATE USER store_user WITH PASSWORD 'yourpassword';
CREATE DATABASE store_db OWNER store_user;
GRANT ALL PRIVILEGES ON DATABASE store_db TO store_user;
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and fill in real values:

| Variable | Description |
|---|---|
| `SECRET_KEY` | A long random string (use `python -c "import secrets; print(secrets.token_urlsafe(50))"`) |
| `DEBUG` | `True` for local dev, `False` in production |
| `ALLOWED_HOSTS` | Comma-separated hostnames, e.g. `localhost,127.0.0.1` |
| `DATABASE_URL` | `postgres://store_user:yourpassword@localhost:5432/store_db` |
| `EMAIL_HOST` | SMTP host (leave blank to print emails to the terminal in dev) |
| `STRIPE_PUBLISHABLE_KEY` | Test publishable key from Stripe Dashboard |
| `STRIPE_SECRET_KEY` | Test secret key from Stripe Dashboard |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` from `stripe listen` output (see below) |

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Seed default data

Populates cake flavors, one starter category per kind, store hours, and site configuration:

```bash
python manage.py seed
```

### 6. Create a superuser (store owner / admin)

```bash
python manage.py createsuperuser
```

Enter an email address and password when prompted.

### 7. Start the development server

```bash
python manage.py runserver
```

- Admin panel: <http://127.0.0.1:8000/admin/>
- Customer auth pages: <http://127.0.0.1:8000/accounts/>

---

## Running with Docker

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes both Docker and Docker Compose)

### 1. Create your `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in at minimum:

| Variable | Notes |
|---|---|
| `SECRET_KEY` | Any long random string |
| `DB_PASSWORD` | Pick anything — this is the dev Postgres container password |
| `DB_NAME`, `DB_USER`, `DB_PORT` | Defaults in `.env.example` work as-is |
| `DATABASE_URL` | Leave the `localhost` URL in place — Compose overrides it automatically |
| `ACCOUNT_EMAIL_VERIFICATION` | Set to `none` for fast dev (no SMTP needed) |

Stripe keys are optional until you need to test payments.

### 2. Build and start

```bash
docker compose up --build
```

On first run this builds the image, starts Postgres, waits for it to be healthy, runs migrations, then starts the Django dev server. Subsequent starts skip the build unless you pass `--build` again.

The app is available at **http://127.0.0.1:8000**.

### 3. Seed default data and create a superuser

Open a second terminal (while the containers are running):

```bash
# Seed store hours, categories, cake flavors, and site configuration
docker compose exec web python manage.py seed

# Create the admin user (enter email + password when prompted)
docker compose exec web python manage.py createsuperuser
```

Any other management command works the same way:

```bash
docker compose exec web python manage.py <command>
```

### 4. Code changes

Source code is mounted directly into the container (`- .:/app`), so edits on the
host reflect immediately via runserver's autoreload — no rebuild needed.

If you add a new Python package, rebuild the image:

```bash
docker compose up --build
```

### 5. Database notes

The Postgres data lives in a **named Docker volume** (`postgres_data`). This means:

- `docker compose down` — stops containers; **data is preserved**
- `docker compose down -v` — stops containers AND **deletes the volume** (full wipe)
- Data from a previously native (non-Docker) Postgres install does **not** carry over. Start fresh with `seed` + `createsuperuser` as shown above.

### 6. Stopping

```bash
docker compose down          # stop; keep data
docker compose down -v       # stop; wipe database too
```

### 7. Stripe webhooks with Docker

The Stripe CLI runs on the **host** (not inside Docker) and forwards to
`localhost:8000`, which Docker maps directly to the container's port 8000. No
changes to the Stripe setup are needed:

```bash
stripe listen --forward-to localhost:8000/webhook/stripe/
```

Copy the printed `whsec_...` value into `.env` as `STRIPE_WEBHOOK_SECRET`. If
Django is already running, restart it:

```bash
docker compose restart web
```

---

## Testing Stripe payments locally

Stripe webhooks cannot reach `localhost` directly, so you need the Stripe CLI to
forward events to your local server.

### 1. Install the Stripe CLI

Download from <https://docs.stripe.com/stripe-cli> and follow the instructions
for your OS. Verify with:

```bash
stripe --version
```

### 2. Log in

```bash
stripe login
```

Follow the browser prompt to authorise the CLI with your Stripe account.

### 3. Forward webhooks to your local server

In a **separate terminal** (keep your Django server running in another):

```bash
stripe listen --forward-to localhost:8000/webhook/stripe/
```

The CLI prints a signing secret on startup, e.g.:

```
> Ready! Your webhook signing secret is whsec_abc123...
```

Copy that value into your `.env`:

```
STRIPE_WEBHOOK_SECRET=whsec_abc123...
```

Restart Django if it is already running.

### 4. Place a test order and pay

1. Sign in, add items to cart, and proceed through checkout.
2. On the confirmation page click **Pay $X Advance**.
3. On the Stripe-hosted page use the test card:
   - Number: `4242 4242 4242 4242`
   - Expiry: any future date (e.g. `12/34`)
   - CVC: any 3 digits
4. After payment, Stripe redirects you to the success page and the CLI terminal
   logs the `checkout.session.completed` event being forwarded.
5. Refresh the confirmation page — status should change to **Confirmed** and a
   confirmation email should appear in the terminal (or your inbox if SMTP is
   configured).

### Other test cards

| Scenario | Card number |
|---|---|
| Payment requires 3D Secure | `4000 0025 0000 3155` |
| Card declined | `4000 0000 0000 9995` |

Full list: <https://docs.stripe.com/testing>

---

## Project structure

```
config/         Django project package (settings, urls, wsgi)
apps/
  accounts/     Custom User model (email login via django-allauth)
  catalog/      Categories (with per-category tax_rate), products, flavors, size prices
  core/         SiteConfiguration, StoreHours, StoreClosure, pickup-window logic
  cart/         DB-backed cart (one per user)
  orders/       Order, OrderItem, Payment, Stripe webhook handler
templates/
  base.html
  cart/
  catalog/
  checkout/     checkout.html, confirmation.html, _pickup_window.html
  orders/       payment_success.html, payment_cancel.html
  emails/       Transactional email templates (txt)
static/         Static assets
```

---

## Running after initial setup

```bash
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
python manage.py runserver
```

In a second terminal (for payment testing):

```bash
stripe listen --forward-to localhost:8000/webhook/stripe/
```

Verification and transactional emails are printed to the terminal console
when `EMAIL_HOST` is not set in `.env`.
