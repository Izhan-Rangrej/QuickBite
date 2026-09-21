# 🍔 QuickBite — Food Delivery Platform

A complete, production-ready food delivery web application built with **Django 6.1**.
Browse restaurants and dishes, cart and checkout with coupons, track orders live,
review what you ate — and manage everything from an admin dashboard and a
restaurant-owner panel.

> **Live demo:** https://quickbite-p7x2.onrender.com
> *(deploy it in ~15 min — see [DEPLOYMENT.md](DEPLOYMENT.md))*


---

## ✨ Features

### Customer
- 🏠 **Home** — hero, categories, top restaurants, offers, reviews, app CTA (original landing design preserved, Poppins + orange `#FF5722` theme, AOS scroll animations)
- 🍕 **Menu** — filter by category / cuisine / price / rating / veg / availability, sort, paginate
- 🔍 **Live search** — AJAX suggestions + full results page (name, description, cuisine)
- 📍 **Location** — browser geolocation with Haversine "distance from you" and delivery-time adjustment
- 🛒 **Cart** — guests (session) *and* logged-in users (DB), merged on login, AJAX quantity updates
- 🎟️ **Coupons** — percentage / flat / free-delivery, min-order & usage-limit validation (`FIRST50`, `FREEDEL` seeded)
- 🧾 **Checkout** — addresses, COD, coupon re-validation, GST-style tax, delivery fee (free above ₹499)
- 📦 **Orders** — order IDs like `QB260914-QXX7K0`, status timeline, ETA, printable invoice PDF attachment
- ⭐ **Reviews** — 1–5 stars + photo, verified purchase, helpful votes, average ratings on dishes
- 👤 **Accounts** — signup, login (rate-limited 🔒), remember-me, profile, order history
- 📄 **Info pages** — About, Contact (working form → email), FAQ accordion, Terms, Privacy, Refund Policy
- 🎭 **Themed error pages** — custom 400/403/404/500 with a "Go to Home" button

### Admin (staff)
- Dashboard with Chart.js analytics (revenue, orders by status, top dishes)
- Full CRUD: categories, restaurants, dishes, coupons, orders (status flow with emails), users

### Restaurant owner
- Owner panel: manage your restaurant, dishes (toggle availability, prices), incoming orders, reviews

### SEO & performance (Phase 10)
- Meta + Open Graph + Twitter Card tags on every page, canonical URLs
- JSON-LD structured data (`Organization`, `Restaurant`, `MenuItem`)
- `sitemap.xml` (generated from DB) + `robots.txt`, semantic HTML, descriptive alt text
- Minified CSS/JS (`minify_static`), fingerprinted + gzip/brotli static via WhiteNoise
  (`Cache-Control: immutable`), `loading="lazy"` images, Pillow image optimizer
- Google Analytics 4 + Search Console hooks (env-var driven, zero template edits)

### Security
- CSRF on every form and AJAX call; ORM-only queries (no raw SQL); auto-escaped templates
- Django password validators, login rate limiting (5 fails / 10 min per IP)
- HTTPS enforcement + HSTS in production, `X-Content-Type-Options`, `X-Frame-Options: DENY`
- Secrets via environment variables (`python-decouple`) — `.env` is git-ignored

## 🧰 Tech stack

| Layer | Tech |
|---|---|
| Backend | Python 3.13, Django 6.1 |
| Database | SQLite (dev) / **Neon** serverless PostgreSQL (prod, via `DATABASE_URL`) |
| Frontend | Django templates, vanilla JS, AOS, Chart.js, Boxicons, Poppins (served by the same Render service — server-rendered monolith, no separate SPA host) |
| Email | Django 6.1 `MAILERS` API — console (dev) / SMTP (Brevo, SendGrid…) |
| Static | WhiteNoise (fingerprint + compress), rcssmin/rjsmin |
| Images | Pillow (`optimize_images` management command) |
| Hosting | **Render** free web service (app + static) · **Neon** free Postgres (data) — see [DEPLOYMENT.md](DEPLOYMENT.md) |

## 📁 Project layout

```
QuickBite/
├── quickbite/          # settings (env-driven), urls, wsgi
├── accounts/           # custom User, signup/login (rate-limited), profile, password reset
├── core/               # home, menu, search, location, info pages, sitemaps, SEO, errors
├── restaurants/        # Restaurant, Category, Dish models
├── cart/               # session + DB carts, coupon engine
├── orders/             # Order lifecycle, invoice PDF, status emails
├── reviews/            # dish reviews + photo uploads
├── dashboard/          # admin analytics + CRUD
├── panel/              # restaurant-owner self-service
├── templates/          # base.html + per-app templates + errors/ + core/pages/
├── static/             # css/js/images  (→ static/dist/ when minified)
├── media/              # user uploads (git-ignored)
├── requirements.txt  Procfile  render.yaml  build.sh  .env.example
└── DEPLOYMENT.md  README.md
```

## 🚀 Run locally

```bash
git clone https://github.com/<you>/quickbite.git && cd quickbite
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # defaults work for development out of the box
python manage.py migrate
python manage.py seed_data    # 6 restaurants, dishes, categories, coupons, reviews
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/> — seeded logins: `pizza_owner / owner123` (owner),
your superuser for `/admin/` and `/dashboard/`. Coupons: **FIRST50**, **FREEDEL**.

### Tests

```bash
python manage.py test        # 110 tests — models, views, forms, SEO, security, deploy
```

## 🌍 Deploy for free

Full step-by-step (Neon project → Render Blueprint → env vars → seed → SMTP →
domain → GA4/Search Console → backups → monitoring; PythonAnywhere & Railway
appendices): **[DEPLOYMENT.md](DEPLOYMENT.md)**

Minimum env vars on the host: `QUICKBITE_DEBUG=False`, `SECRET_KEY`,
`ALLOWED_HOSTS`, `SITE_URL`, `DATABASE_URL` (the rest documented in `.env.example`).

## ⚙️ Useful management commands

| Command | What it does |
|---|---|
| `python manage.py seed_data` | Demo categories, restaurants, dishes, coupons, reviews |
| `python manage.py optimize_images` | Pillow-compress uploads in `media/` (idempotent, `--dry-run`) |
| `python manage.py minify_static` | Build minified `static/dist/` (used automatically in production) |
| `python manage.py collectstatic` | Gather + fingerprint static files (deployment) |

## 📜 License

Educational project — use it, learn from it, make it yours.
