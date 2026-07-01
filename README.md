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
| `EMAIL_BACKEND` | `django.core.mail.backends.console.EmailBackend` for dev (emails print to terminal) |

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

## Project structure

```
config/         Django project package (settings, urls, wsgi)
apps/
  accounts/     Custom User model (email login via django-allauth)
  catalog/      Categories, products (cake / meat / grocery), flavors, size prices
  core/         SiteConfiguration, StoreHours, StoreClosure, pickup-window logic
  orders/       Order, OrderItem, Payment
templates/      Base templates (populated in Phase 2)
static/         Static assets (populated in Phase 2)
```

---

## Running after initial setup

```bash
source .venv/bin/activate   # or .venv\Scripts\activate on Windows
python manage.py runserver
```

Verification emails are printed to the terminal console in dev. Copy the link to confirm a new account.
