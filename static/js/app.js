/**
 * ============================================================================
 * APP.JS — THE SINGLE ALPINE COMPONENT REGISTRY
 * ============================================================================
 * All Alpine component functions live here. One file, zero duplication.
 * This file coexists with alpine-store.js (Alpine.store approach) —
 * alpine-store.js owns global reactive state ($store.ui), this file owns
 * named component functions used via x-data="functionName()".
 *
 * Load order in base.html: alpine-store.js → app.js → alpinejs defer
 *
 * Patterns:
 *  - Named functions — used as x-data="modalManager()"
 *  - ARIA attributes set in HTML, driven by Alpine state
 *  - Keyboard navigation built into every interactive component
 *  - Focus management for a11y (modals trap focus, drawers return focus)
 * ============================================================================
 */

/* ============================================================================
   ROOT APP SHELL
   ============================================================================ */

function appShell() {
  return {
    /**
     * Called from x-data="appShell()" on <body>.
     * Provides the top-level Alpine scope for the public site.
     */
    mobileSearch: false,   // toggled by the mobile search bar
    init() {
      // Restore reading progress if persisted
      this._restoreScrollProgress();
    },
    _restoreScrollProgress() {
      // No-op placeholder — extended by site/core.js
    },
  };
}

/* ============================================================================
   MODAL MANAGER
   ============================================================================ */

function modalManager() {
  return {
    open: false,
    title: "",
    size: "md",     // sm | md | lg | xl
    _previousFocus: null,

    show(cfg = {}) {
      this.title = cfg.title || "";
      this.size = cfg.size || "md";
      this.open = true;
      this._previousFocus = document.activeElement;
      document.body.style.overflow = "hidden";
      this.$nextTick(() => {
        const first = this.$el.querySelector(
          'button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );
        if (first) first.focus();
      });
    },

    close() {
      this.open = false;
      document.body.style.overflow = "";
      if (this._previousFocus) {
        this._previousFocus.focus();
        this._previousFocus = null;
      }
    },

    handleKeydown(e) {
      if (e.key === "Escape") this.close();
      if (e.key === "Tab") this._trapFocus(e);
    },

    _trapFocus(e) {
      const focusable = Array.from(
        this.$el.querySelectorAll(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])'
        )
      );
      if (!focusable.length) { e.preventDefault(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey) {
        if (document.activeElement === first) { e.preventDefault(); last.focus(); }
      } else {
        if (document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    },
  };
}

/* ============================================================================
   DRAWER / SLIDEOVER MANAGER
   ============================================================================ */

function drawerManager() {
  return {
    open: false,
    side: "right",  // right | left
    title: "",
    _previousFocus: null,

    show(cfg = {}) {
      this.side = cfg.side || "right";
      this.title = cfg.title || "";
      this.open = true;
      this._previousFocus = document.activeElement;
      document.body.style.overflow = "hidden";
    },

    close() {
      this.open = false;
      document.body.style.overflow = "";
      if (this._previousFocus) {
        this._previousFocus.focus();
        this._previousFocus = null;
      }
    },

    handleKeydown(e) {
      if (e.key === "Escape") this.close();
    },
  };
}

/* ============================================================================
   TOAST MANAGER
   ============================================================================ */

function toastManager() {
  return {
    toasts: [],

    add(detail) {
      const id = Date.now() + Math.random();
      const duration = detail.duration || 3800;
      const level = detail.type || detail.level || "info";
      const icons = { success: "✓", warning: "⚠", danger: "✕", info: "ℹ" };
      this.toasts.push({
        id,
        message: typeof detail === "string" ? detail : (detail.message || ""),
        title: detail.title || "",
        level,
        icon: detail.icon || icons[level] || "ℹ",
        duration,
        visible: true,
      });
      setTimeout(() => this._dismiss(id), duration);
    },

    _dismiss(id) {
      const t = this.toasts.find((x) => x.id === id);
      if (t) {
        t.visible = false;
        setTimeout(() => { this.toasts = this.toasts.filter((x) => x.id !== id); }, 250);
      }
    },

    dismiss(id) { this._dismiss(id); },
  };
}

/**
 * Global helper — call from anywhere: dispatchToast("Saved!", "success")
 * @param {string} message
 * @param {"success"|"warning"|"danger"|"info"} type
 * @param {number} duration  ms
 */
function dispatchToast(message, type = "success", duration = 3800) {
  window.dispatchEvent(
    new CustomEvent("hl-toast", { detail: { message, type, duration } })
  );
}

// Auto-fire toasts from HX-Trigger: {"showToast": {"message": "...", "type": "success"}}
document.addEventListener("htmx:afterRequest", (e) => {
  const header = e.detail.xhr?.getResponseHeader("HX-Trigger");
  if (!header) return;
  try {
    const data = JSON.parse(header);
    if (data.showToast) {
      dispatchToast(data.showToast.message, data.showToast.type, data.showToast.duration);
    }
  } catch (_) { /* Non-JSON trigger header — ignore */ }
});

/* ============================================================================
   LISTBOX (HeadlessUI Select Clone)
   ============================================================================ */

function listbox(cfg = {}) {
  return {
    open: false,
    selected: cfg.initial || null,
    activeIndex: 0,
    options: cfg.options || [],
    labelKey: cfg.labelKey || "label",
    valueKey: cfg.valueKey || "value",
    query: "",

    get displayLabel() {
      if (!this.selected) return cfg.placeholder || "Select…";
      return this.selected[this.labelKey] ?? this.selected;
    },

    toggle() {
      this.open = !this.open;
      if (this.open) {
        this.activeIndex = this.options.findIndex((o) => this._isSelected(o));
        if (this.activeIndex < 0) this.activeIndex = 0;
      }
    },

    close() { this.open = false; },

    select(option) {
      this.selected = option;
      this.open = false;
      this.$dispatch("listbox-change", { value: option[this.valueKey] ?? option });
    },

    _isSelected(option) {
      if (!this.selected) return false;
      const sv = this.selected[this.valueKey] ?? this.selected;
      const ov = option[this.valueKey] ?? option;
      return sv === ov;
    },

    isSelected(option) { return this._isSelected(option); },

    handleKeydown(e) {
      const len = this.options.length;
      if (!this.open) {
        if (["Enter", " ", "ArrowDown"].includes(e.key)) { e.preventDefault(); this.open = true; }
        return;
      }
      if (e.key === "Escape") { this.close(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); this.activeIndex = (this.activeIndex + 1) % len; }
      if (e.key === "ArrowUp") { e.preventDefault(); this.activeIndex = (this.activeIndex - 1 + len) % len; }
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); this.select(this.options[this.activeIndex]); }
      if (e.key === "Home") { e.preventDefault(); this.activeIndex = 0; }
      if (e.key === "End") { e.preventDefault(); this.activeIndex = len - 1; }
    },
  };
}

