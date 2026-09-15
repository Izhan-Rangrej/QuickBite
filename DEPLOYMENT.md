# 🚀 Deploying QuickBite — step by step

This guide takes QuickBite from your laptop to a live HTTPS URL **for free**, using
**Render** (Option B). A condensed PythonAnywhere version is at the bottom, and
post-deployment (domain, analytics, backups, monitoring) applies to all options.

---

## Why Render?

| | Render | PythonAnywhere | Railway |
|---|---|---|---|
| Free web app | ✅ (spins down after inactivity) | ✅ (always on, `yourname.pythonanywhere.com`) | ⚠️ trial credits only |
| Free PostgreSQL | ✅ | ❌ (MySQL only on free) | ❌ |
| Auto-deploy from GitHub | ✅ | ❌ manual | ✅ |
| Blueprint (infra as code) | ✅ `render.yaml` included | ❌ | ⚠️ |

Render + free Postgres + `render.yaml` (already in this repo) is the smoothest path.
The one trade-off: the free tier sleeps after ~15 minutes without traffic, so the
first request after a nap takes ~30 s. Fine for a portfolio; upgrade later if needed.

---

## Part 1 — Prepare the repo (5 minutes)

1. **Generate a real secret key** (never ship the dev one):

   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
   ```

2. **Confirm the production files exist** (they're all in this repo):

   ```
   requirements.txt   # pinned dependencies
   render.yaml        # Render Blueprint: web service + free Postgres
   build.sh           # pip install → minify_static → collectstatic → migrate
   .env.example       # documentation of every env var
   .gitignore         # keeps .env, db.sqlite3, media/, staticfiles/ out of git
   ```

3. **Smoke-test production mode locally** (catches 90% of deploy surprises):

   ```bash
   python manage.py minify_static
   python manage.py collectstatic --noinput
   QUICKBITE_DEBUG=False ALLOWED_HOSTS=localhost,127.0.0.1 \
     python manage.py runserver 8001
   # then visit http://localhost:8001/ — static files are served by WhiteNoise,
   # custom 404 pages are live, DEBUG banners are gone.
   ```

4. **Push to GitHub:**

   ```bash
   git init && git add . && git commit -m "QuickBite — ready to deploy"
   git branch -M main
   git remote add origin https://github.com/<you>/quickbite.git
   git push -u origin main
   ```

> ⚠️ **Media files note.** Uploaded dish/restaurant photos live in `media/`
> (git-ignored). On Render's free tier there is no persistent disk by default, so
> either (a) commit the seed images under `static/images/seed/` (already in the
> repo) and re-run `python manage.py seed_data` via the shell after deploy, or
> (b) add a Render **Disk** mount at `/opt/render/project/src/media` (Blueprint:
> `disk: { name: media, mountPath: .../media, sizeGB: 1 }`) for real uploads.

---

## Part 2 — Deploy on Render (10 minutes)

1. **Create the account:** [render.com](https://render.com) → sign in with GitHub.

2. **Create a Blueprint:** Dashboard → **New +** → **Blueprint** → pick your
   `quickbite` repo. Render reads `render.yaml` and creates:
   - `quickbite-db` — a free PostgreSQL 16 database
   - `quickbite` — the web service, with `DATABASE_URL` wired automatically

3. **Watch the build.** Render runs `build.sh`:
   `pip install → minify_static → collectstatic → migrate`, then starts
   `gunicorn quickbite.wsgi:application --bind 0.0.0.0:$PORT`.

4. **Set the two `sync: false` env vars** (service → Environment):
   - `ALLOWED_HOSTS` = `quickbite.onrender.com` (your actual URL)
   - `SITE_URL` = `https://quickbite.onrender.com`

   Hit **Save** → the service redeploys.

5. **Seed + superuser.** Service → **Shell** tab:

   ```bash
   python manage.py seed_data                     # categories, restaurants, dishes, coupons, reviews
   python manage.py createsuperuser               # admin login
   ```

6. **Visit `https://quickbite.onrender.com`** 🎉
   Check: homepage → add to cart → login → checkout → `/dashboard/` →
   `/sitemap.xml` → a bad URL (custom 404).

---

## Part 3 — Real email (optional but recommended)

