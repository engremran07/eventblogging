# AGENTS.md — Multi-Agent Development Protocol
# Project: DjangoBlog SaaS Platform
# Read alongside CLAUDE.md — this file governs multi-agent task coordination

---

## 🤖 AGENT ARCHITECTURE OVERVIEW

Six specialized sub-agents each own a domain. Each agent MUST read CLAUDE.md before acting.
No agent modifies files outside its domain without creating a coordination note.

| Agent | Domain | Primary Files | Trigger |
|---|---|---|---|
| **Agent 1: Backend Core** | Models, services, selectors, signals, forms, middleware | `apps/blog/models.py`, `apps/blog/services.py`, `apps/blog/selectors.py`, `apps/blog/signals.py`, `apps/core/models.py`, `apps/core/utils.py`, `apps/core/middleware.py`, `apps/blog/taxonomy_rules.py`, `apps/blog/context_processors.py` | Schema changes, model logic, service extraction |
| **Agent 2: Admin Workspace** | Admin CRUD views, admin templates, admin CSS/JS | `apps/blog/admin_views.py`, `templates/admin/**`, `static/css/admin/**`, `static/js/admin/**` | Admin feature requests, inline style elimination |
| **Agent 3: Public Frontend** | Public views, HTMX partials, Alpine, public CSS/JS | `apps/blog/views.py`, `apps/blog/urls.py`, `templates/blog/**`, `templates/base.html`, `static/css/`, `static/js/site/**` | UI/UX requests, HTMX interactions |
| **Agent 4: SEO Engine** | SEO audits, metadata, interlinks, redirects, Celery tasks | `apps/seo/**`, `templates/seo/**`, `static/js/admin/control.js` | SEO task requests, audit changes |
| **Agent 5: Comments/Tags/Pages** | Comment moderation, reactions, tag management, static pages | `apps/comments/**`, `apps/tags/**`, `apps/pages/**`, `templates/pages/**`, `templates/policies/**`, comment/reaction partials | Content tool requests |
| **Agent 6: Config/DevX/Docs** | Settings, deployment, testing, documentation | `config/**`, `requirements/**`, `.env.example`, `CLAUDE.md`, `AGENTS.md`, `docs/**` | Infra, lint, docs |

---

## 📋 AGENT CONTRACT — EACH AGENT MUST FOLLOW

### Before Every Task
1. Read CLAUDE.md Active Context
2. Check if the task touches ANOTHER agent's domain → coordinate first
3. Write full todo list using manage_todo_list tool
4. Mark first item in-progress

### During Every Task
1. Follow all CLAUDE.md patterns (services.py, selectors.py, 15 Golden Laws)
2. Type-annotate every function you add or modify — `request: HttpRequest`, return types explicit
3. Log `logger.warning(...)` for every `except Exception` — zero silent failures
4. Run ruff check and confirm zero violations before finishing

### After Every Task
1. Run: `ruff check apps/ config/ --output-format=concise` → must be clean
2. Run: `python manage.py check --deploy` if settings changed
3. Update CLAUDE.md Active Context + Learned Patterns
4. Commit with prefix matching task: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`

---

## 🔄 CROSS-AGENT COORDINATION PROTOCOL

When your change affects another agent's domain:
1. Document it in a `COORDINATION NOTE` block in Active Context
2. Format: `"Agent 1→Agent 3: Post.objects type changed — Agent 3 must re-check views.py selectors"`
3. The downstream agent MUST resolve the coordination note before closing their session

### Prohibited Cross-Domain Actions
- Agent 2 (Admin) must NEVER modify `apps/blog/services.py` directly — request Agent 1
- Agent 4 (SEO) must NEVER add ORM queries in `seo/views.py` — use `seo/selectors.py`
- Any agent must NEVER modify `static/js/alpine-store.js` without Agent 3 review

---

## 🚀 ONBOARDING GUIDE — CLONE TO RUNNING IN 10 STEPS

```bash
# 1. Clone
git clone https://github.com/engremran07/eventblogging.git
cd eventblogging

# 2. Create virtual environment
python -m venv .venv
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements/development.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — set DJANGO_SECRET_KEY, POSTGRES_*, REDIS_URL at minimum

