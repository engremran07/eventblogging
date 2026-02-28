/**
 * Alpine.js Central Store
 * Single source of truth for all UI and user state
 * Access via $store.ui and $store.user in any Alpine.js component
 */

// Helper functions needed for UI store
function normalizeLevel(level) {
  const allowed = ["success", "info", "warning", "error"];
  return allowed.includes(level) ? level : "info";
}

function getCookie(name) {
  const cookieValue = document.cookie
    .split("; ")
    .find((row) => row.startsWith(name + "="));
  return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : "";
}

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
  async toggleTheme() {
    const nextTheme = this.theme === "dark" ? "light" : "dark";
    const toggleUrl = document.body?.dataset?.adminThemeToggleUrl || "";

    if (toggleUrl) {
      try {
        const response = await fetch(toggleUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "X-Requested-With": "XMLHttpRequest",
          },
        });
        if (response.ok) {
          const payload = await response.json();
          this.theme = payload.mode || nextTheme;
        } else {
          this.theme = nextTheme;
        }
      } catch (_error) {
        this.theme = nextTheme;
      }
    } else {
      this.theme = nextTheme;
    }

    document.documentElement.setAttribute("data-bs-theme", this.theme);
    if (document.body) {
      document.body.setAttribute("data-bs-theme", this.theme);
    }
  },

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
 * Contains admin-specific state and operations
 */
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
});

// Initialize theme on page load
document.addEventListener('alpine:init', () => {
  const theme = Alpine.store('ui').theme;
  document.documentElement.setAttribute('data-bs-theme', theme);
  if (document.body) {
    document.body.setAttribute('data-bs-theme', theme);
  }
});

