# Store Website — Phase Roadmap

## Phase 1 (current) — Scaffold, auth, data models, admin

- Project scaffold: env config, PostgreSQL, requirements, .gitignore, README
- Custom `User` model (email login) + django-allauth with mandatory email verification; console email backend in dev
- Full domain models: categories & kinds, cakes (sizes + size-prices + flavors), meat (price/lb), grocery (unit price), `SiteConfiguration` singleton, `StoreHours`, `StoreClosure`, orders & line items (price-snapshotted), payments (Stripe-ready, not wired)
- Pickup-window logic: `get_pickup_window(date)` computes window from `StoreHours` + `StoreClosure` override; applies 10 AM readiness floor when the date is the very next open day; window is snapshotted onto the `Order` at placement
- Full Django admin CRUD: categories, products (all three kinds), cake sizes/prices, flavors, site config, store hours, closures; order management including status advancement and offline balance-paid marking
- Management command `seed`: default cake flavors, one starter category per kind, store hours, site configuration

**Not in Phase 1:** storefront browse pages, cart, checkout, Stripe, delivery, email notifications beyond allauth verification.

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
