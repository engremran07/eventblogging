/* =============================================================================
   SITE.JS  PUBLIC SITE UTILITIES
   =============================================================================
   Consolidated from: alpine-htmx-utils.js, core.js
   Contains:
     1. Alpine + HTMX integration utilities (form validation, modals, search)
     2. Public site core (feedback, dashboard live sync, CSRF, confirm dialogs)
   ============================================================================= */


/* ============================================================================
   MERGED FROM: alpine-htmx-utils.js
   ============================================================================ */

/**
 * =============================================================================
 * ALPINE + HTMX INTEGRATION UTILITIES
 * =============================================================================
 * 
 * Reusable utilities for Alpine.js and HTMX integration.
 * Provides common patterns for:
 *  - Form validation and submission
 *  - Dynamic content loading
 *  - State synchronization
 *  - Component interaction
 */

(function () {
  "use strict";

  /**
   * ===========================================================================
   * FORM UTILITIES
   * ===========================================================================
   */

  /**
   * Validate a form field using HTML5 validation
   * @param {HTMLElement} field - Form field element
   * @returns {boolean} - True if valid
   */
  function validateField(field) {
    if (!field.checkValidity) {
      return true;
    }

    const isValid = field.checkValidity();

    if (!isValid) {
      field.classList.add("is-invalid");
      field.setAttribute("aria-invalid", "true");
    } else {
      field.classList.remove("is-invalid");
      field.setAttribute("aria-invalid", "false");
    }

    return isValid;
  }

  /**
   * Validate entire form
   * @param {HTMLFormElement} form - Form element
   * @returns {boolean} - True if all fields are valid
   */
  function validateForm(form) {
    const fields = form.querySelectorAll(
      "input, textarea, select"
    );
    let isValid = true;

    fields.forEach((field) => {
      if (!validateField(field)) {
        isValid = false;
      }
    });

    return isValid;
  }

  /**
   * Handle form field validation on input/change
   * @param {HTMLFormElement} form - Form element
   */
  function setupFormValidation(form) {
    const fields = form.querySelectorAll(
      "input, textarea, select"
    );

    fields.forEach((field) => {
      field.addEventListener("blur", () => validateField(field));
      field.addEventListener("change", () => validateField(field));
      field.addEventListener("input", () => {
        // Clear error state on input
        field.classList.remove("is-invalid");
      });
    });
  }

  /**
   * Submit form with optional validation
   * @param {HTMLFormElement} form - Form to submit
   * @param {Object} options - Options object
   */
  function submitForm(form, options = {}) {
    const {
      validate = true,
      showLoading = true,
      onSuccess = null,
      onError = null,
    } = options;

    if (validate && !validateForm(form)) {
      return;
    }

    if (showLoading) {
      const submitButton = form.querySelector(
        'button[type="submit"]'
      );
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.classList.add("is-loading");
      }
    }

    const formData = new FormData(form);
    const method = form.getAttribute("method") || "POST";
    const action = form.getAttribute("action") || window.location.href;

    htmx.ajax(method, action, {
      data: formData,
      target: form.getAttribute("data-target") || form,
      swap: form.getAttribute("data-swap") || "outerHTML",
      onSuccess: onSuccess,
      onError: onError,
    });
  }

  /**
   * ===========================================================================
   * MODAL UTILITIES
   * ===========================================================================
   */

  /**
   * Show modal with optional content loading
   * @param {string} modalId - ID of modal element
   * @param {string} url - Optional URL to load content from
   * @param {Object} options - Additional options
   */
  function showModal(modalId, url = null, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
      console.warn(`Modal not found: ${modalId}`);
      return;
    }

    if (url) {
      const contentArea = modal.querySelector(
        "[data-modal-content]"
      );
      if (contentArea) {
        htmx.ajax("GET", url, contentArea);
      }
    }

    modal.classList.add("active");
    modal.showModal?.();

    if (options.onOpen) {
      options.onOpen(modal);
    }
  }

  /**
   * Hide modal
   * @param {string} modalId - ID of modal element
   * @param {Object} options - Additional options
   */
  function hideModal(modalId, options = {}) {
    const modal = document.getElementById(modalId);
    if (!modal) {
      console.warn(`Modal not found: ${modalId}`);
      return;
    }

    modal.classList.remove("active");
    modal.close?.();

    if (options.onClose) {
      options.onClose(modal);
    }
  }

  /**
   * ===========================================================================
   * SEARCH/FILTER UTILITIES
   * ===========================================================================
   */

  /**
   * Debounce function for search/filter inputs
   * @param {Function} fn - Function to debounce
   * @param {number} delay - Delay in milliseconds
   * @returns {Function} - Debounced function
   */
  function debounce(fn, delay = 300) {
    let timeoutId;
    return function (...args) {
      clearTimeout(timeoutId);
      timeoutId = setTimeout(() => fn(...args), delay);
    };
  }

  /**
   * Setup autocomplete/search field
   * @param {HTMLInputElement} field - Input field element
   * @param {string} url - URL to fetch suggestions from
   * @param {Object} options - Additional options
   */
  function setupAutocomplete(field, url, options = {}) {
    const {
      minChars = 2,
      maxResults = 10,
      onSelect = null,
    } = options;

    const debouncedSearch = debounce((query) => {
      if (query.length < minChars) {
        return;
      }

      const params = new URLSearchParams({ q: query });
      htmx.ajax("GET", `${url}?${params}`, {
        target: `#${field.id}-results`,
        swap: "innerHTML",
      });
    }, 300);

    field.addEventListener("input", (e) => {
      debouncedSearch(e.target.value);
    });
  }

  /**
   * ===========================================================================
   * TABLE/LIST UTILITIES
   * ===========================================================================
   */

  /**
   * Setup row selection with checkboxes
   * @param {string} tableSelector - CSS selector for table
   */
  function setupRowSelection(tableSelector) {
    const table = document.querySelector(tableSelector);
    if (!table) return;

    const selectAllCheckbox = table.querySelector(
      'input[name="select-all"]'
    );
    const rowCheckboxes = table.querySelectorAll(
      'input[name="select-row"]'
    );

    if (selectAllCheckbox) {
      selectAllCheckbox.addEventListener("change", (e) => {
        rowCheckboxes.forEach((checkbox) => {
          checkbox.checked = e.target.checked;
          checkbox
            .closest("tr")
            ?.classList.toggle("selected", e.target.checked);
        });
      });
    }

    rowCheckboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", (e) => {
        e.target
          .closest("tr")
          ?.classList.toggle("selected", e.target.checked);

        // Update select-all checkbox state
        if (selectAllCheckbox) {
          selectAllCheckbox.checked = 
            Array.from(rowCheckboxes).every(
              (cb) => cb.checked
            );
        }
      });
    });
  }

  /**
   * ===========================================================================
   * NOTIFICATION UTILITIES
   * ===========================================================================
   */

  /**
   * Show notification message
   * @param {string} message - Message text
   * @param {string} level - Level (success, info, warning, error)
   * @param {number} duration - Auto-dismiss duration in ms
   */
  function showNotification(message, level = "info", duration = 5000) {
    const container =
      document.querySelector("[data-notifications]") ||
      document.body;

    const notification = document.createElement("div");
    notification.className = `notification notification-${level}`;
    notification.setAttribute("role", "alert");
    notification.innerHTML = `
      <div class="notification-content">
        <span class="notification-message">${message}</span>
        <button class="notification-close" aria-label="Close">
          <span>&times;</span>
        </button>
      </div>
    `;

    container.appendChild(notification);

    const closeButton = notification.querySelector(".notification-close");
    closeButton.addEventListener("click", () => {
      notification.classList.add("notification-dismiss");
      setTimeout(() => notification.remove(), 300);
    });

    if (duration > 0) {
      setTimeout(() => {
        notification.classList.add("notification-dismiss");
        setTimeout(() => notification.remove(), 300);
      }, duration);
    }
  }

  /**
   * ===========================================================================
   * EXPORT UTILITIES
   * ===========================================================================
   */

  window.alpineHtmxUtils = {
    // Form
    validateField,
    validateForm,
    setupFormValidation,
    submitForm,

    // Modal
    showModal,
    hideModal,

    // Search
    debounce,
    setupAutocomplete,

    // Table
    setupRowSelection,

    // Notifications
    showNotification,
  };

  /**
   * ===========================================================================
   * AUTO-INITIALIZATION
   * ===========================================================================
   */

  document.addEventListener("DOMContentLoaded", () => {
    // Setup form validation for all forms with data-validate attribute
    document.querySelectorAll("form[data-validate]").forEach((form) => {
      setupFormValidation(form);
    });

    // Setup row selection for all tables with data-selectable attribute
    document.querySelectorAll("table[data-selectable]").forEach((table) => {
      setupRowSelection(`#${table.id || "table"}`);
    });

    // Setup autocomplete for all inputs with data-autocomplete attribute
    document.querySelectorAll("input[data-autocomplete]").forEach((field) => {
      const url = field.getAttribute("data-autocomplete");
      setupAutocomplete(field, url);
    });
  });

  // Re-initialize when HTMX adds new items
  htmx.on("htmx:afterSwap", () => {
    document
      .querySelectorAll("form[data-validate]:not([data-validated])")
      .forEach((form) => {
        setupFormValidation(form);
        form.setAttribute("data-validated", "true");
      });
  });
})();


