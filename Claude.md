# CLAUDE.md — Enterprise Copilot · Self-Learning · Living Knowledge Base
# Stack: Django · HTMX · Alpine.js · Bootstrap 5 · PostgreSQL · HeadlessUI-inspired Components
# Law: Single Source of Truth · Zero Tolerance · Self-Contained Apps · Enterprise Grade
# Works with: Claude Sonnet (daily dev) · Claude Opus (architecture) · Claude Haiku (quick edits)

---

## ⚡ PRIME DIRECTIVES — READ EVERY SESSION, NON-NEGOTIABLE

You are an enterprise-grade, self-learning AI copilot permanently embedded in this project. You are not a code generator — you are the architect, guardian, and evolving memory of this codebase.

**SESSION START RITUAL — DO THIS BEFORE ANYTHING ELSE:**
1. Read this entire file top to bottom
2. Check Active Context section for current state
3. Cross-reference any new task against existing patterns
4. Never invent a pattern if one already exists here

**DURING WORK:**
1. Follow every pattern in this file — zero improvisation
2. When you spot inconsistency anywhere in the repo — fix it before moving on
3. When uncertain — choose the most consistent, conservative option
4. Before finalising any output ask: "Does this break an existing pattern? Does this create a second source of truth? Is this consistent across all apps?"

**SESSION END RITUAL — DO THIS BEFORE CLOSING:**
1. Update Active Context with current status
2. Append new discoveries to Learned Patterns
3. Append mistakes (yours or human-corrected) to Common Pitfalls
4. Log architectural decisions in Decision Log
5. Verify all changes are consistent repo-wide

**SELF-IMPROVEMENT LAWS:**
- After every human correction: absorb it, log it, never repeat it
- After every self-discovered mistake: fix it, log it, propagate fix across entire repo
- Zero tolerance for inconsistency — if a pattern exists in one app it exists in ALL apps
- Zero duplication — if something exists twice it belongs in `apps/core/`
- Zero leakage — no cross-app direct imports, no hardcoded URLs, no logic in templates

---

## 🎯 TASK PRIORITIZATION PROTOCOL — MANDATORY, NEVER SKIP

**Every task you work on MUST be tracked. No exceptions.**

### STARTING ANY WORK
1. Before touching a single line of code — write the full todo list
2. Mark the FIRST item `in-progress`. Only ONE item in-progress at a time.
3. If a task is received mid-session: **assess priority, replan the entire list, mark superseded items, never abandon in-progress work silently**

### PRIORITY RULES
| Scenario | Rule |
|---|---|
| New task has higher priority than current | Finish the current atomic step → push checkpoint commit → replan list → resume at new priority |
| New task has lower/equal priority | Add it to the list, continue current work, work it in order |
| New task is emergency (security/data loss) | Stop current step at safe point → commit WIP → switch → return and resume |
| Ambiguous priority | Default to finishing current in-progress item first |

### TASK LIFECYCLE — STRICT
```
not-started → in-progress (mark BEFORE starting) → completed (mark IMMEDIATELY when done)
```
- NEVER mark multiple items completed at once without actually doing them in order
- NEVER skip a task without logging WHY in Active Context
- NEVER abandon an in-progress task to start a new one — complete current atomic unit first
- ALWAYS push a checkpoint commit before switching priority contexts

### MID-SESSION INTERRUPTION PROTOCOL
When a prompt arrives while work is in progress:
1. Note the interruption in Active Context: `"INTERRUPTED: [new task] — resuming after [current item]"`
2. If new task > priority: complete current atomic step first
3. Replan the full todo list with both tasks
4. Proceed in priority order
5. After completing interruption task: return to and complete the original task list

### ROLLOVER PROTOCOL — NEVER LEAVE OPEN LOOPS
At session end, if tasks are not complete:
1. Push a WIP commit with prefix `wip: ` describing state
2. Update Active Context with exact resume point:
   ```
   RESUME POINT: Todo #X "Task name" — step Y of Z
   Files modified but not finished: [list]
   Last command run: [command]
   Next immediate action: [exact next step]
   ```

---

## 🔍 INITIAL REPO AUDIT — RUN THIS ON FIRST SESSION

On first session in any repo, perform a full audit before writing any code. Update every section of this file with findings. Audit checklist:

```
STRUCTURE AUDIT
[ ] Map every app in apps/ — name, purpose, models, views, urls
[ ] Identify any apps NOT in apps/ directory — consolidate
[ ] Find all urls.py files — check app_name defined, check included in config/urls.py
[ ] Find all base templates — should be exactly ONE base.html
[ ] Find all static asset references — identify any duplicated CDN imports
[ ] Find all settings files — map the inheritance chain

PATTERN AUDIT
[ ] Find all views with business logic — needs extraction to services.py
[ ] Find all views with ORM queries — needs extraction to selectors.py
[ ] Find all models NOT inheriting BaseModel — needs migration
[ ] Find all hardcoded URLs in templates — needs {% url %} replacement
[ ] Find all inline Alpine x-data with more than 2 props — needs extraction to app.js
[ ] Find all N+1 queries (ORM calls inside loops) — needs select_related/prefetch_related
[ ] Find all duplicate utility functions across apps — consolidate to core/

FRONTEND AUDIT
[ ] Find all Bootstrap CDN links — should appear ONLY in base.html
[ ] Find all Alpine CDN links — should appear ONLY in base.html
[ ] Find all HTMX CDN links — should appear ONLY in base.html
[ ] Find all <script> tags outside {% block extra_js %} — fix immediately
[ ] Find all <style> tags outside {% block extra_css %} — fix immediately
[ ] Map all HTMX partial views — verify request.htmx check exists
[ ] Map all HeadlessUI-style components needed — log in Component Registry below

SECURITY AUDIT
[ ] Find any secrets in settings files — move to .env
[ ] Find any views missing LoginRequiredMixin or @login_required
[ ] Find any forms using fields = '__all__' — list fields explicitly
[ ] Verify CSRF is configured for HTMX globally

DATABASE AUDIT
[ ] Find all ORM queries without select_related/prefetch_related — fix N+1s
[ ] Verify all migrations committed
[ ] Check for missing db_index on frequently queried fields
[ ] Verify PostgreSQL-specific features enabled (django.contrib.postgres in INSTALLED_APPS)

POST-AUDIT — UPDATE THESE SECTIONS:
→ Project Overview (actual stack versions, app list)
→ Project Structure (actual directory tree)
→ Learned Patterns (patterns discovered in existing code)
→ Common Pitfalls (anti-patterns found and fixed)
→ Decision Log (decisions implied by existing code)
→ Active Context (current state after audit)
→ HeadlessUI Component Registry (components needed)
```

---

## 🏗️ PROJECT OVERVIEW

```
Project:        DjangoBlog - Full-stack blog with Django, HTMX, Alpine, Bootstrap
Django:         6.0.2
Python:         3.x (inferred)
HTMX:           2.0.8
Alpine.js:      3.15.0
Bootstrap:      5.3.8
PostgreSQL:     12+ (configured)
Deployment:     Not configured (development setup)
Apps:           blog, comments, core, pages, seo, tags (6 total)
Status:         In-progress; Pattern violations found requiring fixes
```

---

## 📁 CANONICAL PROJECT STRUCTURE — NEVER DEVIATE

```
project_root/
├── CLAUDE.md                         ← YOU ARE HERE
├── manage.py
├── config/                           ← ALL config — single source of truth
│   ├── settings/
│   │   ├── base.py                   ← Shared settings, no secrets
│   │   ├── development.py            ← Dev overrides
│   │   └── production.py            ← Prod overrides
│   ├── urls.py                       ← ROOT url registry — includes all app urls
│   ├── wsgi.py
│   └── asgi.py
├── apps/                             ← ALL apps live here
│   ├── core/                         ← Shared foundation — inheritable by all apps
│   │   ├── models.py                 ← BaseModel (every model inherits this)
│   │   ├── mixins.py                 ← Shared view mixins
│   │   ├── middleware.py             ← Custom middleware
│   │   ├── context_processors.py    ← Global template context
│   │   ├── utils.py                  ← ALL shared utility functions
│   │   ├── exceptions.py             ← Custom exceptions
│   │   └── templatetags/
│   │       └── core_tags.py          ← ALL shared template tags
│   └── [app_name]/                   ← Self-contained, self-sustained app
│       ├── models.py
│       ├── views.py                  ← Thin orchestration only
│       ├── urls.py                   ← app_name defined here
│       ├── forms.py
│       ├── admin.py
│       ├── signals.py
│       ├── services.py               ← ALL business logic
│       ├── selectors.py              ← ALL database queries
│       ├── apps.py
│       └── tests/
│           ├── __init__.py
│           ├── test_models.py
│           ├── test_views.py
│           └── test_services.py
├── templates/
│   ├── base.html                     ← THE ONE base — all templates extend this
│   ├── partials/                     ← Global HTMX fragments
│   │   ├── _navbar.html
│   │   ├── _footer.html
│   │   ├── _messages.html
│   │   ├── _pagination.html
│   │   ├── _modal.html
│   │   └── _drawer.html
│   └── [app_name]/
│       ├── [model]_list.html
│       ├── [model]_detail.html
│       ├── [model]_form.html
│       └── partials/
│           └── _[fragment].html      ← App HTMX partials
├── static/
│   ├── css/
│   │   ├── custom.css                ← Project overrides only
│   │   └── headless.css              ← HeadlessUI-inspired component styles
│   ├── js/
│   │   └── app.js                    ← ALL Alpine components registered here
│   └── images/
├── staticfiles/                      ← collectstatic output (gitignored)
├── media/                            ← User uploads (gitignored)
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── .env                              ← Secrets (gitignored)
├── .env.example                      ← Committed — all required vars documented
└── docker-compose.yml
```