/* ============================================================================
   COMBOBOX / AUTOCOMPLETE
   ============================================================================ */

function combobox(cfg = {}) {
  return {
    open: false,
    query: "",
    selected: cfg.initial || null,
    loading: false,

    get isEmpty() { return !this.query.trim(); },

    close() { this.open = false; },

    clear() {
      this.query = "";
      this.selected = null;
      this.$dispatch("combobox-clear");
    },

    onSelect(value) {
      this.selected = value;
      this.open = false;
      this.$dispatch("combobox-change", { value });
    },

    handleKeydown(e) {
      if (e.key === "Escape") this.close();
    },
  };
}

/* ============================================================================
   SWITCH / TOGGLE
   ============================================================================ */

function switchToggle(initialValue = false) {
  return {
    checked: initialValue,

    toggle() {
      this.checked = !this.checked;
      this.$dispatch("switch-change", { checked: this.checked });
    },

    handleKeydown(e) {
      if (e.key === " " || e.key === "Enter") { e.preventDefault(); this.toggle(); }
    },
  };
}

/* ============================================================================
   TABS
   ============================================================================ */

function tabs(cfg = {}) {
  return {
    activeTab: cfg.initial || 0,

    setTab(index) {
      this.activeTab = index;
      this.$dispatch("tab-change", { index });
    },

    isActive(index) { return this.activeTab === index; },

    handleKeydown(e, count) {
      if (e.key === "ArrowRight") { e.preventDefault(); this.setTab((this.activeTab + 1) % count); }
      if (e.key === "ArrowLeft") { e.preventDefault(); this.setTab((this.activeTab - 1 + count) % count); }
      if (e.key === "Home") { e.preventDefault(); this.setTab(0); }
      if (e.key === "End") { e.preventDefault(); this.setTab(count - 1); }
    },
  };
}