# 5. Create PostgreSQL database
# psql -U postgres -c "CREATE DATABASE djangoblog;"
# psql -U postgres -c "CREATE USER djangoblog_user WITH PASSWORD 'yourpass';"
# psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE djangoblog TO djangoblog_user;"
# Enable required PostgreSQL extensions (once, in psql):
# CREATE EXTENSION IF NOT EXISTS pg_trgm;
# CREATE EXTENSION IF NOT EXISTS unaccent;

# 6. Run migrations
python manage.py migrate

# 7. Create superuser
python manage.py createsuperuser

# 8. Load initial singleton settings (creates default Site/SEO/Feature settings)
python manage.py shell -c "
from core.models import SiteIdentitySettings, SeoSettings, FeatureControlSettings, SiteAppearanceSettings, IntegrationSettings
for cls in [SiteIdentitySettings, SeoSettings, FeatureControlSettings, SiteAppearanceSettings, IntegrationSettings]:
    cls.get_solo()
print('Singletons initialized.')
"

# 9. Collect static files (dev: optional, prod: required)
python manage.py collectstatic --noinput

# 10. Start development server
python manage.py runserver
# Visit http://127.0.0.1:8000 — public site
# Visit http://127.0.0.1:8000/admin/posts/ — custom admin workspace
# Visit http://127.0.0.1:8000/admin/ — Django admin (auth + settings)
```

### Start Celery Workers (Optional — for SEO background tasks)
```bash
# Terminal 1: worker
celery -A config.celery worker -l info

# Terminal 2: beat (periodic tasks)
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Verify Installation
```bash
python manage.py check --deploy   # Should show no critical issues in dev
python manage.py test apps/       # Run test suite
ruff check apps/ config/          # Must be clean
```

---

## 🏗️ HOW TO ADD A NEW FEATURE — END TO END

### Step 1 — Model (Agent 1)
```python
# apps/your_app/models.py
from core.models import BaseModel

class YourModel(BaseModel):
    name = models.CharField(max_length=255, db_index=True)
    # ... fields

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['name', 'is_active'])]

    def __str__(self): return self.name
    def get_absolute_url(self): return reverse('your_app:detail', kwargs={'pk': self.pk})
```

### Step 2 — Migration (Agent 1)
```bash
python manage.py makemigrations --name=add_yourmodel
python manage.py migrate
```

### Step 3 — Selector (Agent 1)
```python
# apps/your_app/selectors.py
def get_your_model(pk) -> YourModel:
    return get_object_or_404(YourModel.objects.select_related(...), pk=pk)

def get_your_model_list(*, search: str = '') -> QuerySet[YourModel]:
    qs = YourModel.objects.filter(is_active=True).select_related(...)
    if search:
        qs = qs.filter(name__icontains=search)
    return qs
```

### Step 4 — Service (Agent 1)
```python
# apps/your_app/services.py
def create_your_model(*, name: str, ...) -> YourModel:
    obj = YourModel(name=name, ...)
    obj.full_clean()
    obj.save()
    return obj

def update_your_model(*, obj: YourModel, data: dict) -> YourModel:
    for field, value in data.items():
        setattr(obj, field, value)
    obj.full_clean()
    obj.save()
    return obj
```

### Step 5 — View (Agent 3 for public, Agent 2 for admin)
```python
# apps/your_app/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from . import selectors, services

class YourModelListView(LoginRequiredMixin, TemplateView):
    template_name = 'your_app/list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['objects'] = selectors.get_your_model_list(search=self.request.GET.get('q', ''))
        return ctx
```

### Step 6 — URL (Agent 6 registers in config/urls.py)
```python
# apps/your_app/urls.py
app_name = 'your_app'
urlpatterns = [
    path('', views.YourModelListView.as_view(), name='list'),
    path('<uuid:pk>/', views.YourModelDetailView.as_view(), name='detail'),
    # HTMX endpoints prefixed hx_
    path('hx/list/', views.HxListView.as_view(), name='hx_list'),
]
# config/urls.py — add:
# path('your-app/', include('your_app.urls')),
```

### Step 7 — Template (Agent 3)
```html
{# templates/your_app/list.html #}
{% extends "base.html" %}
{% block content %}
<div hx-get="{% url 'your_app:hx_list' %}"
     hx-trigger="load"
     hx-target="#object-list">
  <div id="object-list">{% include 'your_app/partials/_list.html' %}</div>
</div>
{% endblock %}
```