---

## 📜 THE APP CONTRACT — SACRED, EVERY APP FOLLOWS THIS

### Every App MUST:
- Have its own `urls.py` with `app_name` defined (enables namespacing)
- Have `services.py` — ALL business logic lives here
- Have `selectors.py` — ALL ORM queries live here
- Have `tests/` directory with model, view, and service tests
- Have templates under `templates/[app_name]/`
- Have models inherit from `core.models.BaseModel`
- Be registered in `config/urls.py` via `include()`
- Be listed in `INSTALLED_APPS` as `apps.[app_name]`

### Every App MUST NEVER:
- Import from another app's `views.py`, `forms.py`, or `urls.py`
- Put business logic in views (belongs in services.py)
- Put ORM queries in views (belongs in selectors.py)
- Put logic in templates (belongs in view context or template tags)
- Define its own base template (extend base.html always)
- Import CDN scripts or CSS (base.html does this — once)
- Duplicate any utility already in `apps/core/`

---

## 🏛️ BASE MODEL — ALL MODELS INHERIT THIS, NO EXCEPTIONS

```python
# apps/core/models.py
import uuid
from django.db import models

class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']

class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class SoftDeleteModel(BaseModel):
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    def delete(self, *args, **kwargs):
        self.is_active = False
        self.save(update_fields=['is_active', 'updated_at'])

    class Meta:
        abstract = True
```

---

## 🔗 URL ARCHITECTURE — SINGLE SOURCE OF TRUTH

```python
# config/urls.py — the ONE root, never duplicate
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.core.urls', namespace='core')),
    path('accounts/', include('apps.accounts.urls', namespace='accounts')),
    # Add apps below — follow this exact pattern
    # path('[prefix]/', include('apps.[app].urls', namespace='[app]')),
]

# apps/[app]/urls.py — canonical structure
app_name = '[app]'  # ALWAYS defined — enables {% url 'app:view' %}
urlpatterns = [
    path('', views.IndexView.as_view(), name='index'),
    path('<uuid:pk>/', views.DetailView.as_view(), name='detail'),
    path('create/', views.CreateView.as_view(), name='create'),
    path('<uuid:pk>/update/', views.UpdateView.as_view(), name='update'),
    path('<uuid:pk>/delete/', views.DeleteView.as_view(), name='delete'),
    # HTMX endpoints — always prefixed hx_ in name
    path('hx/list/', views.HxListView.as_view(), name='hx_list'),
    path('hx/search/', views.HxSearchView.as_view(), name='hx_search'),
    path('hx/<uuid:pk>/edit/', views.HxEditView.as_view(), name='hx_edit'),
    path('hx/<uuid:pk>/delete/', views.HxDeleteView.as_view(), name='hx_delete'),
    path('hx/create-form/', views.HxCreateFormView.as_view(), name='hx_create_form'),
]

# Template usage — ALWAYS namespaced, NEVER hardcoded
# {% url 'items:detail' item.pk %}
# hx-get="{% url 'items:hx_edit' item.pk %}"
# Python: reverse('items:detail', kwargs={'pk': item.pk})
```

---

## 🎨 THE ONE BASE.HTML — COPY THIS, DO NOT REINVENT

```html
<!DOCTYPE html>
<html lang="en" x-data="appRoot()" :data-bs-theme="darkMode ? 'dark' : 'light'">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="csrf-token" content="{{ csrf_token }}">
    <title>{% block title %}{{ page_title|default:"App" }}{% endblock %} | {{ site_name|default:"Project" }}</title>
    <meta name="description" content="{% block meta_description %}{% endblock %}">

    <!-- Bootstrap 5.3 — loaded ONCE here, never in child templates -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.css" rel="stylesheet">
    <!-- HeadlessUI-inspired custom component styles -->
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/headless.css' %}">
    <link rel="stylesheet" href="{% static 'css/custom.css' %}">
    {% block extra_css %}{% endblock %}
</head>
<body class="min-vh-100 d-flex flex-column">

    <!-- Global toast mount point -->
    <div id="toast-region" aria-live="polite" aria-atomic="true"
         class="toast-container position-fixed top-0 end-0 p-3" style="z-index:9999"
         x-data="toastManager()" @toast.window="add($event.detail)">
        <template x-for="toast in toasts" :key="toast.id">
            <div class="toast show align-items-center" :class="`text-bg-${toast.type}`">
                <div class="d-flex">
                    <div class="toast-body" x-text="toast.message"></div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto"
                            @click="remove(toast.id)"></button>
                </div>
            </div>
        </template>
    </div>

    <!-- HTMX Django messages (OOB swap target) -->
    <div id="django-messages" hx-swap-oob="true">
        {% include 'partials/_messages.html' %}
    </div>

    <!-- Global modal mount -->
    <div id="modal-region" x-data="modalManager()">
        {% include 'partials/_modal.html' %}
    </div>

    <!-- Global drawer/sidebar mount -->
    <div id="drawer-region" x-data="drawerManager()">
        {% include 'partials/_drawer.html' %}
    </div>

    {% include 'partials/_navbar.html' %}

    <main class="flex-grow-1">
        {% block content %}{% endblock %}
    </main>

    {% include 'partials/_footer.html' %}

    <!-- Scripts — loaded ONCE here, never duplicated in child templates -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js"></script>
    <script src="https://unpkg.com/alpinejs@3.14.1/dist/cdn.min.js" defer></script>
    <script src="{% static 'js/app.js' %}"></script>

    <!-- HTMX global CSRF config -->
    <script>
        htmx.config.globalViewTransitions = true;
        document.addEventListener('htmx:configRequest', (e) => {
            e.detail.headers['X-CSRFToken'] = document.querySelector('meta[name="csrf-token"]').content;
        });
    </script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

---

## 🧊 HEADLESSUI COMPONENT REGISTRY

HeadlessUI provides accessible, unstyled components. We clone their behaviour and accessibility patterns, styled with Bootstrap 5 + custom CSS. Alpine.js drives the interactivity. Every component follows the 3-part contract below.

### Component Status Board (Update as components are built):

| HeadlessUI Component | Alpine Function | Template Partial | CSS Class | Status |
|---|---|---|---|---|
| Dialog (Modal) | `modalManager()` | `partials/_modal.html` | `.hl-modal` | [ ] |
| Disclosure (Accordion) | `disclosure()` | inline | `.hl-disclosure` | [ ] |
| Listbox (Select) | `listbox()` | inline | `.hl-options` | [ ] |
| Combobox (Autocomplete) | `combobox()` | `partials/_combobox.html` | `.hl-combobox` | [ ] |
| Menu (Dropdown) | `dropdown()` | inline | `.hl-menu` | [ ] |
| Popover | `popover()` | inline | `.hl-popover` | [ ] |
| RadioGroup | `radioGroup()` | inline | `.hl-radio` | [ ] |
| Switch (Toggle) | `switchToggle()` | inline | `.hl-switch` | [ ] |
| Tabs | `tabs()` | inline | `.hl-tabs` | [ ] |
| Transition | `x-transition` directives | inline | `.hl-enter` | [ ] |
| Command Palette | `commandPalette()` | `partials/_command.html` | `.hl-command` | [ ] |
| Notification (Toast) | `toastManager()` | `partials/_messages.html` | `.hl-toast` | [ ] |
| Drawer/SlideOver | `drawerManager()` | `partials/_drawer.html` | `.hl-drawer` | [ ] |

### 3-Part Component Contract — Follow For Every HeadlessUI Component:
- **Part 1** — Alpine function in `static/js/app.js` (behaviour + state + keyboard nav)
- **Part 2** — HTML in `templates/partials/` or inline (structure + ARIA attributes)
- **Part 3** — CSS in `static/css/headless.css` (transitions + visual states)

---

## 🔄 COMPLETE static/js/app.js — THE ONE ALPINE REGISTRY

```javascript
// static/js/app.js
// THE single Alpine component registry — never split, never duplicate

// ─── ROOT APP STATE ──────────────────────────────────────────────────────────
function appRoot() {
    return {
        darkMode: localStorage.getItem('darkMode') === 'true',
        sidebarOpen: false,
        init() {
            document.documentElement.setAttribute('data-bs-theme', this.darkMode ? 'dark' : 'light');
        },
        toggleDark() {
            this.darkMode = !this.darkMode;
            localStorage.setItem('darkMode', this.darkMode);
            document.documentElement.setAttribute('data-bs-theme', this.darkMode ? 'dark' : 'light');
        }
    }
}

// ─── MODAL MANAGER ──────────────────────────────────────────────────────────
function modalManager() {
    return {
        open: false, title: '', size: 'md',
        show(config = {}) {
            this.title = config.title || '';
            this.size = config.size || 'md';
            this.open = true;
            document.body.style.overflow = 'hidden';
        },
        close() {
            this.open = false;
            document.body.style.overflow = '';
        }
    }
}

// ─── DRAWER / SLIDEOVER ──────────────────────────────────────────────────────
function drawerManager() {
    return {
        open: false, side: 'right', title: '',
        show(config = {}) {
            this.side = config.side || 'right';
            this.title = config.title || '';
            this.open = true;
            document.body.style.overflow = 'hidden';
        },
        close() { this.open = false; document.body.style.overflow = ''; }
    }
}

