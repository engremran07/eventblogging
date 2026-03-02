/* =============================================================================
   APP.JS  UNIFIED ALPINE + THEME + COMPONENT REGISTRY
   =============================================================================
   Consolidated from: theme-core.js, alpine-store.js, app.js
   Load order: This file first (defer), then Alpine CDN (defer, last).
   Contains:
     1. ThemeCore IIFE (window.ThemeCore  shared theme management)
     2. Alpine stores (alpine:init listener  .ui, .user, .admin)
     3. Named Alpine component functions (modalManager, drawerManager, etc.)
   ============================================================================= */


/* ============================================================================
   MERGED FROM: theme-core.js
   ============================================================================ */

/**
 * theme-core.js â€” Shared Theme Management
 * Single source of truth for theme utilities used by both admin and public.
 * Loaded as the FIRST deferred script in both base.html and base_site.html.
 * Exposes window.ThemeCore for consumption by admin/core.js and site/core.js.
 */
(function () {
    "use strict";

    var afterApplyHooks = [];

    function getCookie(name) {
        var cookieValue = document.cookie
            .split("; ")
            .find(function (row) { return row.startsWith(name + "="); });
        return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : null;
    }

    function getThemeMode() {
        // Prefer localStorage (set by applyTheme on every toggle) so the
        // browser-local choice survives page refreshes even when the
        // server-rendered HTML attribute is stale (context-processor cache).
        try {
            var stored = localStorage.getItem("global_theme_mode");
            if (stored === "dark" || stored === "light") { return stored; }
        } catch (_) { /* localStorage unavailable — fall through */ }
        return document.documentElement.getAttribute("data-bs-theme") || "light";
    }

    function getThemePreset() {
        try {
            var stored = localStorage.getItem("global_theme_preset");
            if (stored) { return stored; }
        } catch (_) { /* localStorage unavailable — fall through */ }
        return document.documentElement.getAttribute("data-app-preset") || "aurora";
    }

    function applyAppearanceVariables(cssVariables) {
        if (!cssVariables || typeof cssVariables !== "object") {
            return;
        }
        Object.entries(cssVariables).forEach(function (entry) {
            var variableName = entry[0];
            var variableValue = entry[1];
            if (typeof variableName !== "string" || !variableName.startsWith("--")) {
                return;
            }
            if (typeof variableValue !== "string") {
                return;
            }
            document.documentElement.style.setProperty(variableName, variableValue);
        });
    }

    function applyThemeLogos(mode) {
        var safeMode = mode === "dark" ? "dark" : "light";
        document.querySelectorAll("[data-theme-logo]").forEach(function (element) {
            var lightLogo = element.dataset.logoLight || element.getAttribute("src") || "";
            var darkLogo = element.dataset.logoDark || lightLogo;
            var nextSource = safeMode === "dark" ? darkLogo : lightLogo;
            if (nextSource && element.getAttribute("src") !== nextSource) {
                element.setAttribute("src", nextSource);
            }
        });
    }

    function applyTheme(mode, preset, cssVariables) {
        var safeMode = mode === "dark" ? "dark" : "light";
        var safePreset = (preset || "").trim() || getThemePreset();

        document.documentElement.setAttribute("data-bs-theme", safeMode);
        document.documentElement.setAttribute("data-app-preset", safePreset);
        applyAppearanceVariables(cssVariables);
        if (document.body) {
            document.body.setAttribute("data-bs-theme", safeMode);
            document.body.setAttribute("data-app-preset", safePreset);
        }
        applyThemeLogos(safeMode);

        if (window.Alpine && typeof window.Alpine.store === "function") {
            var uiStore = window.Alpine.store("ui");
            if (uiStore && typeof uiStore === "object") {
                uiStore.theme = safeMode;
            }
        }

        try {
            localStorage.setItem("global_theme_mode", safeMode);
            localStorage.setItem("global_theme_preset", safePreset);
        } catch (_error) {
            // localStorage may be unavailable in private mode; ignore.
        }

        // Execute post-apply hooks (e.g., admin glyph toggle)
        afterApplyHooks.forEach(function (fn) {
            fn(safeMode, safePreset);
        });
    }

    function fetchThemeState(url) {
        return fetch(url, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest",
            },
            cache: "no-store",
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("theme_state_failed");
            }
            return response.json();
        });
    }

    function bindThemeStateSync() {
        var stateUrl = document.body && document.body.dataset
            ? document.body.dataset.themeStateUrl || ""
            : "";
        if (!stateUrl) {
            return;
        }

        var inFlight = false;

        var sync = function () {
            if (inFlight || document.visibilityState === "hidden") {
                return;
            }
            inFlight = true;
            fetchThemeState(stateUrl)
                .then(function (payload) {
                    applyTheme(
                        payload.mode || getThemeMode(),
                        payload.preset || getThemePreset(),
                        payload.css_variables || null
                    );
                })
                .catch(function () {
                    // Keep current theme when sync request fails.
                })
                .finally(function () {
                    inFlight = false;
                });
        };

        window.setInterval(sync, 120000);  // 2 min — reduces server load for anonymous visitors
        document.addEventListener("visibilitychange", function () {
            if (document.visibilityState === "visible") {
                sync();
            }
        });
    }

    function bindThemeStorageSync() {
        window.addEventListener("storage", function (event) {
            if (event.key !== "global_theme_mode" && event.key !== "global_theme_preset") {
                return;
            }
            var mode = getThemeMode();
            var preset = getThemePreset();
            try {
                mode = localStorage.getItem("global_theme_mode") || mode;
                preset = localStorage.getItem("global_theme_preset") || preset;
            } catch (_error) {
                // localStorage may be unavailable in private mode; ignore.
            }
            applyTheme(mode, preset);
        });
    }

    // Public API â€” consumed by admin/core.js, site/core.js, alpine-store.js
    window.ThemeCore = {
        getCookie: getCookie,
        getThemeMode: getThemeMode,
        getThemePreset: getThemePreset,
        applyAppearanceVariables: applyAppearanceVariables,
        applyThemeLogos: applyThemeLogos,
        applyTheme: applyTheme,
        fetchThemeState: fetchThemeState,
        bindThemeStateSync: bindThemeStateSync,
        bindThemeStorageSync: bindThemeStorageSync,
        /**
         * Register a callback to run after every applyTheme() call.
         * Used by admin/core.js for glyph toggling.
         * @param {function(string, string): void} fn  Receives (mode, preset)
         */
        onAfterApply: function (fn) {
            if (typeof fn === "function") {
                afterApplyHooks.push(fn);
            }
        }
    };
})();


