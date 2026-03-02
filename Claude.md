# CLAUDE.md — Enterprise Copilot · Self-Learning · Living Knowledge Base
# Stack: Django · HTMX · Alpine.js · Bootstrap 5 · PostgreSQL · Celery · HeadlessUI-inspired Components
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

## 🏗️ PROJECT OVERVIEW

```
Project:        DjangoBlog — Full-stack blog/CMS with Django + HTMX + Alpine + Bootstrap
Django:         6.0.2
Python:         3.14
HTMX:           2.0.8
Alpine.js:      3.15.8
Bootstrap:      5.3.8
PostgreSQL:     16+
Celery:         5.x (Redis broker)
Apps:           blog, comments, core, pages, seo, tags (6 apps)
Status:         Production-ready, SEO engine v2 operational
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
│   │   └── production.py             ← Prod overrides
│   ├── urls.py                       ← ROOT url registry — includes all app urls
│   ├── wsgi.py
│   └── asgi.py
├── apps/                             ← ALL apps live here
│   ├── core/                         ← Shared foundation — inheritable by all apps
│   │   ├── models.py                 ← BaseModel (every model inherits this)
│   │   ├── mixins.py                 ← Shared view mixins
│   │   ├── middleware.py             ← Custom middleware
│   │   ├── context_processors.py     ← Global template context
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
├── typings/                          ← Custom type stubs (e.g. tagulous/)
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

### Component Status Board

| HeadlessUI Component | Alpine Function | Template Partial | CSS Class | Status |
|---|---|---|---|---|
| Dialog (Modal) | `modalManager()` | `partials/_modal.html` | `.hl-modal` | ✅ |
| Notification (Toast) | `toastManager()` | `partials/_toast_stack.html` | `.hl-toast` | ✅ |
| Drawer/SlideOver | `drawerManager()` | `partials/_drawer.html` | `.hl-drawer` | ✅ |
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
        open: false, selected: config.initial || null, activeIndex: 0,
        options: config.options || [], labelKey: config.labelKey || 'label', valueKey: config.valueKey || 'value',
        toggle() { this.open = !this.open; },
        close() { this.open = false; },
        select(option) { this.selected = option; this.close(); this.$dispatch('listbox-change', { value: option[this.valueKey] }); },
        isSelected(option) { return this.selected && this.selected[this.valueKey] === option[this.valueKey]; },
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
        toggle() { this.checked = !this.checked; this.$dispatch('switch-change', { checked: this.checked }); }
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
    return { open: initialOpen, toggle() { this.open = !this.open; } }
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
        sortField: config.defaultSort || '', sortDir: 'asc', selected: new Set(), selectAll: false,
        sort(field) {
            this.sortDir = this.sortField === field ? (this.sortDir === 'asc' ? 'desc' : 'asc') : 'asc';
            this.sortField = field;
            this.$dispatch('table-sort', { field: this.sortField, dir: this.sortDir });
        },
        toggleSelectAll(ids) { this.selectAll = !this.selectAll; this.selected = this.selectAll ? new Set(ids) : new Set(); },
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
                    method, headers: { 'Content-Type': 'application/json', 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
                    body: JSON.stringify(data)
                });
                const json = await res.json();
                if (!res.ok) { this.errors = json.errors || {}; return json; }
                this.dirty = false; return json;
            } finally { this.loading = false; }
        }
    }
}

// ─── READING PROGRESS ────────────────────────────────────────────────────────
function readingProgress() {
    return {
        progress: 0,
        _handler: null,
        init() {
            this._handler = () => {
                const el = document.documentElement;
                this.progress = Math.min(100, Math.round((el.scrollTop / (el.scrollHeight - el.clientHeight)) * 100));
            };
            window.addEventListener('scroll', this._handler, { passive: true });
        },
        destroy() { if (this._handler) window.removeEventListener('scroll', this._handler); }
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
    backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);
}

/* ── LISTBOX / COMBOBOX OPTIONS PANEL ────────────────────────────────────── */
.hl-options {
    position: absolute; z-index: 50; width: 100%;
    background: var(--bs-body-bg); border: 1px solid var(--bs-border-color);
    border-radius: var(--bs-border-radius-lg); box-shadow: var(--bs-box-shadow-lg);
    max-height: 260px; overflow-y: auto; padding: 4px 0; margin-top: 4px;
}
.hl-option {
    padding: 8px 16px; cursor: pointer; display: flex; align-items: center; gap: 8px;
    font-size: 0.9rem; color: var(--bs-body-color); transition: background 100ms ease;
}
.hl-option:hover, .hl-option[data-active="true"] { background: var(--bs-primary-bg-subtle); }
.hl-option[data-selected="true"] { font-weight: 600; color: var(--bs-primary); }
.hl-option[data-selected="true"]::after { content: '\F633'; font-family: 'Bootstrap-Icons'; margin-left: auto; font-size: 0.85rem; }
.hl-option[data-disabled="true"] { opacity: 0.5; cursor: not-allowed; pointer-events: none; }

/* ── SWITCH / TOGGLE ──────────────────────────────────────────────────────── */
.hl-switch {
    position: relative; display: inline-flex; align-items: center;
    width: 44px; height: 24px; border-radius: 9999px; cursor: pointer; outline: none;
    transition: background-color 200ms ease; background: var(--bs-secondary-bg); border: 2px solid transparent;
}
.hl-switch:focus-visible { box-shadow: 0 0 0 3px rgba(var(--bs-primary-rgb), 0.35); }
.hl-switch[aria-checked="true"] { background: var(--bs-primary); }
.hl-switch-thumb {
    display: block; width: 16px; height: 16px; border-radius: 9999px; background: white;
    box-shadow: 0 1px 3px rgba(0, 0, 0, 0.3); transition: transform 200ms ease; transform: translateX(2px);
}
.hl-switch[aria-checked="true"] .hl-switch-thumb { transform: translateX(22px); }

/* ── DRAWER / SLIDEOVER ──────────────────────────────────────────────────── */
.hl-drawer {
    position: fixed; top: 0; right: 0; bottom: 0; z-index: 1050;
    width: min(480px, 90vw); background: var(--bs-body-bg); box-shadow: var(--bs-box-shadow-lg);
    overflow-y: auto; display: flex; flex-direction: column;
}
.hl-drawer-left { right: auto; left: 0; }
.hl-drawer-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem 1.5rem; border-bottom: 1px solid var(--bs-border-color);
    position: sticky; top: 0; background: var(--bs-body-bg); z-index: 1;
}
.hl-drawer-body { padding: 1.5rem; flex: 1; }

/* ── COMMAND PALETTE ──────────────────────────────────────────────────────── */
.hl-command-palette {
    position: fixed; top: 20%; left: 50%; transform: translateX(-50%);
    width: min(640px, 90vw); z-index: 1060; background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color); border-radius: var(--bs-border-radius-xl);
    box-shadow: 0 25px 50px rgba(0, 0, 0, 0.3); overflow: hidden;
}
.hl-command-input {
    width: 100%; padding: 1rem 1.25rem; border: none;
    border-bottom: 1px solid var(--bs-border-color); background: transparent;
    color: var(--bs-body-color); font-size: 1rem; outline: none;
}
.hl-command-results { max-height: 360px; overflow-y: auto; padding: 4px 0; }
.hl-command-item { display: flex; align-items: center; gap: 12px; padding: 10px 16px; cursor: pointer; transition: background 100ms ease; }
.hl-command-item:hover, .hl-command-item[data-active="true"] { background: var(--bs-primary-bg-subtle); }
.hl-command-empty { padding: 2rem; text-align: center; color: var(--bs-secondary-color); }

/* ── RADIO GROUP ─────────────────────────────────────────────────────────── */
.hl-radio-option {
    display: flex; align-items: flex-start; gap: 12px; padding: 12px 16px; cursor: pointer;
    border: 2px solid var(--bs-border-color); border-radius: var(--bs-border-radius-lg);
    transition: border-color 150ms ease, background 150ms ease;
}
.hl-radio-option:hover { border-color: var(--bs-primary); background: var(--bs-primary-bg-subtle); }
.hl-radio-option[data-checked="true"] { border-color: var(--bs-primary); background: var(--bs-primary-bg-subtle); }
.hl-radio-dot {
    width: 18px; height: 18px; border-radius: 9999px; border: 2px solid var(--bs-border-color);
    flex-shrink: 0; margin-top: 2px; display: flex; align-items: center; justify-content: center;
    transition: border-color 150ms ease;
}
.hl-radio-option[data-checked="true"] .hl-radio-dot { border-color: var(--bs-primary); }
.hl-radio-dot::after { content: ''; width: 8px; height: 8px; border-radius: 9999px; background: var(--bs-primary); opacity: 0; transition: opacity 150ms ease; }
.hl-radio-option[data-checked="true"] .hl-radio-dot::after { opacity: 1; }

/* ── TABS ────────────────────────────────────────────────────────────────── */
.hl-tab-list { display: flex; border-bottom: 2px solid var(--bs-border-color); gap: 0; margin-bottom: 1.5rem; }
.hl-tab {
    padding: 10px 20px; cursor: pointer; font-weight: 500; color: var(--bs-secondary-color);
    border: none; background: none; border-bottom: 2px solid transparent; margin-bottom: -2px;
    transition: color 150ms ease, border-color 150ms ease;
}
.hl-tab:hover { color: var(--bs-primary); }
.hl-tab[aria-selected="true"] { color: var(--bs-primary); border-bottom-color: var(--bs-primary); }

/* ── POPOVER ─────────────────────────────────────────────────────────────── */
.hl-popover {
    position: absolute; z-index: 50; background: var(--bs-body-bg);
    border: 1px solid var(--bs-border-color); border-radius: var(--bs-border-radius-lg);
    box-shadow: var(--bs-box-shadow-lg); padding: 1rem; min-width: 200px; margin-top: 8px;
}

/* ── EDITABLE (Inline edit trigger) ─────────────────────────────────────── */
.editable { cursor: pointer; border-radius: 4px; padding: 2px 6px; transition: background 150ms ease; }
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

<!-- ── LAZY-LOADED TABS ──────────────────────────────────────────────────── -->
<div x-data="tabs()" class="hl-tab-list" role="tablist">
    <button class="hl-tab" :aria-selected="isActive(0)" @click="setTab(0)">Overview</button>
    <button class="hl-tab" :aria-selected="isActive(1)" @click="setTab(1)">Details</button>
</div>
<div x-show="isActive(0)" hx-get="{% url 'items:hx_overview' %}" hx-trigger="intersect once">
    <div class="htmx-indicator"><div class="spinner-border"></div></div>
</div>
<div x-show="isActive(1)" hx-get="{% url 'items:hx_details' %}" hx-trigger="intersect once">
    <div class="htmx-indicator"><div class="spinner-border"></div></div>
</div>
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
        'CONN_HEALTH_CHECKS': True,
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
    'django_celery_beat',
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

# config/settings.py — environment-based routing
import os
env = os.environ.get("DJANGO_ENV", "development")
if env == "production":
    from .settings.production import *
else:
    from .settings.development import *
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
django-solo

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

# HTML Sanitization
nh3

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

# Task queue
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

# DB
python manage.py makemigrations --name=describe_what_changed
python manage.py migrate
python manage.py dbshell

# PostgreSQL extensions (run once in dbshell)
# CREATE EXTENSION IF NOT EXISTS pg_trgm;
# CREATE EXTENSION IF NOT EXISTS unaccent;

# Static
python manage.py collectstatic --noinput

# Tests
pytest
pytest apps/[app]/tests/ -v
pytest --cov=apps --cov-report=html

# SEO backfill
python manage.py seo_backfill --batch-size=50
python manage.py seo_backfill --repair-orphans --dry-run

# New app (always under apps/)
mkdir -p apps/[name]/tests
touch apps/[name]/__init__.py apps/[name]/tests/__init__.py
python manage.py startapp [name] apps/[name]
# Then create manually: urls.py, services.py, selectors.py

# Celery
celery -A config.celery worker -l info
celery -A config.celery beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Lint
ruff check apps/ config/ --output-format=concise
```