// ─── TOAST MANAGER ──────────────────────────────────────────────────────────
function toastManager() {
    return {
        toasts: [],
        add(detail) {
            const id = Date.now();
            this.toasts.push({ id, message: detail.message || detail, type: detail.type || 'success' });
            setTimeout(() => this.remove(id), detail.duration || 4000);
        },
        remove(id) { this.toasts = this.toasts.filter(t => t.id !== id); }
    }
}
// Global helper — call from anywhere: dispatchToast('Saved!', 'success')
function dispatchToast(message, type = 'success', duration = 4000) {
    window.dispatchEvent(new CustomEvent('toast', { detail: { message, type, duration } }));
}
// HTMX hook — auto-fire toast from HX-Trigger header in Django views
document.addEventListener('htmx:afterRequest', (e) => {
    const trigger = e.detail.xhr.getResponseHeader('HX-Trigger');
    if (trigger) {
        try {
            const data = JSON.parse(trigger);
            if (data.showToast) dispatchToast(data.showToast.message, data.showToast.type);
        } catch {}
    }
});

// ─── LISTBOX — HeadlessUI Select clone ──────────────────────────────────────
function listbox(config = {}) {
    return {
        open: false,
        selected: config.initial || null,
        activeIndex: 0,
        options: config.options || [],
        labelKey: config.labelKey || 'label',
        valueKey: config.valueKey || 'value',
        toggle() { this.open = !this.open; },
        close() { this.open = false; },
        select(option) {
            this.selected = option;
            this.close();
            this.$dispatch('listbox-change', { value: option[this.valueKey] });
        },
        isSelected(option) {
            return this.selected && this.selected[this.valueKey] === option[this.valueKey];
        },
        handleKeydown(e) {
            if (!this.open && ['Enter', ' ', 'ArrowDown'].includes(e.key)) { e.preventDefault(); this.open = true; return; }
            if (e.key === 'Escape') { this.close(); return; }
            if (e.key === 'ArrowDown') { e.preventDefault(); this.activeIndex = Math.min(this.activeIndex + 1, this.options.length - 1); }
            if (e.key === 'ArrowUp') { e.preventDefault(); this.activeIndex = Math.max(this.activeIndex - 1, 0); }
            if (e.key === 'Enter' && this.open) { e.preventDefault(); this.select(this.options[this.activeIndex]); }
        }
    }
}

// ─── COMBOBOX — HeadlessUI Autocomplete clone ────────────────────────────────
function combobox(config = {}) {
    return {
        open: false, query: '', selected: config.initial || null, loading: false,
        close() { this.open = false; },
        clear() { this.query = ''; this.selected = null; this.$dispatch('combobox-clear'); },
        onSelect(value) { this.selected = value; this.open = false; this.$dispatch('combobox-change', { value }); }
    }
}

// ─── SWITCH — HeadlessUI Switch clone ───────────────────────────────────────
function switchToggle(initialValue = false) {
    return {
        checked: initialValue,
        toggle() {
            this.checked = !this.checked;
            this.$dispatch('switch-change', { checked: this.checked });
        }
    }
}

// ─── TABS — HeadlessUI Tabs clone ───────────────────────────────────────────
function tabs(config = {}) {
    return {
        activeTab: config.initial || 0,
        setTab(index) { this.activeTab = index; this.$dispatch('tab-change', { index }); },
        isActive(index) { return this.activeTab === index; }
    }
}

// ─── DISCLOSURE — HeadlessUI Disclosure clone ────────────────────────────────
function disclosure(initialOpen = false) {
    return {
        open: initialOpen,
        toggle() { this.open = !this.open; }
    }
}

// ─── DROPDOWN MENU — HeadlessUI Menu clone ───────────────────────────────────
function dropdown() {
    return {
        open: false, activeIndex: -1,
        toggle() { this.open = !this.open; if (this.open) this.activeIndex = 0; },
        close() { this.open = false; this.activeIndex = -1; },
        handleKeydown(e, itemCount) {
            if (e.key === 'Escape') { this.close(); return; }
            if (e.key === 'ArrowDown') { e.preventDefault(); this.activeIndex = Math.min(this.activeIndex + 1, itemCount - 1); }
            if (e.key === 'ArrowUp') { e.preventDefault(); this.activeIndex = Math.max(this.activeIndex - 1, 0); }
        }
    }
}

// ─── RADIO GROUP — HeadlessUI RadioGroup clone ───────────────────────────────
function radioGroup(initial = null) {
    return {
        selected: initial,
        select(value) { this.selected = value; this.$dispatch('radio-change', { value }); },
        isSelected(value) { return this.selected === value; }
    }
}

// ─── COMMAND PALETTE ─────────────────────────────────────────────────────────
function commandPalette() {
    return {
        open: false, query: '', loading: false,
        show() { this.open = true; this.$nextTick(() => this.$refs.input?.focus()); },
        close() { this.open = false; this.query = ''; },
        init() {
            window.addEventListener('keydown', (e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'k') { e.preventDefault(); this.open ? this.close() : this.show(); }
            });
        }
    }
}

// ─── DATA TABLE ──────────────────────────────────────────────────────────────
function dataTable(config = {}) {
    return {
        sortField: config.defaultSort || '',
        sortDir: 'asc',
        selected: new Set(),
        selectAll: false,
        sort(field) {
            this.sortDir = this.sortField === field ? (this.sortDir === 'asc' ? 'desc' : 'asc') : 'asc';
            this.sortField = field;
            this.$dispatch('table-sort', { field: this.sortField, dir: this.sortDir });
        },
        toggleSelectAll(ids) {
            this.selectAll = !this.selectAll;
            this.selected = this.selectAll ? new Set(ids) : new Set();
        },
        toggleSelect(id) { this.selected.has(id) ? this.selected.delete(id) : this.selected.add(id); }
    }
}

// ─── FORM STATE ──────────────────────────────────────────────────────────────
function formState() {
    return {
        loading: false, dirty: false, errors: {},
        setError(field, msg) { this.errors[field] = msg; },
        clearErrors() { this.errors = {}; },
        async submit(url, data, method = 'POST') {
            this.loading = true; this.clearErrors();
            try {
                const res = await fetch(url, {
                    method,
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content
                    },
                    body: JSON.stringify(data)
                });
                const json = await res.json();
                if (!res.ok) { this.errors = json.errors || {}; return json; }
                this.dirty = false;
                return json;
            } finally { this.loading = false; }
        }
    }
}
```

---

## 🎭 static/css/headless.css — HEADLESSUI STYLES

```css
/* static/css/headless.css */
/* HeadlessUI-inspired component styles — Bootstrap 5 integrated */

[x-cloak] { display: none !important; }

/* ── TRANSITIONS ──────────────────────────────────────────────────────────── */
.hl-enter { transition: opacity 150ms ease-out, transform 150ms ease-out; }
.hl-enter-from { opacity: 0; transform: scale(0.95); }
.hl-enter-to { opacity: 1; transform: scale(1); }
.hl-leave { transition: opacity 100ms ease-in, transform 100ms ease-in; }
.hl-leave-from { opacity: 1; transform: scale(1); }
.hl-leave-to { opacity: 0; transform: scale(0.95); }
.hl-slide-enter { transition: opacity 300ms ease-out, transform 300ms ease-out; }
.hl-slide-enter-from { opacity: 0; transform: translateX(100%); }
.hl-slide-enter-to { opacity: 1; transform: translateX(0); }
.hl-slide-leave { transition: opacity 200ms ease-in, transform 200ms ease-in; }
.hl-slide-leave-from { opacity: 1; transform: translateX(0); }
.hl-slide-leave-to { opacity: 0; transform: translateX(100%); }

/* ── BACKDROP ─────────────────────────────────────────────────────────────── */
.hl-backdrop {
    position: fixed; inset: 0; z-index: 1040;
    background: rgba(0, 0, 0, 0.5);
    backdrop-filter: blur(2px);
    -webkit-backdrop-filter: blur(2px);
}

/* ── LISTBOX / COMBOBOX OPTIONS PANEL ────────────────────────────────────── */
.hl-options {
    position: absolute; z-index: 50; width: 100%;
    background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color);
    border-radius: var(--bs-border-radius-lg);
    box-shadow: var(--bs-box-shadow-lg);
    max-height: 260px; overflow-y: auto;
    padding: 4px 0; margin-top: 4px;
}
.hl-option {
    padding: 8px 16px; cursor: pointer;
    display: flex; align-items: center; gap: 8px;
    font-size: 0.9rem; color: var(--bs-body-color);
    transition: background 100ms ease;
}
.hl-option:hover,
.hl-option[data-active="true"] { background: var(--bs-primary-bg-subtle); }
.hl-option[data-selected="true"] { font-weight: 600; color: var(--bs-primary); }
.hl-option[data-selected="true"]::after {
    content: '\F633'; font-family: 'Bootstrap-Icons';
    margin-left: auto; font-size: 0.85rem;
}
.hl-option[data-disabled="true"] { opacity: 0.5; cursor: not-allowed; pointer-events: none; }

/* ── SWITCH / TOGGLE ──────────────────────────────────────────────────────── */
.hl-switch {
    position: relative; display: inline-flex; align-items: center;
    width: 44px; height: 24px; border-radius: 9999px;
    cursor: pointer; outline: none;
    transition: background-color 200ms ease;
    background: var(--bs-secondary-bg);
    border: 2px solid transparent;
}
.hl-switch:focus-visible { box-shadow: 0 0 0 3px rgba(var(--bs-primary-rgb), 0.35); }
.hl-switch[aria-checked="true"] { background: var(--bs-primary); }
.hl-switch-thumb {
    display: block; width: 16px; height: 16px; border-radius: 9999px;
    background: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3);
    transition: transform 200ms ease;
    transform: translateX(2px);
}
.hl-switch[aria-checked="true"] .hl-switch-thumb { transform: translateX(22px); }

