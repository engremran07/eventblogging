# Ultimate Django Blog

A full-stack content platform built with modern Django architecture and a unified UI stack.

## Stack

- Django 6
- PostgreSQL (`postgreswl` / `Aa1357`)
- Jazzmin admin
- HTMX + `django-htmx`
- Alpine.js
- Bootstrap 5
- Tagulous (single tags, tag sets, tree categories, autocomplete)
- Deterministic algorithmic intelligence (rule engine + heuristics + NLP, no LLMs)
- Celery + Redis (optional async workers)

## Implemented Capabilities

### Backend

- Rich `Post` model with:
  - markdown -> sanitized HTML rendering
  - SEO fields (`meta_title`, `meta_description`, `canonical_url`)
  - editorial flags (`is_featured`, `is_editors_pick`)
  - engagement controls (`allow_comments`, `allow_reactions`)
  - computed analytics (`word_count`, `reading_time`, `views_count`)
- `PostRevision` model for content history snapshots
- `NewsletterSubscriber` model for growth workflow
- Interaction models: `Comment`, `PostLike`, `PostBookmark`, `PostView`
- Service layer (`blog/services.py`) for filtering, feed context, metrics, serialization
- JSON APIs:
  - `GET /api/posts/`
  - `GET /api/dashboard/stats/` (authenticated)

### Algorithmic Intelligence (No LLM)

- Rule-based tokenization and scoring in `blog/services.py`
- Deterministic vector hashing + cosine similarity for related-post retrieval
- Heuristic bonuses for popularity and recency
- No LLM provider dependencies

### Admin Control Bar

- WordPress-style admin/staff topbar with:
  - context label
  - quick create menu (post/page)
  - comments moderation shortcut with pending badge
  - notifications dropdown with mark-read action
  - cache flush (superuser only)
  - content refresh trigger
- Control endpoints:
  - `GET /admin/control/context`
  - `GET /admin/control/notifications`
  - `POST /admin/control/action/<action_key>`
  - `GET /admin/control/panel/stats`
- Feature flag:
  - `ENABLE_STAFF_ADMINBAR=true|false` to keep/remove staff admin bar globally.

### Site Settings App

- Dedicated `site_settings` app in admin with enriched singleton controls:
  - `Appearance` (theme mode + preset + live palette preview)
  - `Site Profile` (brand identity, footer, contact defaults)
  - `SEO Settings` (robots, canonical base, OG/Twitter defaults)
  - `Integrations` (analytics and webhook configuration)
  - `Feature Controls` (adminbar, API, reactions, newsletter, maintenance/read-only toggles)
- Appearance is exposed as a submenu under **Site Settings**.

### Tagulous

- `primary_topic` using `SingleTagField`
- `tags` using `TagField`
- `categories` using tree `TagField`
- Autocomplete endpoints for all tag fields
- Initial tags wired through `manage.py initial_tags`

### Frontend

- Componentized pages with Bootstrap + custom CSS visual system
- HTMX-driven feed updates, filtering, and pagination
- HTMX reaction/comment interactions
- Alpine-powered reading progress and shell behaviors
- Live markdown preview in post editor (`POST /editor/preview/`)
- Dashboard analytics surface and revision history UI

## Seed Data and Accounts

- Seeded demo content (published and draft posts)
- Accounts:
  - `admin` / `Aa1357` (superuser)
  - `writer` / `Aa1357` (author)

## PostgreSQL Setup Performed

Already provisioned in this environment:

- Role: `postgreswl`
- Database: `postgreswl`
- Password: `Aa1357`
- Privileges: includes `CREATEDB`
- Migrations: applied

## Run

```powershell
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

Current background server:

- URL: `http://127.0.0.1:8000`
- PID file: `runserver.pid`
- Logs: `server.out.log`, `server.err.log`

## Useful Commands

```powershell
# Migrations
.\.venv\Scripts\python manage.py makemigrations
.\.venv\Scripts\python manage.py migrate

# Tagulous initial data
.\.venv\Scripts\python manage.py initial_tags

# Test suite
.\.venv\Scripts\python manage.py test

# Stop background server
Stop-Process -Id (Get-Content runserver.pid)
```