---

## 📊 DECISION LOG

| Date | Decision | Reason | Alternatives Rejected |
|---|---|---|---|
| — | CBVs everywhere | Consistent, mixin-composable | FBVs |
| — | services.py + selectors.py | Clean separation of concerns | Fat models / fat views |
| — | UUID primary keys (BaseModel) | Security, merge-safe | Integer PKs |
| — | HTMX over React/Vue | Python-native, minimal JS | React, Vue |
| — | Alpine.js for client state | HTML-first, plays well with HTMX | React, vanilla JS |
| — | HeadlessUI cloned to Alpine | Best accessibility + UX patterns | Custom from scratch |
| — | PostgreSQL FTS | Native, no extra infra | Elasticsearch |
| — | Soft deletes | Audit trail, recovery | Hard deletes |
| — | Single app.js for Alpine | One source of truth | Per-component files |
| — | Centralised templates root | Clear structure, no app-level base.html | Per-app templates dirs |
| Feb 2025 | Adopted selectors.py pattern | ORM queries scattered across views | Fat models, fat views |
| Feb 2025 | Moved secrets to .env | Hardcoded DB creds + insecure SECRET_KEY fallback | Leaving in settings |
| Mar 2026 | `DJANGO_ENV`-based settings routing | Hardcoded dev import can't switch envs | Single settings file |
| Mar 2026 | `STORAGES` dict over `STATICFILES_STORAGE` | Django 4.2+ deprecation | Legacy setting |
| Mar 2026 | nh3 replaces bleach for HTML sanitization | bleach deprecated | bleach, manual regex |
| Mar 2026 | SEO views split into 4 modules | 1725-line monolith unmaintainable | Single file |
| Mar 2026 | HTMX lazy-loaded tabs for SEO dashboard | Full page loaded all tabs' data (15+ queries) | Server-side render all tabs |
| Mar 2026 | SEO admin: kanban boards removed | Static HTML kanban without DnD wastes screen space | Status filter pills on tables |
| Mar 2026 | Tagulous type stubs in `typings/` dir | No official stubs; scattered `cast(Any)` unmaintainable | cast() everywhere |
| Mar 2026 | `readingProgress()` as Alpine component | Inline `x-data` with scroll listener caused memory leaks | Inline Alpine |