/* ── DRAWER / SLIDEOVER ──────────────────────────────────────────────────── */
.hl-drawer {
    position: fixed; top: 0; right: 0; bottom: 0; z-index: 1050;
    width: min(480px, 90vw);
    background: var(--bs-body-bg);
    box-shadow: var(--bs-box-shadow-lg);
    overflow-y: auto; display: flex; flex-direction: column;
}
.hl-drawer-left { right: auto; left: 0; }
.hl-drawer-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid var(--bs-border-color);
    position: sticky; top: 0; background: var(--bs-body-bg); z-index: 1;
}
.hl-drawer-body { padding: 1.5rem; flex: 1; }

/* ── COMMAND PALETTE ──────────────────────────────────────────────────────── */
.hl-command-palette {
    position: fixed; top: 20%; left: 50%; transform: translateX(-50%);
    width: min(640px, 90vw); z-index: 1060;
    background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color);
    border-radius: var(--bs-border-radius-xl);
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3);
    overflow: hidden;
}
.hl-command-input {
    width: 100%; padding: 1rem 1.25rem;
    border: none; border-bottom: 1px solid var(--bs-border-color);
    background: transparent; color: var(--bs-body-color);
    font-size: 1rem; outline: none;
}
.hl-command-results { max-height: 360px; overflow-y: auto; padding: 4px 0; }
.hl-command-item {
    display: flex; align-items: center; gap: 12px;
    padding: 10px 16px; cursor: pointer;
    transition: background 100ms ease;
}
.hl-command-item:hover,
.hl-command-item[data-active="true"] { background: var(--bs-primary-bg-subtle); }
.hl-command-empty { padding: 2rem; text-align: center; color: var(--bs-secondary-color); }

/* ── RADIO GROUP ─────────────────────────────────────────────────────────── */
.hl-radio-option {
    display: flex; align-items: flex-start; gap: 12px;
    padding: 12px 16px; cursor: pointer;
    border: 2px solid var(--bs-border-color);
    border-radius: var(--bs-border-radius-lg);
    transition: border-color 150ms ease, background 150ms ease;
}
.hl-radio-option:hover { border-color: var(--bs-primary); background: var(--bs-primary-bg-subtle); }
.hl-radio-option[data-checked="true"] {
    border-color: var(--bs-primary);
    background: var(--bs-primary-bg-subtle);
}
.hl-radio-dot {
    width: 18px; height: 18px; border-radius: 9999px;
    border: 2px solid var(--bs-border-color); flex-shrink: 0; margin-top: 2px;
    display: flex; align-items: center; justify-content: center;
    transition: border-color 150ms ease;
}
.hl-radio-option[data-checked="true"] .hl-radio-dot { border-color: var(--bs-primary); }
.hl-radio-dot::after {
    content: ''; width: 8px; height: 8px; border-radius: 9999px;
    background: var(--bs-primary); opacity: 0; transition: opacity 150ms ease;
}
.hl-radio-option[data-checked="true"] .hl-radio-dot::after { opacity: 1; }

/* ── TABS ────────────────────────────────────────────────────────────────── */
.hl-tab-list {
    display: flex; border-bottom: 2px solid var(--bs-border-color);
    gap: 0; margin-bottom: 1.5rem;
}
.hl-tab {
    padding: 10px 20px; cursor: pointer; font-weight: 500;
    color: var(--bs-secondary-color); border: none; background: none;
    border-bottom: 2px solid transparent; margin-bottom: -2px;
    transition: color 150ms ease, border-color 150ms ease;
}
.hl-tab:hover { color: var(--bs-primary); }
.hl-tab[aria-selected="true"] { color: var(--bs-primary); border-bottom-color: var(--bs-primary); }

/* ── POPOVER ─────────────────────────────────────────────────────────────── */
.hl-popover {
    position: absolute; z-index: 50;
    background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color);
    border-radius: var(--bs-border-radius-lg);
    box-shadow: var(--bs-box-shadow-lg);
    padding: 1rem; min-width: 200px;
    margin-top: 8px;
}

/* ── EDITABLE (Inline edit trigger) ─────────────────────────────────────── */
.editable {
    cursor: pointer; border-radius: 4px;
    padding: 2px 6px; transition: background 150ms ease;
}
.editable:hover { background: var(--bs-primary-bg-subtle); }
.editable::after { content: ' \F4CA'; font-family: 'Bootstrap-Icons'; font-size: 0.7em; opacity: 0.5; }

/* ── HTMX INDICATORS ─────────────────────────────────────────────────────── */
.htmx-indicator { opacity: 0; transition: opacity 200ms ease; }
.htmx-request .htmx-indicator { opacity: 1; }
.htmx-request.htmx-indicator { opacity: 1; }
```

---

## 🐍 DJANGO THREE-LAYER PATTERN — CANONICAL, NO DEVIATIONS

```python
# ── LAYER 1: selectors.py — ALL database reads ──────────────────────────────
from django.db.models import QuerySet, Prefetch
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

def get_items(*, user, active_only: bool = True, search: str = '') -> QuerySet:
    qs = Item.objects.filter(user=user).select_related('category').prefetch_related('tags')
    if active_only:
        qs = qs.filter(is_active=True)
    if search:
        vector = SearchVector('name', weight='A') + SearchVector('description', weight='B')
        query = SearchQuery(search, search_type='websearch')
        qs = qs.annotate(rank=SearchRank(vector, query)).filter(rank__gte=0.05).order_by('-rank')
    return qs

def get_item_or_404(*, pk, user) -> 'Item':
    from django.shortcuts import get_object_or_404
    return get_object_or_404(Item, pk=pk, user=user, is_active=True)

# ── LAYER 2: services.py — ALL business logic / writes ──────────────────────
from django.core.exceptions import ValidationError

def create_item(*, user, data: dict) -> 'Item':
    if Item.objects.filter(user=user, name=data['name']).exists():
        raise ValidationError({'name': 'An item with this name already exists.'})
    item = Item(user=user, **data)
    item.full_clean()
    item.save()
    return item

def update_item(*, item: 'Item', data: dict) -> 'Item':
    for field, value in data.items():
        setattr(item, field, value)
    item.full_clean()
    item.save()
    return item

def delete_item(*, item: 'Item') -> None:
    item.delete()  # soft delete via SoftDeleteModel

# ── LAYER 3: views.py — thin orchestration ONLY ─────────────────────────────
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView, View
from django.shortcuts import render, redirect
from django_htmx.http import trigger_client_event

class ItemListView(LoginRequiredMixin, TemplateView):
    template_name = 'items/item_list.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['items'] = selectors.get_items(user=self.request.user, search=self.request.GET.get('q', ''))
        ctx['page_title'] = 'Items'
        return ctx

class HxItemListView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.htmx:
            return redirect('items:index')  # Non-HTMX requests redirected
        items = selectors.get_items(user=request.user, search=request.GET.get('q', ''))
        return render(request, 'items/partials/_item_list.html', {'items': items})

class HxCreateView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.htmx:
            return redirect('items:index')
        return render(request, 'items/partials/_create_form.html', {'form': ItemForm()})

    def post(self, request):
        form = ItemForm(request.POST)
        if form.is_valid():
            try:
                item = services.create_item(user=request.user, data=form.cleaned_data)
                response = render(request, 'items/partials/_item_card.html', {'item': item})
                return trigger_client_event(response, 'showToast', {'message': 'Created!', 'type': 'success'})
            except ValidationError as e:
                form.add_error(None, e)
        return render(request, 'items/partials/_create_form.html', {'form': form}, status=422)

# Model — zero business logic, only properties
class Item(BaseModel):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='items')
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = 'Item'
        indexes = [models.Index(fields=['user', 'is_active', 'created_at'])]

    def __str__(self): return self.name
    def get_absolute_url(self): return reverse('items:detail', kwargs={'pk': self.pk})
    def save(self, *args, **kwargs):
        if not self.slug: self.slug = slugify(self.name)
        super().save(*args, **kwargs)

# Form — NEVER fields = '__all__'
class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['name', 'description', 'category']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }
```

---

## 🌐 HTMX CANONICAL PATTERNS

```html
<!-- ── LIVE SEARCH ────────────────────────────────────────────────────────── -->
<input type="search" name="q" class="form-control"
       hx-get="{% url 'items:hx_list' %}"
       hx-trigger="keyup changed delay:300ms, search"
       hx-target="#results" hx-swap="innerHTML"
       hx-indicator="#search-spinner">
<span id="search-spinner" class="htmx-indicator spinner-border spinner-border-sm text-primary ms-2"></span>
<div id="results"></div>

<!-- ── INFINITE SCROLL ────────────────────────────────────────────────────── -->
{% if page_obj.has_next %}
<div hx-get="{% url 'items:hx_list' %}?page={{ page_obj.next_page_number }}"
     hx-trigger="revealed" hx-swap="outerHTML" hx-indicator="#load-spinner">
    <div id="load-spinner" class="text-center py-4 htmx-indicator">
        <div class="spinner-border text-primary"></div>
    </div>
</div>
{% endif %}

<!-- ── INLINE EDIT ────────────────────────────────────────────────────────── -->
<span id="item-{{ item.pk }}-name" class="editable"
      hx-get="{% url 'items:hx_edit' item.pk %}"
      hx-trigger="dblclick" hx-target="#item-{{ item.pk }}-name" hx-swap="outerHTML"
      title="Double-click to edit">{{ item.name }}</span>