/* ============================================================================
   MERGED FROM: alpine-store.js
   ============================================================================ */

/**
 * Alpine.js Central Store
 * Single source of truth for all UI and user state
 * Access via $store.ui and $store.user in any Alpine.js component
 */

// All store registrations are deferred until Alpine fires 'alpine:init'.
// This lets Alpine CDN load LAST in the defer chain (correct per Alpine 3 docs)
// while this script runs first â€” no 'Alpine is not defined' errors.
// Helper functions are scoped INSIDE the callback â€” zero window pollution.
document.addEventListener('alpine:init', () => {

  // â”€â”€ Private helpers (scoped to this callback, not on window) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
  function normalizeLevel(level) {
    const allowed = ["success", "info", "warning", "error"];
    return allowed.includes(level) ? level : "info";
  }

  // getCookie is provided by theme-core.js (loaded before this script).
  // Fallback to inline version if ThemeCore is unavailable (defensive).
  var getCookie = (window.ThemeCore && window.ThemeCore.getCookie) || function (name) {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith(name + "="));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
  };

  function findInlineSlot(target) {
    if (!target) {
      return document.querySelector('[data-ui-feedback-slot="global"]');
    }
    if (typeof target !== "string") {
      return null;
    }
    const key = target.trim();
    if (!key) {
      return document.querySelector('[data-ui-feedback-slot="global"]');
    }
    if (key.startsWith("#") || key.startsWith(".") || key.startsWith("[")) {
      return document.querySelector(key);
    }
    return document.querySelector(`[data-ui-feedback-slot="${key}"]`);
  }

  function renderInline(slot, level, message) {
    if (!slot) {
      return;
    }
    if (!slot.dataset.baseClass) {
      slot.dataset.baseClass = slot.className || "";
    }

    const currentLevel = normalizeLevel(level);
    slot.className =
      slot.dataset.baseClass +
      " ui-inline-feedback ui-inline-feedback-" +
      currentLevel;
    slot.classList.remove("d-none");

    slot.replaceChildren();
    const icon = document.createElement("span");
    icon.className = "ui-inline-feedback-icon";
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = currentLevel === "success" ? "+" : currentLevel === "error" ? "x" : "i";

    const text = document.createElement("span");
    text.className = "ui-inline-feedback-text";
    text.textContent = message || "Action completed.";

    slot.append(icon, text);
  }
  // â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

Alpine.store('ui', {
  // UI State - Theme and sidebar
  sidebarOpen: localStorage.getItem('sidebar_open') !== 'false',
  theme: document.documentElement.getAttribute('data-bs-theme') || 'light',
  loading: false,
  notificationsOpen: false,
  
  // Toast and modal state
  toasts: [],
  toastCounter: 0,
  _confirmOpen: false,
  _modal: null,

  // Theme Methods
  // NOTE: Theme toggling is owned by ThemeCore (window.ThemeCore.applyTheme).
  // Page-specific toggle handlers live in admin/admin.js and site/site.js.
  // $store.ui.theme is READ-ONLY from Alpine templates; ThemeCore.applyTheme
  // syncs it automatically after every toggle.

  toggleSidebar() {
    this.sidebarOpen = !this.sidebarOpen;
    localStorage.setItem('sidebar_open', this.sidebarOpen);
  },

  setLoading(isLoading) {
    this.loading = isLoading;
  },

  // Toast Methods - Combined implementation
  toastIcon(level) {
    const safeLevel = normalizeLevel(level);
    if (safeLevel === "success") {
      return "+";
    }
    if (safeLevel === "warning") {
      return "!";
    }
    if (safeLevel === "error") {
      return "x";
    }
    return "i";
  },

  notify(level, message, opts = {}) {
    const safeLevel = normalizeLevel(level);
    const safeMessage = (message || "").trim() || "Action completed.";
    const duration = Number(opts.duration || 3400);

    const id = ++this.toastCounter;
    this.toasts.push({
      id: id,
      level: safeLevel,
      message: safeMessage,
      visible: true,
    });

    window.setTimeout(() => {
      this.dismissToast(id);
    }, duration);
  },

  dismissToast(id) {
    const toast = this.toasts.find((entry) => entry.id === id);
    if (!toast) {
      return;
    }
    toast.visible = false;
    window.setTimeout(() => {
      this.toasts = this.toasts.filter((entry) => entry.id !== id);
    }, 180);
  },

  // Legacy toast methods for backward compatibility
  addToast(message, type = 'info', duration = 3000) {
    this.notify(type, message, { duration });
  },

  removeToast(id) {
    this.dismissToast(id);
  },

  clearToasts() {
    this.toasts = [];
    this.toastCounter = 0;
  },

  // Inline feedback method
  setInline(target, level, message) {
    const slot = findInlineSlot(target);
    if (!slot) {
      return;
    }
    renderInline(slot, level, message);
  },

  // Modal / Confirmation Methods
  openModal(modalId) {
    this._modal = modalId;
  },

  closeModal() {
    this._modal = null;
  },

  showConfirm(options = {}) {
    const title = options.title || "Confirm Action";
    const message = options.message || "Are you sure you want to continue?";
    const confirmText = options.confirmText || "Confirm";
    const cancelText = options.cancelText || "Cancel";
    const inlineTarget = options.inlineTarget || "global";

    if (this._confirmOpen) {
      return Promise.resolve(false);
    }

    if (!window.bootstrap || !window.bootstrap.Modal) {
      this.setInline(
        inlineTarget,
        "warning",
        "Confirmation dialog is unavailable. Action blocked."
      );
      this.notify(
        "warning",
        "Confirmation dialog is unavailable. Action blocked."
      );
      return Promise.resolve(false);
    }

    const modalElement = document.getElementById("ui-confirm-modal");
    const titleElement = document.getElementById("uiConfirmTitle");
    const messageElement = document.getElementById("uiConfirmMessage");
    const approveButton = document.getElementById("ui-confirm-approve");
    const cancelButton = document.getElementById("ui-confirm-cancel");

    if (
      !modalElement ||
      !titleElement ||
      !messageElement ||
      !approveButton ||
      !cancelButton
    ) {
      this.setInline(
        inlineTarget,
        "warning",
        "Confirmation dialog is unavailable. Action blocked."
      );
      this.notify(
        "warning",
        "Confirmation dialog is unavailable. Action blocked."
      );
      return Promise.resolve(false);
    }

    titleElement.textContent = title;
    messageElement.textContent = message;
    approveButton.textContent = confirmText;
    cancelButton.textContent = cancelText;

    const activeElement = document.activeElement;
    this._modal = this._modal || new window.bootstrap.Modal(modalElement);
    this._confirmOpen = true;

    return new Promise((resolve) => {
      let confirmed = false;

      const cleanup = () => {
        modalElement.removeEventListener("hidden.bs.modal", onHidden);
        approveButton.removeEventListener("click", onApprove);
        this._confirmOpen = false;
        if (activeElement && typeof activeElement.focus === "function") {
          activeElement.focus();
        }
      };

      const onApprove = () => {
        confirmed = true;
        this._modal.hide();
      };

      const onHidden = () => {
        cleanup();
        resolve(confirmed);
      };

      modalElement.addEventListener("hidden.bs.modal", onHidden, {
        once: true,
      });
      approveButton.addEventListener("click", onApprove, { once: true });
      this._modal.show();
    });
  },
});

/**
 * User State Store
 * Contains information about the currently logged-in user
 */
Alpine.store('user', {
  id: null,
  username: '',
  email: '',
  role: 'guest',
  permissions: [],
  is_staff: false,
  is_superuser: false,

  init(userData) {
    if (userData) {
      this.id = userData.id;
      this.username = userData.username;
      this.email = userData.email;
      this.role = userData.role || 'guest';
      this.permissions = userData.permissions || [];
      this.is_staff = userData.is_staff || false;
      this.is_superuser = userData.is_superuser || false;
    }
  },

  hasPermission(permission) {
    return this.is_superuser || this.permissions.includes(permission);
  },

  isAuthenticated() {
    return this.id !== null;
  },

  isStaff() {
    return this.is_staff || this.is_superuser;
  },
});

/**
 * Admin State Store
 * Contains admin-specific state and operations.
 * Only registered on admin pages (pages with .admin-shell container).
 */
if (document.querySelector('.admin-shell')) {
  Alpine.store('admin', {
    panelOpen: true,
    activeSection: null,
    notifications: [],
    
    togglePanel() {
      this.panelOpen = !this.panelOpen;
    },

    setActiveSection(section) {
      this.activeSection = section;
    },

    addNotification(message, type = 'info', duration = 3000) {
      const id = Math.random().toString(36).substr(2, 9);
      this.notifications.push({ id, message, type });
      
      if (duration > 0) {
        window.setTimeout(() => this.removeNotification(id), duration);
      }
    },

    removeNotification(id) {
      this.notifications = this.notifications.filter(n => n.id !== id);
    },

    clearNotifications() {
      this.notifications = [];
    },
  }); // end Alpine.store('admin')
} // end admin-shell guard

// Theme state is managed by ThemeCore (runs before Alpine). No need to
// re-set data-bs-theme here — ThemeCore already applied it synchronously.

}); // end document.addEventListener('alpine:init')