---

## 🧠 LEARNED PATTERNS — TOP 30 ESSENTIALS

1. **Custom QuerySet typing**: `Post.objects: ClassVar[PostQuerySet] = PostQuerySet.as_manager()  # type: ignore[assignment]` — Pylance needs this to resolve custom queryset methods
2. **View function typing**: All Django view functions must annotate `request: HttpRequest` explicitly — omission cascades into 10-20+ downstream unknown-type errors per function
3. **Summernote CSS isolation**: Summernote BS5 reuses `.card`, `.card-header`, `.btn` Bootstrap classes — use `:not(.note-editor)` / `:not(.note-btn)` exclusions on global rules + JS `classList.remove()` as backup
4. **OOB swaps**: `hx-swap-oob="true"` required when updating multiple DOM targets from one HTMX response
5. **HTMX view guards**: `request.htmx` is falsy for non-HTMX requests — guard with `if not request.htmx: return redirect(...)` on all HTMX-only views
6. **Toast from server**: `HX-Trigger` response header is the cleanest way to fire Alpine events (toasts, modal close) from Django — use `trigger_client_event` from `django_htmx.http`
7. **Dark mode**: Bootstrap 5.3 `data-bs-theme` on `<html>` enables native dark mode — Alpine drives the toggle
8. **nh3 gotcha**: `"rel"` must NOT be in `ALLOWED_HTML_ATTRIBUTES["a"]` when `link_rel` parameter is used — causes Rust panic
9. **PostgreSQL extensions**: `pg_trgm` and `unaccent` must be created manually via `CREATE EXTENSION IF NOT EXISTS ...;`
10. **Signal handler typing**: Django signal handlers must annotate `sender: type[Any]`, `instance: Any`, `**kwargs: Any` — unannotated triggers ~40 cascade errors per handler
11. **Tagulous stubs**: Tagulous has NO official type stubs — use `typings/tagulous/` directory with `.pyi` files, set `"typingsPath": "typings"` in pyrightconfig
12. **Lean tab contexts**: Loading all tabs' data in one view (`_control_common_context`) kills performance — use lean per-tab context builders with HTMX lazy-loading
13. **CSS glassmorphism**: `color-mix(in srgb, var(--surface-1) 85%, transparent)` enables glassmorphism with CSS variables without hardcoding rgba
14. **will-change**: Only add `will-change: transform` to elements that actually animate — prevents unnecessary compositor rasterisation
15. **Summernote word count**: Use `MutationObserver` on `.summernote-bridge-host` for real-time updates instead of reading the hidden textarea (delayed by bridge sync)
16. **Settings routing**: `os.environ.get("DJANGO_ENV", "development")` in config/settings.py — never hardcode the import
17. **Connection health**: `CONN_HEALTH_CHECKS = True` in DATABASES config enables Django 4.1+ connection health verification on persistent connections
18. **Selector dedup**: Each queryset helper lives in exactly ONE app's selectors.py; cross-app usage imports from the canonical location — never copy
19. **data-ui-confirm**: Must NEVER go on create/edit forms — only on destructive/bulk actions; `preventDefault()` kills the form if the modal chain breaks
20. **Conditional jQuery**: `if(!window.jQuery) document.write(...)` prevents double-load when Tagulous already includes jQuery
21. **Alpine wrapper divs**: `display:contents` + `x-cloak` on Alpine wrapper elements makes them invisible to layout while maintaining scope
22. **View Transitions**: `::view-transition-old(root)` / `::view-transition-new(root)` with `animation: none` prevents default cross-fade — let HTMX handle transitions
23. **btn-xs specificity**: `.btn-xs` needs explicit `padding` + `.btn.btn-xs` selector (0,2,0 specificity) to override `:not(.note-btn)` rules
24. **Multi-line template comments**: `{% comment %}...{% endcomment %}` for multi-line — `{# #}` is single-line only and `{# ... {%  ... #}` still triggers tag processing
25. **Alpine CDN load order**: Alpine CDN script must load LAST after all stores/components are registered
26. **overflow-y clips dropdowns**: `overflow-y: auto` on containers clips absolutely-positioned Summernote dropdowns/popovers — never set on containers with third-party widgets
27. **Production cache**: Redis cache must `raise ImportError(...)` on failure, not silently fallback to LocMemCache
28. **STORAGES dict**: Replaces deprecated `STATICFILES_STORAGE` and `DEFAULT_FILE_STORAGE` in Django 4.2+
29. **PowerShell encoding**: `Set-Content` defaults to system encoding (CP1252 on Windows) — use Python for text replacement in files with non-ASCII characters
30. **`:not()` specificity bump**: Adding `:not(.x)` bumps specificity from 0,1,0 to 0,2,0 — audit ALL downstream overrides for cascade breakage