<!-- ── OPTIMISTIC DELETE ──────────────────────────────────────────────────── -->
<button hx-delete="{% url 'items:hx_delete' item.pk %}"
        hx-target="#item-{{ item.pk }}" hx-swap="outerHTML swap:300ms"
        hx-confirm="Delete this item?"
        class="btn btn-sm btn-outline-danger">
    <i class="bi bi-trash"></i>
</button>

<!-- ── MODAL TRIGGER ──────────────────────────────────────────────────────── -->
<button hx-get="{% url 'items:hx_create_form' %}"
        hx-target="#modal-body" hx-swap="innerHTML"
        @click="$dispatch('open-modal', { title: 'Create Item' })"
        class="btn btn-primary">
    <i class="bi bi-plus-lg me-1"></i>Add Item
</button>

<!-- ── POLLING (real-time feel) ──────────────────────────────────────────── -->
<div hx-get="{% url 'dashboard:hx_stats' %}" hx-trigger="every 30s" hx-swap="innerHTML">
    {% include 'dashboard/partials/_stats.html' %}
</div>

<!-- ── BOOSTED NAVIGATION (SPA feel) ─────────────────────────────────────── -->
<nav hx-boost="true" hx-push-url="true">
    <a href="{% url 'items:index' %}" class="nav-link">Items</a>
    <a href="{% url 'dashboard:index' %}" class="nav-link">Dashboard</a>
</nav>

<!-- ── FORM WITH HTMX + Alpine validation ────────────────────────────────── -->
<form hx-post="{% url 'items:hx_create_form' %}"
      hx-target="#create-form-region" hx-swap="innerHTML"
      x-data="formState()" @submit="loading = true">
    <div class="mb-3">
        <label class="form-label">Name</label>
        <input name="name" class="form-control" :class="{ 'is-invalid': errors.name }">
        <div class="invalid-feedback" x-text="errors.name"></div>
    </div>
    <button type="submit" class="btn btn-primary" :disabled="loading">
        <span x-show="loading" class="spinner-border spinner-border-sm me-1"></span>
        <span x-text="loading ? 'Saving...' : 'Save'"></span>
    </button>
</form>
```

---

## 🗃️ POSTGRESQL CANONICAL PATTERNS

```python
# selectors.py — advanced PostgreSQL patterns

# Full-text search
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank, TrigramSimilarity

def full_text_search(*, qs, query: str, fields: list) -> QuerySet:
    vector = sum(SearchVector(f) for f in fields)
    sq = SearchQuery(query, search_type='websearch')
    return qs.annotate(rank=SearchRank(vector, sq)).filter(rank__gte=0.05).order_by('-rank')

# Fuzzy/trigram search — requires pg_trgm extension
def fuzzy_search(*, qs, query: str, field: str, threshold: float = 0.3) -> QuerySet:
    return qs.annotate(sim=TrigramSimilarity(field, query)).filter(sim__gte=threshold).order_by('-sim')

# JSONB queries
def filter_by_metadata(*, qs, key: str, value) -> QuerySet:
    return qs.filter(**{f'metadata__{key}': value})

# Bulk update — never one by one
def bulk_activate(*, ids: list) -> int:
    from django.utils.timezone import now
    return Item.objects.filter(id__in=ids).update(is_active=True, updated_at=now())

# Window functions
from django.db.models import Window, F
from django.db.models.functions import Rank

def get_ranked_items(*, user) -> QuerySet:
    return Item.objects.filter(user=user).annotate(
        position=Window(expression=Rank(), order_by=F('created_at').desc())
    )

# Database settings — config/settings/base.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST', default='localhost'),
        'PORT': env('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'OPTIONS': {'connect_timeout': 10},
    }
}
```

---

## ⚙️ SETTINGS — SINGLE SOURCE OF TRUTH

```python
# config/settings/base.py
import environ
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env()

SECRET_KEY = env('SECRET_KEY')
DEBUG = env('DEBUG')
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.postgres',       # Always — enables PG features
    # Third party
    'django_htmx',
    'django_extensions',
    'crispy_forms',
    'crispy_bootstrap5',
    # Project apps — ALWAYS 'apps.' prefixed
    'apps.core',
    # 'apps.accounts',
    # add more here
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',   # request.htmx detection
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [BASE_DIR / 'templates'],          # centralised templates
    'APP_DIRS': True,
    'OPTIONS': { 'context_processors': [
        'django.template.context_processors.debug',
        'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth',
        'django.contrib.messages.context_processors.messages',
        'apps.core.context_processors.site_settings',
    ]},
}]

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
```

---

## 🔢 NEXT.JS FEATURES → THIS STACK

| Next.js | Django + HTMX + Alpine | Notes |
|---|---|---|
| Server Components | CBV + HTMX partials | Server-rendered, DOM-swapped |
| Client Components | Alpine.js in app.js | HTML-first reactive state |
| App Router | URL namespacing | `app_name` + `include()` |
| `loading.js` | `hx-indicator` + spinner | `.htmx-indicator` CSS class |
| `layout.js` | `base.html` | All pages extend one base |
| Suspense | `hx-trigger="revealed"` | Lazy-load on element reveal |
| SWR polling | `hx-trigger="every Xs"` | Server-sent updates |
| Server Actions | HTMX POST → partial | Form submits, returns fragment |
| View Transitions | `htmx.config.globalViewTransitions` | Native browser transitions |
| Middleware | Django Middleware | `apps/core/middleware.py` |
| `useRouter` push | `hx-push-url="true"` | HTMX updates browser URL |
| Image Optimization | `sorl-thumbnail` | `{% thumbnail img "200x200" %}` |
| i18n | `django.utils.translation` | `{% trans %}` / `gettext_lazy` |
| Auth | `django-allauth` | Social + email + 2FA |
| API Routes | DRF ViewSets | `djangorestframework` |
| ISR / Cache | Django cache framework | `@cache_page` / `cache.set()` |
| Metadata/SEO | `{% block meta %}` in base | Per-page meta tags |
| Command Palette | `commandPalette()` Alpine + HTMX | Ctrl+K global search |
| Dialog | `modalManager()` Alpine | Full accessibility via ARIA |
| Select/Combobox | `listbox()` / `combobox()` Alpine | HeadlessUI-style |
| Notifications | `toastManager()` Alpine | `HX-Trigger` header fires toasts |

---

## 📦 APPROVED PACKAGES

```
# Core
django>=5.0
psycopg2-binary
django-environ

# Frontend
django-htmx

# Forms
django-crispy-forms
crispy-bootstrap5

# Auth
django-allauth

# Filtering
django-filter

# Images
Pillow
sorl-thumbnail

# Dev
django-extensions
django-debug-toolbar

# Testing
pytest-django
factory-boy
model-bakery

# API (if needed)
djangorestframework
drf-spectacular

# Task queue (if needed)
celery[redis]
django-celery-beat

# Performance
whitenoise
django-redis
```

---

## 🧪 TESTING PATTERNS

```python
# conftest.py
import pytest
from model_bakery import baker

@pytest.fixture
def user(db): return baker.make('auth.User', is_active=True)

@pytest.fixture
def client_auth(client, user): client.force_login(user); return client

@pytest.fixture
def htmx_headers(): return {'HTTP_HX_REQUEST': 'true', 'HTTP_HX_TARGET': 'results'}

# test_services.py
@pytest.mark.django_db
class TestItemServices:
    def test_create_success(self, user):
        item = services.create_item(user=user, data={'name': 'Test', 'description': ''})
        assert item.pk is not None

    def test_duplicate_raises(self, user):
        baker.make('items.Item', user=user, name='Dupe')
        with pytest.raises(ValidationError):
            services.create_item(user=user, data={'name': 'Dupe', 'description': ''})

# test_views.py
@pytest.mark.django_db
class TestHxViews:
    def test_requires_login(self, client):
        assert client.get(reverse('items:hx_list')).status_code == 302

    def test_redirects_without_htmx(self, client_auth):
        assert client_auth.get(reverse('items:hx_list')).status_code == 302

    def test_returns_partial_with_htmx(self, client_auth, htmx_headers):
        r = client_auth.get(reverse('items:hx_list'), **htmx_headers)
        assert r.status_code == 200
        assert 'partials' in r.templates[0].name
```

---

## 🛠️ COMMANDS

```bash
# Dev
python manage.py runserver
python manage.py shell_plus --ipython
python manage.py graph_models apps -o schema.png

# DB
python manage.py makemigrations --name=describe_what_changed
python manage.py migrate
python manage.py dbshell

# PostgreSQL extensions (run once in dbshell)
# CREATE EXTENSION IF NOT EXISTS pg_trgm;
# CREATE EXTENSION IF NOT EXISTS unaccent;
# CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

# Static
python manage.py collectstatic --noinput

# Tests
pytest
pytest apps/[app]/tests/ -v
pytest --cov=apps --cov-report=html