/* ============================================================================
   MERGED FROM: app.js
   ============================================================================ */

/**
 * ============================================================================
 * APP.JS â€” THE SINGLE ALPINE COMPONENT REGISTRY
 * ============================================================================
 * All Alpine component functions live here. One file, zero duplication.
 * This file coexists with alpine-store.js (Alpine.store approach) â€”
 * alpine-store.js owns global reactive state ($store.ui), this file owns
 * named component functions used via x-data="functionName()".
 *
 * Load order in base.html: alpine-store.js â†’ app.js â†’ alpinejs defer
 *
 * Patterns:
 *  - Named functions â€” used as x-data="modalManager()"
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
      // No-op placeholder â€” extended by site/core.js
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
      const icons = { success: "âœ“", warning: "âš ", danger: "âœ•", info: "â„¹" };
      this.toasts.push({
        id,
        message: typeof detail === "string" ? detail : (detail.message || ""),
        title: detail.title || "",
        level,
        icon: detail.icon || icons[level] || "â„¹",
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
 * Global helper â€” call from anywhere: dispatchToast("Saved!", "success")
 * @param {string} message
 * @param {"success"|"warning"|"danger"|"info"} type
 * @param {number} duration  ms
 */
function dispatchToast(message, type = "success", duration = 3800) {
  window.dispatchEvent(
    new CustomEvent("hl-toast", { detail: { message, type, duration } })
  );
}