---

## 🚨 COMMON PITFALLS — ZERO TOLERANCE, NEVER REPEAT

| ❌ Never | ✅ Always |
|---|---|
| Business logic in views | `services.py` |
| ORM queries in views | `selectors.py` |
| Logic in templates | View context or `core_tags.py` |
| `fields = '__all__'` in forms | List every field explicitly |
| Hardcoded URLs in templates or Python | `{% url 'namespace:name' %}` / `reverse()` |
| CDN imports in child templates | `base.html` only — once |
| `<script>` outside `{% block extra_js %}` | Use the block |
| `<style>` outside `{% block extra_css %}` | Use the block |
| Alpine logic > 2 props inline | Extract to named function in `app.js` |
| Missing `app_name` in `urls.py` | Always defined — enables namespacing |
| N+1 queries (ORM in loop) | `select_related` / `prefetch_related` in selectors |
| Secrets in settings files | `environ.Env()` from `.env`, fail if missing |
| Missing `request.htmx` check in HTMX view | Guard and redirect for non-HTMX requests |
| Model not inheriting BaseModel | Always inherit `core.models.BaseModel` |
| Cross-app view/form/url imports | Use `core/` or Django signals |
| Global CSS rules bleeding into Summernote | Use `:not(.note-editor)` / `:not(.note-btn)` exclusions |
| `data-ui-confirm` on create/edit forms | Reserve for destructive/bulk operations only |
| Write operations in `selectors.py` | `selectors.py` = reads ONLY; writes go in `services.py` |
| Duplicate selectors across apps | One canonical location per selector; import cross-app |
| `<meta name="htmx-config">` after htmx script | Place htmx-config meta BEFORE the htmx script tag |