# New app (always under apps/)
mkdir -p apps/[name]/tests
touch apps/[name]/__init__.py apps/[name]/tests/__init__.py
python manage.py startapp [name] apps/[name]
# Then create manually: urls.py, services.py, selectors.py
```

---

## 📊 DECISION LOG

| Date | Decision | Reason | Alternatives Rejected |
|---|---|---|---|
| Feb 2025 | Found NO selectors.py pattern | Need to implement per-app selectors | Fat models, fat views |
| Feb 2025 | Models don't inherit BaseModel | Need consistent PKs, timestamps | Current inconsistency |
| Feb 2025 | DB creds hardcoded with defaults | CRITICAL SECURITY ISSUE | Proper .env management needed |
| Feb 2025 | SECRET_KEY has "django-insecure" fallback | CRITICAL SECURITY ISSUE | Must fail in production |
| Feb 2025 | Hardcoded URLs in templates | Maintenance & SEO issue | Must use {% url %} |
| — | CBVs everywhere | Consistent, mixin-composable | FBVs |
| — | services.py + selectors.py | Clean separation of concerns | Fat models / fat views |
| — | UUID primary keys | Security, merge-safe | Integer PKs |
| — | HTMX over React/Vue | Python-native, minimal JS | React, Vue |
| — | Alpine.js for client state | HTML-first, plays well with HTMX | React, vanilla JS |
| — | HeadlessUI cloned to Alpine | Best accessibility + UX patterns | Custom from scratch |
| — | PostgreSQL FTS | Native, no extra infra | Elasticsearch |
| — | Soft deletes | Audit trail, recovery | Hard deletes |
| — | Single app.js for Alpine | One source of truth | Per-component files |
| — | Centralised templates root | Clear structure, no app-level base.html | Per-app templates dirs |

---

## 🧠 LEARNED PATTERNS — GROWS EVERY SESSION

> Claude appends here after every session. [HUMAN CORRECTED] marks human-fixed mistakes.

**FROM AUDIT (Feb 26, 2025):**
- ORM queries scatter across views and services — this project NEEDS selectors.py pattern
- Models don't inherit BaseModel — UUID PKs, created_at/updated_at not standardized
- Hard-coded URLs found in templates: `/admin/` and `/seo/audit/` in base.html — must use {% url 'namespace:name' %}
- DB credentials (user "postgreswl", password "Aa1357") hardcoded with fallback values — MAJOR security issue
- No .env.example provided — cannot run locally without modifying settings.py
- HeadlessUI components (Modal, Tabs, etc.) NOT implemented — only basic Alpine stores
- `hx-swap-oob="true"` required when updating multiple DOM targets from one response
- Always add `[x-cloak] { display: none !important; }` to prevent Alpine flash
- `request.htmx` is falsy for non-HTMX requests — guard with `if not request.htmx: return redirect(...)`
- `HX-Trigger` response header is cleanest way to fire Alpine events (toasts, modal close) from Django
- Bootstrap 5.3 `data-bs-theme` on `<html>` enables native dark mode — Alpine drives the toggle
- `pg_trgm` must be created manually: `CREATE EXTENSION IF NOT EXISTS pg_trgm;`
- `trigger_client_event` from `django_htmx.http` is correct import for HX-Trigger header
**FROM TYPE-HARDENING SESSION (Mar 1, 2026):**
- `Post.objects = PostQuerySet.as_manager()` must be `objects: ClassVar[PostQuerySet] = PostQuerySet.as_manager()  # type: ignore[assignment]` for Pylance to understand custom queryset methods
- All Django view functions must type `request: HttpRequest` explicitly — failure cascades into hundreds of "unknown" errors per untyped parameter
- `ClassVar` must be imported from `typing` even with `from __future__ import annotations`
- `django-stubs` QuerySet methods use `_QS = TypeVar("_QS", bound=QuerySet)` so subclass methods propagate correctly when `objects` is typed as the subclass
- Ruff config: `target-version = "py314"` is wrong if running Python 3.11 — use `"py311"`
- Ruff: migrations should be in `exclude` list to avoid flagging auto-generated code
- pyrightconfig `include` should NOT duplicate paths (`blog` AND `apps` → Pylance analysed blog twice); use only `["apps", "config"]`
- pyrightconfig: `"useLibraryCodeForTypes": true` is crucial for proper Django/Tagulous type resolution
- pyrightconfig: `venvPath` and `venv` settings must be set for Pylance to resolve installed packages
- `"reportUnknownAttributeAccessIssue": false` is not a valid Pylance key — use `"reportAttributeAccessIssue": "warning"` instead
- `SIM103`: `if condition: return False; return True` → `return not condition`; two checks → `return cond1 or cond2`
- `B905`: `zip(a, b)` must have `strict=False` (lengths known different) or `strict=True` (lengths must match) to pass strict ruff
- `PERF401`: Loop-with-append → list comprehension for creation; `list.extend(gen)` for additions to existing list
- `RUF005`: `list1 + [item]` → `[*list1, item]` for unpacking style
- Ruff `isort` (`I` rules) was missing— after adding, `known-first-party` must list all project module names to properly sort internal vs external imports
**FROM PYLANCE SIGNAL SESSION (Mar 1, 2026 Session 2):**
- Django signal handlers: always annotate `sender: type[Any]`, `instance: Any`, `**kwargs: Any` — unannotated triggers ~40 cascade errors per handler
- `evaluate_comment_risk` returns `dict[str, object]` — access via `.get("score", 0)` not tuple unpack; always check return type before unpacking
- `int(result.get("score", 0))  # type: ignore[arg-type]` pattern for `dict[str, object]` to `int` narrowing
- `int(getattr(obj, "field", default))  # type: ignore[arg-type]` pattern to safely narrow `object`-typed getattr results
- `type(instance).objects.filter(...)  # type: ignore[union-attr]` to suppress `type[Any]` ORM access in signal handlers
- Bare `dict` in function signatures → `dict[str, Any]` in strict mode (bare dict = `dict[Unknown, Unknown]`)
- Always add `-> bool` (or appropriate return type) when function has explicit `return True`/`return False` branches
- `emit_platform_webhook` calling side: "partially unknown" error goes away after fixing the callee's parameter type from bare `dict` to `dict[str, Any]`
**FROM TAGULOUS STUBS SESSION (Mar 1, 2026 Session 3):**
- Tagulous has NO type stubs — systematic fix is `typings/tagulous/` directory with `.pyi` files, NOT scattered `cast(Any, ...)` everywhere
- `pyrightconfig.json` key: `"typingsPath": "typings"` — without this, Pylance ignores your typings/ directory
- Tagulous descriptor pattern: `__get__(None, type)` returns the FIELD ITSELF (with `.tag_model`); `__get__(Model, type)` returns the MANAGER (with `.all()`, `.set_tag_string()`)
- Per-model `objects: ClassVar[Manager[SelfType]]` is required in each stub — django's Manager is invariant, so `BaseTagModelManager` (Manager[BaseTagModel]) cannot be assigned to a function returning `QuerySet[TagModel]`
- `TagField(tree=True)` creates a `BaseTagTreeModel` at runtime but Pylance sees `type[BaseTagModel]` — one `# type: ignore[assignment]` narrow at the entry point with a doc comment is the correct pattern
- `post.save()  # type: ignore[misc]` is NECESSARY when Tagulous monkey-patches a model's save() — this is a genuine library limitation unresolvable without stubs for the patched model
- `type: ignore` count in admin_views.py: 20+ → 13, all remaining are genuine gaps (8 × FileField django-stubs, 2 × tree model narrowing, 2 × Tagulous-patched save(), 1 × TextChoices comparison)
- "38,475 code lines" in admin dashboard is the repo stat (Python + HTML + CSS + JS + migrations); actual Python-only app source is ~20,541 lines — already within 15-20k target, no code reduction needed
- *(Claude appends new entries here each session)*
**FROM UI PHASE 0-4 SESSION (Mar 2, 2026 Session 4):**
- `color-mix(in srgb, var(--surface-1) 85%, transparent)` enables glassmorphism with CSS variables without hardcoding any rgba values — works in all major browsers (Chrome 111+, Firefox 113+, Safari 16.2+)
- `.admin-topbar.topbar-elevated` modifier + `transition: box-shadow 200ms, background-color 200ms` on base creates smooth scroll elevation without JS transition management
- Bootstrap 5 `btn-close` + `<button class="modal-component-close-btn btn-close">` mixes framework + custom class safely — BS close icon is purely CSS, not JS
- `display:contents` on Alpine wrapper element (`style="display:contents"`) allows the wrapper div to be invisible to layout while still being an Alpine scope — critical for modal/drawer portals
- `pointer-events:none` on the modal-wrap + `pointer-events:auto` on the inner dialog prevents clicks outside the dialog being silently blocked, while still allowing backdrop click capture
- `animation: comment-reveal 0.32s ease both` + `:nth-child(n+6) { animation-delay: 300ms }` caps stagger at 300ms max — prevents late-loading comments feeling laggy on long threads
- `will-change: transform` on post card images prevents compositor rasterisation on every frame during zoom — only add to elements that actually animate
- Inline styles in CSS templates should NEVER be used for anything that can be expressed as a CSS class EXCEPT: (1) server-calculated `style="width: {{ X }}%"` progress bars; (2) third-party embed requirements (GTM noscript); (3) runtime JS-set dimensions
- `shimmer-slide` keyframe: `left: -100% → left: 200%` for button shimmer needs `overflow: hidden` and `position: relative` on the parent button
- HeadlessUI partials use `x-cloak` + `style="display:contents"` on root to prevent FOUC (flash of unstyled content) — `[x-cloak] { display: none !important }` in headless.css hides the entire structure until Alpine initialises
**FROM META AUTO-SYNC SESSION (Session 5):**
- Meta field auto-sync pattern: use `metaTitleManual` / `metaDescManual` / `canonicalManual` boolean flags. Set `true` only when user manually types a value DIFFERENT from the auto-generated value. This allows clearing the field to re-enable auto-sync.
- Canonical URL auto-generation: `window.location.origin + "/" + slug + "/"` — always use `encodeURIComponent(slug)` for safety. Admin editor uses `/{slug}/`, public post form uses `/{slug}/`, page form uses `/pages/{slug}/` to match URL patterns.
- `maxlength` in HTML inputs MUST match model `max_length` (70 for meta_title, 170 for meta_description) — prior mismatch (60/155 in admin editor) silently truncated user input below model capacity.
- Summernote-aware word counting: prefer reading from `.note-editable` textContent (immediate) over the hidden markdown textarea (delayed by bridge sync). Use `MutationObserver` on `.summernote-bridge-host` for real-time updates as user types in rich editor.
- `.note-modal { z-index: 2050 }` must be higher than `.note-modal-content { z-index: 2000 }` — the overlay wrapper needs to be above the admin sidebar (z-index: 100).
- `.note-statusbar` needs explicit theme styling (`background: var(--surface-2)`, `border-top`) — Summernote default is white which breaks dark mode.
**FROM JS DEDUP + BUGFIX SESSION (Sessions 6-7):**
- `{# ... #}` Django comments containing `{% url %}` tags STILL trigger `NoReverseMatch` — use `{% comment %}...{% endcomment %}` blocks instead
- Alpine 3 CDN load order: the Alpine CDN script must be LAST after all stores/components; store registration must happen inside `document.addEventListener('alpine:init', ...)` NOT at top level
- `style="display:contents"` on Alpine x-data wrapper divs is fragile — if Alpine hasn't initialized, the element is visible with wrong display; better to use `x-cloak` and `[x-cloak] { display: none !important }` which reliably hides until Alpine init
- JS theme logic (dark mode toggle, system preference, localStorage) was duplicated across `admin/core.js`, `site/core.js`, and `alpine-store.js` — consolidated into single `theme-core.js` loaded before Alpine
- `overflow-y: auto` on `.admin-content` wrapper clips ALL absolutely-positioned children (Summernote dropdowns, popovers, tooltips) — NEVER set overflow on a container that holds third-party widgets with dropdown menus
- Summernote `$host.on('summernote.change', ...)` should NOT be re-registered on HTMX `afterSwap` — leads to duplicate listeners; use `$host.off('summernote.change').on(...)` or guard with data attribute
- Template `{# visible comments #}` with `{{` or `{%` inside are NOT actually commented out — Django's comment syntax `{# #}` is single-line only; multi-line requires `{% comment %}`
**FROM SUMMERNOTE ROOT CAUSE FIX SESSION (Session 8 — Current):**
- **ROOT CAUSE IDENTIFIED**: Summernote BS5 creates DOM with Bootstrap classes: `.note-editor.note-frame.card`, `.note-toolbar.card-header`, `.note-btn.btn.btn-outline-secondary.btn-sm`, `.note-editable.card-block`
- Global `.card { padding: var(--space-6) }` bleeds 24px padding into Summernote's outer frame; `.card-header { font-size; font-weight; margin-bottom }` bloats the toolbar; `.btn { padding: 12px 16px; font-size: 16px }` bloats every toolbar button
- Fix: three-layer isolation: (1) CSS `:not()` exclusions on global rules — `.card:not(.note-editor)`, `.btn:not(.note-btn)`, etc.; (2) JS `classList.remove('card')` / `classList.remove('card-header')` / `classList.remove('card-block')` at runtime; (3) Retained `!important` CSS + inline JS `style.setProperty()` as belt-and-suspenders
- When adding `:not(.x)` to a global selector, specificity bumps from 0,1,0 to 0,2,0 — audit ALL overrides of that selector across the project for cascade breakage
- `.btn-xs` using Bootstrap CSS custom properties (`--bs-btn-padding-y`) is overridden by `.btn:not(.note-btn) { padding: ... }` at higher specificity — must convert to explicit `padding` and bump selector to `.btn.btn-xs` (0,2,0) to tie
- To discover the exact DOM structure a third-party widget creates, fetch and read its FULL source JS from CDN — documentation rarely shows the actual renderer templates with Bootstrap class reuse
- `enforceToolbarStyles()` must be called at 4+ points after Summernote init: immediately, 100ms, 500ms, and via `onInit` callback — Summernote's own CSS applies asynchronously across multiple animation frames


