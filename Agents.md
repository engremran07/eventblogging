# AGENTS.md — Multi-Agent Development Protocol
# Project: DjangoBlog SaaS Platform
# Read alongside CLAUDE.md — this file governs multi-agent task coordination

---

## 🤖 AGENT ARCHITECTURE OVERVIEW

Six specialized sub-agents each own a domain. Each agent MUST read CLAUDE.md before acting.
No agent modifies files outside its domain without creating a coordination note.

| Agent | Domain | Primary Files | Trigger |
|---|---|---|---|
| **Agent 1: Backend Core** | Models, migrations, BaseModel, ORM | `apps/blog/models.py`, `apps/core/models.py`, `apps/*/models.py`, `apps/*/migrations/` | Schema changes, model logic |
| **Agent 2: Admin Workspace** | Admin CRUD views, custom admin UI | `apps/blog/admin_views.py`, `apps/blog/admin.py`, `templates/admin/` | Admin feature requests |
| **Agent 3: Public Frontend** | Public views, HTMX partials, Alpine components | `apps/blog/views.py`, `templates/blog/`, `static/js/app.js`, `static/css/` | UI/UX requests |
| **Agent 4: SEO Engine** | SEO audits, metadata, interlinks, redirects | `apps/seo/`, `apps/seo/services.py`, `apps/seo/views.py` | SEO task requests |
| **Agent 5: Comments/Tags/Pages** | Comment moderation, tag management, static pages | `apps/comments/`, `apps/tags/`, `apps/pages/` | Content tool requests |
| **Agent 6: Config/DevX/Docs** | Settings, deployment, testing, documentation | `config/`, `requirements/`, `pyproject.toml`, `pyrightconfig.json`, `CLAUDE.md` | Infra, lint, docs |

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
- Any agent must NEVER modify `static/js/app.js` without Agent 3 review

---

## 🧑‍💻 AGENT 1: BACKEND CORE

**Owns:** Data layer — all models, migrations, BaseModel, custom managers, signals

**Responsibilities:**
- Maintain BaseModel inheritance across all apps
- Own PostQuerySet and all custom manager/queryset patterns
- Handle all schema migrations (`makemigrations`, `migrate`)
- Maintain `ClassVar[PostQuerySet]` type declaration on `Post.objects`

**Current State (Mar 1, 2026):**
- `Post.objects: ClassVar[PostQuerySet]` — ✅ Fixed
- BaseModel inheritance — ❌ Not yet applied (pending migration planning)
- UUID PKs — ❌ Not yet applied

**Pattern Rules:**
```python
# ALL models inherit BaseModel
class MyModel(BaseModel):
    ...

# ALL custom managers typed on the model
class Post(models.Model):
    objects: ClassVar[PostQuerySet] = PostQuerySet.as_manager()  # type: ignore[assignment]
```

---

## 🖥️ AGENT 2: ADMIN WORKSPACE  

**Owns:** Custom admin views, admin templates, admin bulk actions, admin settings

**Responsibilities:**
- All functions in `apps/blog/admin_views.py`
- All templates in `templates/admin/`
- Admin authentication (all views use `@staff_member_required`)

**Current State (Mar 1, 2026):**
- 36 request parameters annotated with `HttpRequest` — ✅ Fixed
- Return types added to all 36 public view functions — ✅ Fixed

**Critical Pattern:**
```python
# ALL admin view functions MUST have HttpRequest annotation
@staff_member_required
def admin_posts_list(request: HttpRequest) -> HttpResponse:
    ...
```

---

## 🌐 AGENT 3: PUBLIC FRONTEND

**Owns:** Public views, HTMX partials, Alpine components, templates for public site

**Responsibilities:**
- All views in `apps/blog/views.py` 
- All templates in `templates/blog/`, `templates/partials/`
- All Alpine.js components in `static/js/app.js`
- All custom CSS in `static/css/`