---

## 🎯 ACTIVE CONTEXT — UPDATE EVERY SESSION

```
Last Updated:     Mar 3, 2026
Working On:       SEO Admin UI rewrite (clean data-table design)
Status:           Backend views split into 4 modules, templates rewritten
Blocked By:       Nothing
Next Steps:
  1. Media Manager (apps/media/) — django-filer integration (HIGH)
  2. HeadlessUI components 4-13 (MEDIUM)
  3. BaseModel migration for remaining models (HIGH)
  4. Test suite expansion (MEDIUM)
  5. SEO selector optimization — cache + DB pagination (MEDIUM)
Open Questions:   None

RUFF STATUS:      ✅ All checks passed (0 violations)
DJANGO CHECK:     ✅ System check identified no issues
```

---

## 📌 THE 15 GOLDEN LAWS
 1. ONE base.html — everything inherits it
 2. ONE config/urls.py — all app urls included here
 3. ONE services.py per app — all business logic
 4. ONE selectors.py per app — all ORM queries
 5. ONE apps/core/ — all shared utilities, tags, mixins, base models
 6. ONE static/js/app.js — all Alpine components + theme + stores
 7. ONE static/css/components.css — all HeadlessUI + component styles
 8. ZERO business logic in views, models, or templates
 9. ZERO hardcoded URLs — {% url %} and reverse() everywhere
10. ZERO duplication — exists twice = belongs in core
11. ZERO N+1 queries — select_related / prefetch_related always
12. ZERO secrets in code — .env always
13. ZERO cross-app direct imports — use core/ or signals
14. ALL apps self-contained under apps/ with app_name in urls.py
15. ALL HeadlessUI components = app.js function + HTML partial + components.css

---

*Living document. Claude grows it every session. Team grows it. Never becomes stale.*
*HeadlessUI: 3/13 done | Last clean rewrite: Mar 3, 2026*