---

## 🚨 COMMON PITFALLS — ZERO TOLERANCE, NEVER REPEAT

| ❌ Never | ✅ Always |
|---|---|
| Business logic in views | services.py |
| ORM queries in views | selectors.py |
| Logic in templates | view context or core_tags.py |
| `fields = '__all__'` in forms | List every field explicitly |
| Hardcoded URLs in templates | `{% url 'namespace:name' %}` |
| Hardcoded URLs in Python | `reverse('namespace:name', kwargs={...})` |
| CDN imports in child templates | base.html only — once |
| `<script>` outside `{% block extra_js %}` | Use the block |
| `<style>` outside `{% block extra_css %}` | Use the block |
| Alpine logic > 2 props inline | Extract to named function in app.js |
| Missing `app_name` in urls.py | Every urls.py defines `app_name` |
| N+1 queries (ORM in loop) | select_related / prefetch_related in selectors |
| Secrets in settings | `environ.Env()` from .env |
| Missing `request.htmx` check in HTMX view | Check and redirect |
| Model not inheriting BaseModel | Always inherit BaseModel |
| Cross-app view/form/url imports | Use core/ or Django signals |
| HeadlessUI logic inline in template | Extract to app.js named function |
| Creating utility already in core/ | Check core/utils.py first |
| **[AUDIT FOUND]** DB credentials hardcoded | Use os.getenv() with NO fallback, fail loudly in production |
| **[AUDIT FOUND]** SECRET_KEY with insecure fallback | NEVER have fallback value; fail if not in .env |
| **[AUDIT FOUND]** No selectors.py in any app | Every app MUST have selectors.py for all ORM |
| **[AUDIT FOUND]** No BaseModel inheritance | Every model must inherit core.models.BaseModel |
| **[AUDIT FOUND]** Hardcoded URLs /admin/, /seo/audit/ | Replace with {% url %} or reverse() calls |
| **[TYPE SESSION]** Missing `request: HttpRequest` in view functions | Cascades into 10-20+ downstream unknown-type errors per function | Always annotate `request: HttpRequest` in EVERY view function |
| **[TYPE SESSION]** `Post.objects = PostQuerySet.as_manager()` untyped | Pylance sees `BaseManager[Post]`, blocking all custom queryset methods | `objects: ClassVar[PostQuerySet] = PostQuerySet.as_manager()  # type: ignore[assignment]` |
| **[TYPE SESSION]** pyrightconfig `include` lists both `blog` and `apps` | Pylance analyses `apps/blog` twice causing duplicate diagnostics | Only include `["apps", "config"]` |
| **[TYPE SESSION]** ruff `target-version` mismatch with actual Python | UP rules flag valid 3.11 syntax as "old" or vice versa | Match `target-version` to your actual Python version |
| **[TYPE SESSION]** `logger = getLogger(...)` placed before imports | Causes E402 "module level import not at top of file" | Place `logger =` AFTER all imports |
| **[SUMMERNOTE ROOT CAUSE]** Global `.card`/`.btn` rules bleed into Summernote | Summernote BS5 reuses `.card`, `.card-header`, `.btn`, `.btn-sm` Bootstrap classes on its DOM — global overrides for these classes corrupt the editor | Use `:not(.note-editor)` / `:not(.note-btn)` / `:not(.note-toolbar)` on global rules + JS `classList.remove()` |
| **[SUMMERNOTE ROOT CAUSE]** CSS `!important` isolation alone insufficient | Even with `!important` overrides, global padding/font-size from shared Bootstrap classes still applies first paint causing FOUC before JS corrects it | Prevent bleeding at source with `:not()` selectors; keep `!important` + JS as backup only |
| **[SPECIFICITY]** Adding `:not()` bumps specificity from 0,1,0 to 0,2,0 | Downstream selectors at 0,1,0 or 0,1,1 that override the base rule silently lose | Audit ALL overrides after adding `:not()` to a widely-used selector |
| *(Human corrections appended here)* | |

---

## 🎯 ACTIVE CONTEXT — UPDATE EVERY SESSION

