# Store Website — Phase Roadmap

> **Status: Phases 1–4 are implemented.** This file is kept as the historical
> roadmap; the phase sections below describe the original plan. Where the build
> differs from the plan, see "Implemented vs. planned".

## Current status

Implemented:

- Customer storefront for cakes (incl. a custom-cake configurator), meat, grocery and a full catering menu, with search
- Database-backed cart (one per logged-in user) with HTMX quantity/weight updates
- Checkout with pickup-date selection and a live pickup window
- Advance payment through Stripe Checkout, confirmed by the success redirect, the Stripe webhook, or the `reconcile_stripe_orders` command (all idempotent)
- Customer order history, order detail and self-service cancellation
- Admin workflow: advance status, mark ready (emails the customer), complete pickup with offline balance, cancel
- Email notifications: order confirmed, ready for pickup, cancelled
- Docker image (gunicorn + WhiteNoise), docker-compose for development, AWS ALB/Auto Scaling/RDS reference architecture provisioned with Terraform (see ARCHITECTURE.md)

Implemented vs. planned:

- Cart is stored in the database (`Cart`/`CartItem`), not in the session
- Stripe uses Checkout Sessions, not a directly created PaymentIntent
- Custom cakes are a single `CakeProduct` with `is_custom=True` plus configurable option groups, not a separate `CategoryKind`
- Catering (sections, tray/weight options, variants) was added; it was not in the original roadmap
- Not built: balance-due reminder email, delivery, inventory, wholesale pricing, per-flavor price modifiers

---

## Phase 1 — Scaffold, auth, data models, admin

- Project scaffold: env config, PostgreSQL, requirements, .gitignore, README
- Custom `User` model (email login) + django-allauth with mandatory email verification; console email backend in dev
- Full domain models: categories & kinds, cakes (sizes + size-prices + flavors), meat (price/lb), grocery (unit price), `SiteConfiguration` singleton, `StoreHours`, `StoreClosure`, orders & line items (price-snapshotted), payments
- Pickup-window logic: `get_pickup_window(date)` computes window from `StoreHours` + `StoreClosure` override; applies 10 AM readiness floor when the date is the very next open day; window is snapshotted onto the `Order` at placement
- Full Django admin CRUD: categories, products (all three kinds), cake sizes/prices, flavors, site config, store hours, closures; order management including status advancement and offline balance-paid marking
- Management command `seed`: default cake flavors, one starter category per kind, store hours, site configuration

**Not in Phase 1** (built in later phases): storefront browse pages, cart, checkout, Stripe, delivery, email notifications beyond allauth verification.

---

## Phase 2 — Customer storefront

- Browse products by category
- Product detail pages
- Cake builder: size selector, flavor picker, optional inscription and special-requests fields
- Meat order: cut selector + weight (lbs) entry; live line-price display
- Grocery: quantity entry
- Cart (session-based)
- Pickup-date selector with live window display (computed from `get_pickup_window`); validation enforces next-open-day minimum and no same-day pickup

---

## Phase 3 — In-app advance payment (Stripe)

- Stripe integration: create PaymentIntent for the advance amount at checkout
- `Order` created in `AWAITING_PAYMENT` state; moves to `CONFIRMED` on successful capture
- Stripe webhook handler to confirm capture and update `Payment` record
- Customer order status tracking page

---

## Phase 4 — Balance payment & completion flows; email notifications

- Admin action: mark offline balance paid (records staff member + timestamp)
- Admin action: mark order ready / completed
- Email notifications: order confirmed, order ready for pickup, balance due reminder
- Customer-facing order history page

---

## Later phases

- Delivery scheduling: delivery option, address capture, fee structure
- Custom cakes: a new `CategoryKind.CUSTOM_CAKE` with multi-step builder (shape, tier count, fondant/buttercream, decoration requests, custom quote flow)
- Grocery inventory: stock tracking, low-stock alerts
- Wholesale / bulk tiered pricing
- Per-flavor price modifiers (hook is already in `CakeFlavor.sort_order` era schema — add `price_modifier` field)