// Auto-fire toasts from HX-Trigger: {"showToast": {...}} or {"ui:feedback": {...}}
// Consolidated handler — covers both showToast and ui:feedback formats.
document.addEventListener("htmx:afterRequest", (e) => {
  const xhr = e.detail.xhr;
  if (!xhr || xhr.__uiFeedbackHandled) return;
  const header = xhr.getResponseHeader("HX-Trigger");
  if (!header) return;
  try {
    const data = JSON.parse(header);
    if (data.showToast) {
      dispatchToast(data.showToast.message, data.showToast.type, data.showToast.duration);
    }
    if (data["ui:feedback"]) {
      xhr.__uiFeedbackHandled = true;
      const fb = data["ui:feedback"];
      if (fb.toast && fb.toast.message) {
        dispatchToast(fb.toast.message, fb.toast.level || "info");
      }
      if (fb.inline && fb.inline.message) {
        const ui = window.Alpine?.store?.("ui");
        if (ui && ui.setInline) {
          ui.setInline(fb.inline.target || "global", fb.inline.level, fb.inline.message);
        }
      }
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
      if (!this.selected) return cfg.placeholder || "Selectâ€¦";
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
   READING PROGRESS
   ============================================================================ */

/**
 * Track scroll progress through long-form content (e.g. blog posts).
 * Usage: x-data="readingProgress()" on a progress bar wrapper.
 */
function readingProgress() {
  return {
    progress: 0,
    _onScroll: null,

    init() {
      this._onScroll = () => {
        const d = document.documentElement;
        const max = d.scrollHeight - d.clientHeight;
        this.progress = max > 0 ? Math.round((d.scrollTop / max) * 100) : 0;
      };
      window.addEventListener('scroll', this._onScroll, { passive: true });
    },

    destroy() {
      if (this._onScroll) {
        window.removeEventListener('scroll', this._onScroll);
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
   VIEW TRANSITIONS â€” HTMX integration
   ============================================================================ */

// htmx.config.globalViewTransitions is set in base.html templates
// These CSS names are used by ::view-transition-old/new rules in site/core.css
document.addEventListener("htmx:beforeTransition", () => {
  document.documentElement.classList.add("htmx-transitioning");
});
document.addEventListener("htmx:afterTransition", () => {
  document.documentElement.classList.remove("htmx-transitioning");
});