### Step 8 — HTMX Partial (Agent 3)
```python
# HTMX view
def hx_list(request):
    if not request.htmx:
        return redirect('your_app:list')
    objects = selectors.get_your_model_list(search=request.GET.get('q', ''))
    return render(request, 'your_app/partials/_list.html', {'objects': objects})
```

---

## 🖥️ HOW TO ADD A NEW ADMIN WORKSPACE SECTION (Agent 2)

1. Add view functions to `apps/blog/admin_views.py` decorated with `@staff_member_required`
2. Register URL in `config/urls.py` under `/admin/your-section/`
3. Add sidebar link to `templates/admin/partials/sidebar.html`
4. Create templates in `templates/admin/your_section/`
5. All styling via workspace.css — zero inline styles
6. All HTMX partials must guard: `if not request.htmx: return redirect(...)`

---

## 🔍 HOW TO ADD A NEW SEO CHECK (Agent 4)

1. Open `apps/seo/checks.py`
2. Add a function following the existing pattern:
   ```python
   def check_your_rule(post: Post, context: dict) -> CheckResult:
       passed = ...  # evaluate condition
       return CheckResult(
           check_id="your_rule",
           label="Human-readable label",
           passed=passed,
           score=5,  # weight out of 100 total
           detail="What to show when failed",
       )
   ```
3. Add to `ALL_CHECKS` list at the bottom of `checks.py`
4. Verify `sum(check.score for check in ALL_CHECKS) == 100`
5. Run SEO audit on a test post to verify the check appears in results

---

## 🎨 HOW TO ADD A NEW APPEARANCE PRESET (Agent 1/Agent 6)

1. Open `apps/core/models.py` → `APPEARANCE_PRESETS` dict
2. Copy an existing preset block and rename it:
   ```python
   "your_preset": {
       "label": "Your Preset Name",
       "light": { "--bg-main": "...", "--brand": "...", ... },
       "dark":  { "--bg-main": "...", "--brand": "...", ... },
   }
   ```
3. Run `python manage.py migrate` (no migration needed — data-only change)
4. In Django admin, go to Site Appearance Settings, choose the new preset
5. Verify both light and dark modes render correctly via the theme toggle
6. Update `THEME_STYLE_INVENTORY.md` in docs/

---

## 🧪 HOW TO RUN TESTS

```bash
# All tests
pytest

# Specific app
pytest apps/blog/tests/ -v

# With coverage
pytest --cov=apps --cov-report=html

# Test database: Django creates a test DB from migrations each run.
# Default: test_djangoblog on same Postgres host as POSTGRES_HOST.
# Override in settings: TEST = {'NAME': 'custom_test_db'}

# Factories (model-bakery pattern):
from model_bakery import baker

@pytest.fixture
def post(db):
    return baker.make('blog.Post', status='published', published_at=timezone.now())
```

---

## 🧑‍💻 AGENT 1: BACKEND CORE

**Owns:** Data layer — all models, migrations, BaseModel, custom managers, signals, services, selectors, taxonomy

**Current State (Mar 1, 2026):**
- `Post.objects: ClassVar[PostQuerySet]` — ✅
- `Post.is_published` property — ✅ Added
- `Post.get_reading_time_display()` — ✅ Added
- `Post.can_be_edited_by(user)` — ✅ Added
- `apps/blog/signals.py` — ✅ Created (publish webhook + comment moderation backstop)
- `blog/apps.py` ready() wires signals — ✅
- `taxonomy_rules.get_category_max_depth()` caches result 5 min — ✅
- `context_processors.site_appearance` caches 5 singletons 5 min — ✅
- BaseModel inheritance for all new models — ✅ (core models)
- Post model does NOT inherit BaseModel (integer PK by design) — intentional

---

## 🖥️ AGENT 2: ADMIN WORKSPACE

**Owns:** Custom admin views, admin templates, admin bulk actions, admin settings

**Current State (Mar 1, 2026):**
- 36 request parameters annotated with `HttpRequest` — ✅
- Return types on all 36 public view functions — ✅
- Inline styles in `dashboard.html` (20) and `editor.html` (32) — ❌ PENDING