```
Last Updated:     Mar 2, 2026 (Session 8 — Summernote Root Cause Fix)
Session Type:     BUGFIX — Summernote CSS root cause + JS dedup + meta auto-sync (Sessions 5-8 cumulative)
Working On:       static/css/components.css, static/js/summernote-bridge.js, static/css/admin/control.css
Current App:      Frontend CSS/JS (cross-cutting)
Status:           ✅ COMPLETE — root cause identified and three-layer fix applied
Blocked By:       Nothing critical
Next Steps:
  1. BaseModel migration for remaining models (Agent 1 — HIGH)
  2. HeadlessUI partials 4-13: Disclosure, Listbox, Combobox, Menu, Popover, RadioGroup, Switch, Tabs, Transition, CommandPalette (Agent 3)
  3. Test suite expansion (Agent 6)
Open Questions:   None blocking
Last Commit:      "fix: root-cause Summernote CSS isolation via :not() exclusions + class stripping"

SESSION 8 CHANGES (Current — Summernote Root Cause Fix):
  DISCOVERY:
    - Fetched full Summernote BS5 source from CDN (~700KB) — found exact renderer templates
    - Summernote intentionally applies .card, .card-header, .btn, .btn-sm, .card-block Bootstrap classes
    - Our global CSS for these classes (padding, font-size, font-weight, margin) bled into Summernote DOM
  MODIFIED:
    - static/css/components.css: .card → .card:not(.note-editor), .card-header → .card-header:not(.note-toolbar),
      .btn → .btn:not(.note-btn), .btn-sm → .btn-sm:not(.note-btn), .btn i/svg → .btn:not(.note-btn) i/svg
    - static/js/summernote-bridge.js: enforceToolbarStyles() now also does classList.remove("card"),
      classList.remove("card-header"), classList.remove("card-block")
    - static/css/admin/control.css: .btn-xs converted from CSS custom properties to explicit padding
      (was dead due to .btn:not(.note-btn) specificity bump)

SESSION 5-7 CHANGES (Previously undocumented):
  Commits: 1fcf121, 92f65ef, 4115c35, ca5f581, 1490fd9, 1926e17, b343efc, 8609756, 80fd164
  CREATED:
    - static/js/theme-core.js: Consolidated dark mode logic from 3 files into single source
    - templates/pages/page_form.html: Public page form with meta auto-sync
  MODIFIED:
    - static/js/admin/core.js: Slimmed ~200 lines — theme logic extracted to theme-core.js
    - static/js/site/core.js: Slimmed ~200 lines — theme logic extracted to theme-core.js
    - static/js/alpine-store.js: Cleaned up duplicate theme state
    - static/js/summernote-bridge.js: Added enforceToolbarStyles() with inline !important + onInit callback
    - static/css/components.css: Added Summernote isolation rules (~80 lines !important CSS)
    - static/css/layout.css: Removed overflow-y:auto from .admin-content (Summernote dropdown clipping fix)
    - templates/admin/base_site.html: Fixed Alpine CDN load order (last after stores), added theme-core.js
    - templates/admin/posts/editor.html: Meta auto-sync (title/desc/canonical), Summernote word counting
    - templates/blog/post_form.html: Meta auto-sync fields
    - templates/partials/_toast_stack.html: x-cloak fix (replaced display:contents)
    - templates/admin/comments/list.html, groups/list.html, pages/list.html, posts/list.html,
      taxonomy/categories_list.html, flat_list.html, users/list.html: Fixed {# #} → {% comment %} blocks
    - templates/admin/settings.html, seo/admin/base.html: Removed stale inline styles
    - config/urls.py: Registered debug_toolbar URLs under __debug__/ when DEBUG=True

FILES CHANGED IN SESSION 4:
  CREATED:
    - static/js/app.js: Alpine.data registry (16 components + dispatchToast, countUp, scroll-animate, HTMX hooks)
    - static/css/animations.css: 28 keyframes + utility classes + reduced-motion
    - static/css/headless.css: full HeadlessUI CSS (backdrop, modal, drawer, toast-stack, listbox, switch, tabs, disclosure, menu, combobox, radio-group, command-palette, popover, skeleton, editable, tag-chips, seo-score-ring, form-char-counter)
    - templates/partials/_modal.html: HeadlessUI modal partial (modalManager-driven)
    - templates/partials/_toast_stack.html: HeadlessUI toast stack (toastManager-driven)
    - templates/partials/_drawer.html: HeadlessUI drawer / slideover (drawerManager-driven)
  UPDATED:
    - templates/base.html: +animations.css, +headless.css, +app.js, 3 HeadlessUI includes, logout form d-inline fix
    - config/settings/production.py: whitenoise added to MIDDLEWARE
    - config/settings/development.py: debug_toolbar conditional block added
    - templates/admin/dashboard.html: all 20 inline styles → CSS classes, <style> block removed
    - templates/admin/posts/editor.html: all 29 inline styles → CSS classes, <style> block removed
    - templates/components/*.html (6 files): all inline styles → CSS classes
    - templates/components/button.html, badge.html: inline styles removed
    - 15+ additional admin/seo/pages/blog templates: remaining inline styles eliminated
    - static/css/admin/workspace.css: +400 lines (dashboard classes, editor classes, micro-interactions, .is-removing)
    - static/css/components.css: +280 lines (component classes, button micro-interactions, skeleton)
    - static/css/layout.css: .topbar-elevated glassmorphism state added to .admin-topbar
    - static/css/site/core.css: Phase 3 public micro-interactions (image zoom, progress glow, comment stagger, reaction spring, scroll-animate)
    - static/js/admin/workspace.js: Ctrl+S shortcut + htmx:beforeSwap row animation
    - static/js/admin/core.js: bindTopbarScrollElevation() added + called on DOMContentLoaded

PHASE SUMMARY:
  ✅ Phase 0 — Foundation: animations.css, headless.css, app.js created; base.html wired
  ✅ Phase 1 — Zero inline styles: all 71 inline styles across 20+ templates eliminated (3 legitimate dynamic/GTM remain)
  ✅ Phase 2 — Admin micro-interactions: topbar glassmorphism, row-remove animation, Ctrl+S, stat-card hover lift, KPI row hover
  ✅ Phase 3 — Public micro-interactions: post-card image zoom, reading-progress glow, comment stagger, reaction spring, scroll-animate
  ✅ Phase 4 — HeadlessUI HTML partials: modal, toast-stack, drawer (MVP set) wired into base.html

RUFF STATUS: ✅ "All checks passed!" (0 violations)
PYLANCE STATUS: ✅ (unchanged — 0 errors from Session 3 carried forward)

COMPLETED ACROSS ALL SESSIONS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Post.objects: ClassVar[PostQuerySet] — ~50+ cascade Pylance errors fixed
✅ 36 admin_views.py functions annotated with request: HttpRequest
✅ 32 views.py functions annotated with request: HttpRequest
✅ Ruff 9 rule categories, 0 violations
✅ pyrightconfig.json: venvPath, useLibraryCodeForTypes, correct includes
✅ Silent exceptions log via logger.warning — zero silent failures
✅ SSE WSGI blocking stream → polling endpoint
✅ Post model: is_published, get_reading_time_display(), can_be_edited_by()
✅ apps/blog/signals.py: all params typed, TextChoices fixed, evaluate_comment_risk call corrected
✅ apps/core/integrations.py: dict[str, Any] payload, -> bool return type
✅ handler404 + handler500 in urls.py + views.py + error templates
✅ site_appearance() context processor: 5 DB hits/request → 0 (cached 5 min)
✅ get_category_max_depth() cached with 5-min TTL
✅ SeoRedirectRule save/delete invalidates middleware redirect cache
✅ INTERNAL_IPS in development.py
✅ SESSION_ENGINE=cache + whitenoise in production.py + MIDDLEWARE
✅ get_all_tags_with_counts() alias in tags/selectors.py
✅ .env.example comprehensive rewrite
✅ AGENTS.md: single canonical version, onboarding guide, feature-add guides
✅ SECRET_KEY raises ValueError (already hardened — no fallback)
✅ POSTGRES_* raises ValueError (already hardened — no fallback)
✅ selectors.py pattern fully applied in all apps (blog, seo, comments, tags, pages)
✅ typings/tagulous/ stub package: TagField/SingleTagField descriptors + tree model attributes
✅ admin_views.py: cast(Any) × 7 eliminated; type:ignore[union-attr] × 8 eliminated; cast import removed
✅ animations.css, headless.css, app.js created (Phase 0)
✅ 71 inline styles across 20+ templates eliminated (Phase 1) — 3 legitimate remain
✅ Admin micro-interactions: topbar glassmorphism, .is-removing row animation, Ctrl+S, hover states (Phase 2)
✅ Public micro-interactions: image zoom, progress glow, comment stagger, reaction spring (Phase 3)
✅ HeadlessUI HTML partials: _modal.html, _toast_stack.html, _drawer.html wired into base.html (Phase 4 MVP)
✅ JS theme dedup: theme-core.js consolidates dark mode from admin/core.js + site/core.js + alpine-store.js
✅ Meta auto-sync: editor.html, post_form.html, page_form.html — title/desc/canonical auto-generate from slug
✅ {# #} Django comment fix → {% comment %} blocks (prevented NoReverseMatch)
✅ Alpine CDN load order fixed — CDN last, stores in alpine:init listener
✅ overflow-y:auto removed from .admin-content — fixed Summernote dropdown clipping
✅ Summernote root cause fix: :not() exclusions on .card/.btn/.card-header + JS class stripping
✅ .btn-xs specificity fix: explicit padding at .btn.btn-xs (0,2,0) to compete with :not() bump

REMAINING ISSUES (Known/Accepted):
🟡 HeadlessUI components: 3/13 partials MVP'd (_modal, _toast_stack, _drawer) — remaining 10 not started (Agent 3 — MEDIUM)
🟠 BaseModel not inherited by all models — pending migration planning (Agent 1 — HIGH)
3 remaining style= are all legitimate (2 dynamic server %widths + 1 GTM noscript)
```

---

## 📌 THE 15 GOLDEN LAWS
 1. ONE base.html — everything inherits it
 2. ONE config/urls.py — all app urls included here
 3. ONE services.py per app — all business logic
 4. ONE selectors.py per app — all ORM queries
 5. ONE apps/core/ — all shared utilities, tags, mixins, base models
 6. ONE static/js/app.js — all Alpine components
 7. ONE static/css/headless.css — all HeadlessUI component styles
 8. ZERO business logic in views, models, or templates
 9. ZERO hardcoded URLs — {% url %} and reverse() everywhere
10. ZERO duplication — exists twice = belongs in core
11. ZERO N+1 queries — select_related / prefetch_related always
12. ZERO secrets in code — .env always
13. ZERO cross-app direct imports — use core/ or signals
14. ALL apps self-contained under apps/ with app_name in urls.py
15. ALL HeadlessUI components = app.js function + HTML partial + headless.css
```

---

*Living document. Claude grows it every session. Team grows it. Never becomes stale.*
*Audit: ✅ | HeadlessUI: 3/13 MVP | Last session: Mar 2 2026 — Session 8 Summernote root cause fix | Model: Sonnet / Opus / Haiku*