/* ============================================================================
   DISCLOSURE / ACCORDION
   ============================================================================ */

function disclosure(initialOpen = false) {
  return {
    open: initialOpen,
    toggle() { this.open = !this.open; },
  };
}

/* ============================================================================
   DROPDOWN MENU
   ============================================================================ */

function dropdown() {
  return {
    open: false,
    activeIndex: -1,

    toggle() {
      this.open = !this.open;
      if (this.open) {
        this.activeIndex = 0;
        this.$nextTick(() => {
          const items = this.$el.querySelectorAll(".hl-menu-item");
          if (items[0]) items[0].focus();
        });
      }
    },

    close() { this.open = false; this.activeIndex = -1; },

    handleKeydown(e, itemCount) {
      if (e.key === "Escape") { this.close(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); this.activeIndex = Math.min(this.activeIndex + 1, itemCount - 1); }
      if (e.key === "ArrowUp")   { e.preventDefault(); this.activeIndex = Math.max(this.activeIndex - 1, 0); }
    },
  };
}

/* ============================================================================
   RADIO GROUP
   ============================================================================ */

function radioGroup(initial = null) {
  return {
    selected: initial,

    select(value) {
      this.selected = value;
      this.$dispatch("radio-change", { value });
    },

    isSelected(value) { return this.selected === value; },
  };
}

/* ============================================================================
   COMMAND PALETTE
   ============================================================================ */

function commandPalette() {
  return {
    open: false,
    query: "",
    loading: false,
    activeIndex: 0,

    show() {
      this.open = true;
      this.query = "";
      this.$nextTick(() => this.$refs.input?.focus());
    },

    close() {
      this.open = false;
      this.query = "";
    },

    init() {
      window.addEventListener("keydown", (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === "k") {
          e.preventDefault();
          this.open ? this.close() : this.show();
        }
      });
    },

    handleKeydown(e, itemCount) {
      if (e.key === "Escape") { this.close(); return; }
      if (e.key === "ArrowDown") { e.preventDefault(); this.activeIndex = Math.min(this.activeIndex + 1, (itemCount || 1) - 1); }
      if (e.key === "ArrowUp")   { e.preventDefault(); this.activeIndex = Math.max(this.activeIndex - 1, 0); }
    },
  };
}

/* ============================================================================
   DATA TABLE
   ============================================================================ */

function dataTable(cfg = {}) {
  return {
    sortField: cfg.defaultSort || "",
    sortDir: "asc",
    selected: new Set(),
    _allIds: cfg.ids || [],

    get allSelected() {
      return this._allIds.length > 0 && this._allIds.every((id) => this.selected.has(id));
    },

    get selectedCount() { return this.selected.size; },

    sort(field) {
      if (this.sortField === field) {
        this.sortDir = this.sortDir === "asc" ? "desc" : "asc";
      } else {
        this.sortField = field;
        this.sortDir = "asc";
      }
      this.$dispatch("table-sort", { field: this.sortField, dir: this.sortDir });
    },

    toggleSelectAll() {
      if (this.allSelected) {
        this.selected.clear();
      } else {
        this._allIds.forEach((id) => this.selected.add(id));
      }
    },

    toggleSelect(id) {
      if (this.selected.has(id)) this.selected.delete(id);
      else this.selected.add(id);
    },

    isSelected(id) { return this.selected.has(id); },
  };
}

/* ============================================================================
   FORM STATE
   ============================================================================ */

function formState() {
  return {
    loading: false,
    dirty: false,
    errors: {},
    _csrfToken: () =>
      document.querySelector('meta[name="csrf-token"]')?.content ||
      document.querySelector('[name="csrfmiddlewaretoken"]')?.value ||
      "",

    setError(field, msg) { this.errors[field] = msg; },
    clearErrors() { this.errors = {}; },
    hasError(field) { return !!this.errors[field]; },

    async submit(url, data, method = "POST") {
      this.loading = true;
      this.clearErrors();
      try {
        const res = await fetch(url, {
          method,
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this._csrfToken(),
          },
          body: JSON.stringify(data),
        });
        const json = await res.json();
        if (!res.ok) {
          this.errors = json.errors || {};
          return json;
        }
        this.dirty = false;
        return json;
      } finally {
        this.loading = false;
      }
    },
  };
}