/* ============================================================================
   MERGED FROM: core.js
   ============================================================================ */

(function () {
  "use strict";

  // ── Shared theme utilities loaded from theme-core.js ──────────────────────
  var TC = window.ThemeCore;

  // ── Feedback parsing utilities ────────────────────────────────────────────

  function parseJson(value) {
    if (!value) {
      return null;
    }
    try {
      return JSON.parse(value);
    } catch (_error) {
      return null;
    }
  }

  function parseHxTriggerPayload(headerValue) {
    var parsed = parseJson(headerValue);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return parsed["ui:feedback"] || null;
  }

  function resolveFeedbackTarget(element) {
    if (!element || !(element instanceof Element)) {
      return "global";
    }
    var source = element.closest("[data-ui-feedback-target]");
    if (!source) {
      return "global";
    }
    return source.dataset.uiFeedbackTarget || "global";
  }

  function getSelectedBulkLabel(form) {
    if (!form) {
      return "";
    }
    const selector = form.querySelector('select[name="bulk_action"]');
    if (!selector) {
      return "";
    }
    const option = selector.options[selector.selectedIndex];
    return option ? option.textContent.trim() : "";
  }

  function resolveConfirmMessage(form, submitter) {
    const source = submitter || form;
    if (!source) {
      return "";
    }

    const direct = source.dataset.uiConfirm || form.dataset.uiConfirm;
    if (direct) {
      return direct;
    }

    const template = source.dataset.uiConfirmTemplate || form.dataset.uiConfirmTemplate;
    if (!template) {
      return "";
    }

    const actionLabel = getSelectedBulkLabel(form) || "selected action";
    return template.replace("{action}", actionLabel);
  }

  function getUiStore() {
    if (!window.Alpine || typeof window.Alpine.store !== "function") {
      return null;
    }
    return window.Alpine.store("ui") || null;
  }

  function initUiStore() {
    // UI store is centralized in js/alpine-store.js.
    // Keep this guard so HTMX hooks don't fail when Alpine loads late.
    return Boolean(getUiStore());
  }

  function dispatchFeedback(feedback, sourceElement) {
    if (!feedback) {
      return;
    }
    const ui = getUiStore();
    if (!ui) {
      return;
    }

    if (feedback.toast && feedback.toast.message) {
      ui.notify(feedback.toast.level, feedback.toast.message);
    }

    if (feedback.inline && feedback.inline.message) {
      ui.setInline(
        feedback.inline.target || resolveFeedbackTarget(sourceElement),
        feedback.inline.level,
        feedback.inline.message
      );
    }
  }

  function handleFeedbackFromXhr(xhr, sourceElement) {
    if (!xhr || xhr.__uiFeedbackHandled) {
      return false;
    }
    const feedback = parseHxTriggerPayload(xhr.getResponseHeader("HX-Trigger"));
    if (!feedback) {
      return false;
    }
    xhr.__uiFeedbackHandled = true;
    dispatchFeedback(feedback, sourceElement);
    return true;
  }

  function formatDashboardNumber(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) {
      return value ?? "0";
    }
    return new Intl.NumberFormat().format(numeric);
  }

  function formatDashboardTimestamp(value) {
    const parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) {
      return "";
    }
    return parsed.toLocaleString([], {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function replaceDashboardList(container, rows, emptyMessage) {
    if (!container) {
      return;
    }

    container.replaceChildren();
    if (!Array.isArray(rows) || rows.length === 0) {
      const fallback = document.createElement("li");
      fallback.className = "workspace-muted";
      fallback.textContent = emptyMessage || "No data available.";
      container.appendChild(fallback);
      return;
    }

    rows.forEach((row) => {
      const item = document.createElement("li");

      const left = document.createElement(row.url ? "a" : "span");
      if (row.url) {
        left.href = row.url;
        left.className = "workspace-link";
      }
      left.textContent = row.label || "";

      const right = document.createElement("span");
      right.className = "workspace-muted";
      right.textContent = row.meta || "";

      item.append(left, right);
      container.appendChild(item);
    });
  }

  function bindDashboardLiveSync() {
    const root = document.querySelector("[data-dashboard-live]");
    if (!root) {
      return;
    }

    const statsUrl = root.dataset.statsUrl || "";
    if (!statsUrl) {
      return;
    }

    const metricNodes = Array.from(root.querySelectorAll("[data-dashboard-metric]"));
    const topPostsTarget = root.querySelector("[data-dashboard-top-posts]");
    const topPostsEmpty = topPostsTarget?.dataset.emptyMessage || "Publish posts to collect analytics.";
    const activityTarget = root.querySelector("[data-dashboard-activity]");
    const activityEmpty = activityTarget?.dataset.emptyMessage || "No activity yet.";
    const syncLabel = root.querySelector("[data-dashboard-last-sync]");
    const refreshButton = root.querySelector("[data-dashboard-refresh]");

    let inFlight = false;

    const applyPayload = (payload) => {
      metricNodes.forEach((node) => {
        const key = node.dataset.dashboardMetric;
        if (!key || !(key in payload)) {
          return;
        }
        node.textContent = formatDashboardNumber(payload[key]);
      });

      replaceDashboardList(
        topPostsTarget,
        (payload.dashboard_top_posts || []).map((post) => ({
          label: post.title || "",
          meta: `${formatDashboardNumber(post.views_count || 0)} views`,
          url: post.url || "",
        })),
        topPostsEmpty
      );

      replaceDashboardList(
        activityTarget,
        (payload.dashboard_latest_activity || []).map((post) => ({
          label: post.title || "",
          meta: formatDashboardTimestamp(post.updated_at) || "",
          url: "",
        })),
        activityEmpty
      );

      if (syncLabel) {
        syncLabel.textContent = `Live synced ${new Date().toLocaleTimeString()}`;
      }
    };

    const sync = async () => {
      if (inFlight) {
        return;
      }
      inFlight = true;
      root.classList.add("dashboard-live-loading");
      if (refreshButton) {
        refreshButton.disabled = true;
      }
      try {
        const response = await fetch(statsUrl, {
          method: "GET",
          credentials: "same-origin",
          headers: {
            "X-Requested-With": "XMLHttpRequest",
          },
          cache: "no-store",
        });
        if (!response.ok) {
          throw new Error("dashboard_sync_failed");
        }
        const payload = await response.json();
        applyPayload(payload);
      } catch (_error) {
        if (syncLabel) {
          syncLabel.textContent = "Live sync paused. Click refresh to retry.";
        }
      } finally {
        inFlight = false;
        root.classList.remove("dashboard-live-loading");
        if (refreshButton) {
          refreshButton.disabled = false;
        }
      }
    };

    if (refreshButton) {
      refreshButton.addEventListener("click", () => {
        sync();
      });
    }

    window.setInterval(() => {
      if (document.visibilityState === "visible") {
        sync();
      }
    }, 20000);

    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        sync();
      }
    });
  }

  document.addEventListener("alpine:init", initUiStore);
  document.addEventListener("DOMContentLoaded", function () {
    initUiStore();
    TC.applyTheme(TC.getThemeMode(), TC.getThemePreset());
    TC.bindThemeStateSync();
    TC.bindThemeStorageSync();
    bindDashboardLiveSync();
  });

  document.body.addEventListener("htmx:configRequest", function (event) {
    var token = TC.getCookie("csrftoken");
    if (token) {
      event.detail.headers["X-CSRFToken"] = token;
    }
  });

  document.body.addEventListener("htmx:confirm", function (event) {
    const question = event.detail ? event.detail.question : "";
    if (!question) {
      return;
    }

    const ui = getUiStore();
    if (!ui) {
      return;
    }

    event.preventDefault();
    const sourceElement = event.detail.elt || event.target;
    const inlineTarget = resolveFeedbackTarget(sourceElement);
    const confirmLabel =
      (sourceElement && sourceElement.dataset && sourceElement.dataset.uiConfirmText) ||
      "Confirm";

    ui
      .showConfirm({
        title: "Confirm Action",
        message: question,
        confirmText: confirmLabel,
        cancelText: "Cancel",
        inlineTarget: inlineTarget,
      })
      .then(function (approved) {
        if (approved) {
          event.detail.issueRequest(true);
          return;
        }
        ui.setInline(inlineTarget, "info", "Action canceled.");
      });
  });

  document.body.addEventListener("htmx:afterRequest", function (event) {
    const sourceElement = event.detail.elt || event.target;
    handleFeedbackFromXhr(event.detail.xhr, sourceElement);
  });

  document.body.addEventListener("htmx:responseError", function (event) {
    const sourceElement = event.detail.elt || event.target;
    if (handleFeedbackFromXhr(event.detail.xhr, sourceElement)) {
      return;
    }

    const ui = getUiStore();
    if (!ui) {
      return;
    }

    const statusCode = event.detail && event.detail.xhr ? event.detail.xhr.status : null;
    const message = statusCode
      ? `Request failed (${statusCode}). Please try again.`
      : "Request failed. Please try again.";
    const inlineTarget = resolveFeedbackTarget(sourceElement);
    ui.notify("error", message);
    ui.setInline(inlineTarget, "error", message);
  });

  document.addEventListener(
    "submit",
    function (event) {
      const form = event.target;
      if (!(form instanceof HTMLFormElement)) {
        return;
      }
      if (!form.matches("form[data-ui-confirm], form[data-ui-confirm-template]")) {
        return;
      }
      if (form.dataset.uiConfirmBypass === "1") {
        form.dataset.uiConfirmBypass = "0";
        return;
      }

      const ui = getUiStore();
      if (!ui) {
        return;
      }

      const submitter = event.submitter || null;
      const message = resolveConfirmMessage(form, submitter);
      if (!message) {
        return;
      }

      event.preventDefault();
      const inlineTarget = resolveFeedbackTarget(submitter || form);
      const confirmText = submitter ? submitter.textContent.trim() || "Confirm" : "Confirm";

      ui
        .showConfirm({
          title: "Confirm Action",
          message: message,
          confirmText: confirmText,
          cancelText: "Cancel",
          inlineTarget: inlineTarget,
        })
        .then(function (approved) {
          if (!approved) {
            ui.setInline(inlineTarget, "info", "Action canceled.");
            return;
          }

          form.dataset.uiConfirmBypass = "1";
          if (typeof form.requestSubmit === "function") {
            form.requestSubmit(submitter || undefined);
          } else {
            form.submit();
          }
        });
    },
    true
  );
  // appShell() is the single Alpine root component defined in app.js.
  // Do NOT redefine window.appShell here — that would silently overwrite it.
})();