**Current State (Mar 1, 2026):**
- 32 request parameters annotated with `HttpRequest` — ✅ Fixed
- SSE WSGI-blocking stream replaced with polling endpoint — ✅ Fixed
- HeadlessUI components — ❌ 0/13 implemented (HIGH PRIORITY backlog)

**HeadlessUI Backlog (Priority order):**
1. `modalManager()` — Dialog
2. `toastManager()` — Notifications  
3. `drawerManager()` — SlideOver
4. `tabs()` — Tabs
5. `listbox()` — Select  
6. `combobox()` — Autocomplete
7. `dropdown()` — Menu
8. `disclosure()` — Accordion
9. `switchToggle()` — Toggle
10. `radioGroup()` — Radio
11. `popover()` — Popover
12. `commandPalette()` — Command Palette (Ctrl+K)
13. `dataTable()` — Data Table

---

## 🔍 AGENT 4: SEO ENGINE

**Owns:** SEO audits, metadata resolution, interlinking, redirects, scan jobs

**Responsibilities:**
- All code in `apps/seo/`
- SEO signals (`apps/seo/signals.py`)
- TF-IDF keyword extraction (`apps/seo/tfidf.py`)

**Current State (Mar 1, 2026):**
- All silent `except Exception: pass` blocks now log via `logger.warning(...)` — ✅ Fixed
- PERF401 list comprehension violations — ✅ Fixed
- `seo/views.py` and `seo/admin_config_services.py` PERF401 — ✅ Fixed

---

## 💬 AGENT 5: COMMENTS/TAGS/PAGES

**Owns:** Comment moderation, newsletter, tag management, static pages, policies

**Responsibilities:**
- `apps/comments/` — all models, selectors, services
- `apps/tags/` — tag selectors and views
- `apps/pages/` — pages views, policies, navigation

**Current State (Mar 1, 2026):**
- `pages/context_processors.py` logging added — ✅ Fixed
- Empty TYPE_CHECKING blocks removed — ✅ Fixed
- Unused imports removed from `comments/selectors.py` — ✅ Fixed

**Pending:**
- `selectors.py` pattern not fully applied in comments/tags — add selectors

---

## ⚙️ AGENT 6: CONFIG/DEVX/DOCS

**Owns:** Settings, deployment config, developer tooling, documentation, CI

**Responsibilities:**
- `config/settings/` — settings hierarchy
- `pyproject.toml` — ruff, pytest config
- `pyrightconfig.json` — type checking config
- `requirements/` — package management
- `CLAUDE.md`, `AGENTS.md` — living documentation

**Current State (Mar 1, 2026):**
- ruff rules expanded: `E,F,I,B,UP,C4,SIM,PERF,RUF` + `target-version = "py311"` — ✅
- pyrightconfig: `venvPath`, `venv`, `useLibraryCodeForTypes`, `include: ["apps","config"]` — ✅
- migrations excluded from ruff — ✅

**Security Backlog (CRITICAL):**
```
🔴 DB credentials hardcoded in settings/base.py — must move to .env
🔴 SECRET_KEY has insecure fallback value — must fail loudly if not in env
🔴 No .env.example exists — cannot onboard new developers
```

---

## 🚨 TASK ROUTING MATRIX

When a user request comes in, route it to the right agent:

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

These were started but not completed. Next session must resume:

| # | Item | Owner | Priority | Status |
|---|---|---|---|---|
| 1 | Migrate all models to use BaseModel | Agent 1 | HIGH | Not started |
| 2 | Move DB creds + SECRET_KEY to .env | Agent 6 | CRITICAL | Not started |  
| 3 | Create .env.example | Agent 6 | CRITICAL | Not started |
| 4 | HeadlessUI components 0/13 | Agent 3 | MEDIUM | Not started |
| 5 | selectors.py for comments app | Agent 5 | MEDIUM | Not started |
| 6 | selectors.py for tags app | Agent 5 | MEDIUM | Not started |
| 7 | Hardcoded URL /admin/ in base.html | Agent 3 | LOW | Not started |

---

*This document is maintained by Agent 6 (Config/DevX/Docs). Update after every cross-agent session.*