The free tier has no SMTP. Use [Brevo](https://brevo.com) (300 emails/day free):

1. Brevo → SMTP & API → create an SMTP key.
2. On Render, add env vars:
   `EMAIL_HOST=smtp-relay.brevo.com`, `EMAIL_PORT=587`,
   `EMAIL_HOST_USER=yourlogin`, `EMAIL_HOST_PASSWORD=<smtp-key>`,
   `DEFAULT_FROM_EMAIL=QuickBite <you@yourdomain.com>`, `CONTACT_EMAIL=you@yourdomain.com`.
3. Order confirmations, status updates and contact-form messages now send for real.

---

## Part 4 — Post-deployment checklist

### Custom domain
Render → your service → **Settings → Custom Domains** → add `quickbite.com` →
at your registrar create `CNAME quickbite → quickbite.onrender.com` → wait for
the green check (Render issues the TLS cert automatically). Then update
`ALLOWED_HOSTS` and `SITE_URL` to the new domain.

### Google Analytics 4
1. [analytics.google.com](https://analytics.google.com) → create property → **Web**
   data stream → copy the Measurement ID (`G-XXXXXXXXXX`).
2. Set `GA_MEASUREMENT_ID=G-XXXXXXXXXX` on Render. The `gtag.js` snippet is
   already wired into `base.html` (IP-anonymised) and only renders when the
   variable is set — no template edits needed.

### Google Search Console
1. [search.google.com/search-console](https://search.google.com/search-console) →
   add property → **HTML tag** method → copy the `content="..."` token.
2. Set `SEARCH_CONSOLE_TOKEN=<token>` on Render (it renders the verification meta
   tag), then click **Verify**.
3. **Sitemaps** → submit `sitemap.xml`. It's generated live from your database
   (dishes, restaurants, categories, static pages) and `robots.txt` already
   points at it.

### Backups
- **Database:** Render free tier: nightly snapshots are a paid add-on, so schedule
  a dump instead — a GitHub Action with `pg_dump $DATABASE_URL > backup.sql`
  pushed to a private repo weekly is free and sufficient at this scale.
- **Media:** keep seed images in git (already done); if you add a Disk, back it up
  with a periodic `tar` to object storage.
- **Code:** GitHub *is* the backup — every deploy is a commit.

### Monitoring
- **Uptime:** [UptimeRobot](https://uptimerobot.com) free — ping `/` every 5 min,
  email on downtime.
- **Errors:** Render → your service → **Logs** tab shows Django's console logging
  (configured in `settings.py`). For alerting, add Sentry (free tier) later:
  `pip install sentry-sdk`, `sentry_sdk.init(dsn=...)` in `settings.py`.
- **Health:** the Blueprint sets `healthCheckPath: /` — Render restarts the app
  automatically if it stops responding.

---

## Appendix A — PythonAnywhere (Option A) instead

1. Sign up (free "Beginner" account) → **Web** tab → *Add a new web app* →
   **Manual configuration**, Python 3.13.
2. **Files** tab: upload the repo (or clone via a Bash console:
   `git clone https://github.com/<you>/quickbite.git`).
3. Bash console:
   ```bash
   cd quickbite
   pip install --user -r requirements.txt
   python manage.py minify_static && python manage.py collectstatic
   python manage.py migrate && python manage.py seed_data
   python manage.py createsuperuser
   ```
4. Create `.env` in the project dir with `QUICKBITE_DEBUG=False`,
   `SECRET_KEY=...`, `ALLOWED_HOSTS=<you>.pythonanywhere.com`,
   `SITE_URL=https://<you>.pythonanywhere.com`.
5. **Web** tab:
   - *Source code*: `/home/<you>/quickbite`
   - *WSGI file* — edit to:
     ```python
     import os, sys
     from decouple import AutoConfig
     path = '/home/<you>/quickbite'
     if path not in sys.path:
         sys.path.append(path)
     os.chdir(path)
     from django.core.wsgi import get_wsgi_application
     application = get_wsgi_application()
     ```
   - *Static files*: URL `/static/` → dir `/home/<you>/quickbite/staticfiles/`
     and URL `/media/` → `/home/<you>/quickbite/media/`
6. Reload the web app. Free accounts renew every 3 months (one click) and must
   use PythonAnywhere' outbound whitelist — SMTP to Brevo works.

## Appendix B — Railway (Option C), in short

`railway init` inside the repo → `railway up` → `railway add postgresql` →
Railway injects `DATABASE_URL` automatically (our settings already read it) →
set `QUICKBITE_DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `SITE_URL` →
Settings → Networking → **Generate domain**. Note: Railway's free plan is
trial credits, not a perpetual free tier.

---

## Rollback plan

Every Render deploy is immutable — **Deploys** tab → any previous deploy →
**Rollback**. Database migrations are the only non-reversible part; keep them
additive (no destructive `migrations.RemoveField`) between releases.