**Critical Pattern:**
```python
@staff_member_required
def admin_posts_list(request: HttpRequest) -> HttpResponse:
    ...
```

---

## 🌐 AGENT 3: PUBLIC FRONTEND

**Owns:** Public views, HTMX partials, Alpine components, templates for public site

**Current State (Mar 1, 2026):**
- 32 request parameters annotated with `HttpRequest` — ✅
- SSE WSGI-blocking stream replaced with polling endpoint — ✅
- HeadlessUI components — ❌ 0/13 implemented (HIGH PRIORITY backlog)
- Custom 404 template (`templates/errors/404.html`) — ✅ Added

---

## 🔍 AGENT 4: SEO ENGINE

**Owns:** SEO audits, metadata resolution, interlinking, redirects, scan jobs

**Current State (Mar 1, 2026):**
- All silent `except Exception: pass` blocks log via `logger.warning(...)` — ✅
- PERF401 list comprehension violations — ✅ Fixed
- `SeoRedirectMiddleware` caches redirect table — ✅ (was already present)
- `SeoRedirectRule` save/delete → cache invalidation signal — ✅ Added

---

## 💬 AGENT 5: COMMENTS/TAGS/PAGES

**Owns:** Comment moderation, newsletter, tag management, static pages, policies

**Current State (Mar 1, 2026):**
- `comments/selectors.py` — ✅ Full selectors present
- `tags/selectors.py` — ✅ Full selectors + `get_all_tags_with_counts()` added
- `pages/selectors.py` — ✅ Present
- `selectors.py` pattern fully applied in comments/tags — ✅

---

## ⚙️ AGENT 6: CONFIG/DEVX/DOCS

**Owns:** Settings, deployment config, developer tooling, documentation, CI

**Current State (Mar 1, 2026):**
- ruff rules: `E,F,I,B,UP,C4,SIM,PERF,RUF` + `target-version = "py311"` — ✅
- pyrightconfig: `venvPath`, `venv`, `useLibraryCodeForTypes`, `include: ["apps","config"]` — ✅
- migrations excluded from ruff — ✅
- `.env.example` with full comments — ✅ Updated
- `handler404` and `handler500` registered in `config/urls.py` — ✅ Added
- `templates/errors/404.html` and `templates/errors/500.html` — ✅ Added
- `INTERNAL_IPS` in `development.py` — ✅ Added
- `SESSION_ENGINE = cache` in `production.py` — ✅ Added
- `STATICFILES_STORAGE = whitenoise` in `production.py` — ✅ Added

---

## 🚨 TASK ROUTING MATRIX

| Request Contains | Primary Agent | Notify |
|---|---|---|
| "model", "migration", "database", "queryset" | Agent 1 | Agent 2 if admin-facing |
| "admin", "dashboard", "bulk action", "settings page" | Agent 2 | Agent 1 if schema change |
| "public", "view", "template", "HTMX", "Alpine" | Agent 3 | Agent 2 if shared component |
| "SEO", "audit", "interlink", "redirect", "metadata" | Agent 4 | Agent 1 if model change |
| "comment", "tag", "topic", "category", "page", "policy" | Agent 5 | Agent 1 if model change |
| "settings", "deploy", "ruff", "pyright", "requirements", "docs" | Agent 6 | All agents if global change |

---

## 📊 OPEN LOOPS — ITEMS REQUIRING FOLLOW-UP

| # | Item | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Admin dashboard.html: eliminate 20 inline styles | Agent 2 | HIGH | Not started |
| 2 | Admin posts/editor.html: eliminate 32 inline styles | Agent 2 | HIGH | Not started |
| 3 | HeadlessUI components 0/13 | Agent 3 | MEDIUM | Not started |
| 4 | Add whitenoise to MIDDLEWARE in production.py | Agent 6 | MEDIUM | Not started |
| 5 | Add SEO audit `checks.py` count verification (must equal 25) | Agent 4 | MEDIUM | Not started |
| 6 | Add `django-debug-toolbar` to development.py INSTALLED_APPS | Agent 6 | LOW | Not started |

---

*This document is maintained by Agent 6 (Config/DevX/Docs). Update after every cross-agent session.*