/* ============================================================================
   TAG CHIPS INPUT
   ============================================================================ */

function tagChips(initialValue = "", fieldName = "tags") {
  return {
    tags: [],
    fieldName,
    inputValue: "",
    _backspaceArmed: false,

    init() {
      if (initialValue) {
        this.tags = initialValue
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean);
      }
    },

    get tagsString() { return this.tags.join(", "); },

    addTag(value) {
      const tag = value.trim().replace(/,/g, "").trim();
      if (tag && !this.tags.includes(tag)) {
        this.tags.push(tag);
      }
      this.inputValue = "";
      this._backspaceArmed = false;
    },

    removeTag(tag) {
      this.tags = this.tags.filter((t) => t !== tag);
    },

    handleKeydown(e) {
      if (e.key === "Enter" || e.key === ",") {
        e.preventDefault();
        if (this.inputValue.trim()) this.addTag(this.inputValue);
      }
      if (e.key === "Backspace" && !this.inputValue) {
        if (this._backspaceArmed) {
          this.tags.pop();
          this._backspaceArmed = false;
        } else {
          this._backspaceArmed = true;
        }
      } else {
        this._backspaceArmed = false;
      }
    },
  };
}

/* ============================================================================
   TABLE OF CONTENTS
   ============================================================================ */

function tableOfContents() {
  return {
    headings: [],
    activeId: "",
    _observer: null,

    init() {
      this._buildHeadings();
      this._setupObserver();
    },

    _buildHeadings() {
      const article = document.querySelector(".markdown-body, article.content-panel, .post-body");
      if (!article) return;
      const nodes = article.querySelectorAll("h2, h3, h4");
      nodes.forEach((node, i) => {
        if (!node.id) node.id = "toc-" + i;
        this.headings.push({ id: node.id, text: node.textContent.trim(), level: parseInt(node.tagName[1]) });
      });
    },

    _setupObserver() {
      this._observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (entry.isIntersecting) this.activeId = entry.target.id;
          });
        },
        { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
      );
      this.headings.forEach((h) => {
        const el = document.getElementById(h.id);
        if (el) this._observer.observe(el);
      });
    },

    scrollTo(id) {
      const el = document.getElementById(id);
      if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    },

    destroy() {
      if (this._observer) this._observer.disconnect();
    },
  };
}

/* ============================================================================
   COUNT-UP ANIMATION HELPER
   ============================================================================ */

function countUp(element, target, duration = 1200) {
  const startTime = performance.now();
  const update = (currentTime) => {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // cubic ease-out
    const current = Math.floor(eased * target);
    element.textContent = current.toLocaleString();
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

// Auto-init countUp on elements with data-count-up attribute
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-count-up]").forEach((el) => {
    const raw = el.dataset.countUp || el.textContent;
    const target = parseInt(raw.replace(/[^0-9]/g, ""), 10);
    if (!isNaN(target)) {
      // Use IntersectionObserver so off-screen elements animate when visible
      const obs = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            obs.unobserve(entry.target);
            countUp(entry.target, target);
          });
        },
        { threshold: 0.3 }
      );
      obs.observe(el);
    }
  });
});

/* ============================================================================
   SCROLL-TRIGGERED ANIMATIONS (IntersectionObserver)
   ============================================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const scrollObs = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          scrollObs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -40px 0px" }
  );
  document.querySelectorAll(".animate-on-scroll").forEach((el) => scrollObs.observe(el));
});

/* ============================================================================
   VIEW TRANSITIONS — HTMX integration
   ============================================================================ */

// htmx.config.globalViewTransitions is set in base.html templates
// These CSS names are used by ::view-transition-old/new rules in site/core.css
document.addEventListener("htmx:beforeTransition", () => {
  document.documentElement.classList.add("htmx-transitioning");
});
document.addEventListener("htmx:afterTransition", () => {
  document.documentElement.classList.remove("htmx-transitioning");
});
