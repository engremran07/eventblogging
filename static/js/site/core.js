(function () {
  "use strict";

  function getCookie(name) {
    const cookieValue = document.cookie
      .split("; ")
      .find((row) => row.startsWith(name + "="));
    return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : null;
  }

  function getThemeMode() {
    return document.documentElement.getAttribute("data-bs-theme") || "light";
  }

  function getThemePreset() {
    return document.documentElement.getAttribute("data-app-preset") || "aurora";
  }

  function applyAppearanceVariables(cssVariables) {
    if (!cssVariables || typeof cssVariables !== "object") {
      return;
    }
    Object.entries(cssVariables).forEach(([variableName, variableValue]) => {
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
    const safeMode = mode === "dark" ? "dark" : "light";
    document.querySelectorAll("[data-theme-logo]").forEach((element) => {
      const lightLogo = element.dataset.logoLight || element.getAttribute("src") || "";
      const darkLogo = element.dataset.logoDark || lightLogo;
      const nextSource = safeMode === "dark" ? darkLogo : lightLogo;
      if (nextSource && element.getAttribute("src") !== nextSource) {
        element.setAttribute("src", nextSource);
      }
    });
  }

  function applyTheme(mode, preset, cssVariables) {
    const safeMode = mode === "dark" ? "dark" : "light";
    const safePreset = (preset || "").trim() || getThemePreset();

    document.documentElement.setAttribute("data-bs-theme", safeMode);
    document.documentElement.setAttribute("data-app-preset", safePreset);
    applyAppearanceVariables(cssVariables);
    if (document.body) {
      document.body.setAttribute("data-bs-theme", safeMode);
      document.body.setAttribute("data-app-preset", safePreset);
    }
    applyThemeLogos(safeMode);

    if (window.Alpine && typeof window.Alpine.store === "function") {
      const uiStore = window.Alpine.store("ui");
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
  }

  async function fetchThemeState(url) {
    const response = await fetch(url, {
      method: "GET",
      credentials: "same-origin",
      headers: {
        "X-Requested-With": "XMLHttpRequest",
      },
      cache: "no-store",
    });
    if (!response.ok) {
      throw new Error("theme_state_failed");
    }
    return response.json();
  }

  function bindThemeStateSync() {
    const stateUrl = document.body?.dataset?.themeStateUrl || "";
    if (!stateUrl) {
      return;
    }

    let inFlight = false;
    const sync = async () => {
      if (inFlight || document.visibilityState === "hidden") {
        return;
      }
      inFlight = true;
      try {
        const payload = await fetchThemeState(stateUrl);
        applyTheme(
          payload.mode || getThemeMode(),
          payload.preset || getThemePreset(),
          payload.css_variables || null
        );
      } catch (_error) {
        // Keep current theme when sync request fails.
      } finally {
        inFlight = false;
      }
    };

    window.setInterval(sync, 15000);
    document.addEventListener("visibilitychange", () => {
      if (document.visibilityState === "visible") {
        sync();
      }
    });
  }

  function bindThemeStorageSync() {
    window.addEventListener("storage", (event) => {
      if (event.key !== "global_theme_mode" && event.key !== "global_theme_preset") {
        return;
      }
      let mode = getThemeMode();
      let preset = getThemePreset();
      try {
        mode = localStorage.getItem("global_theme_mode") || mode;
        preset = localStorage.getItem("global_theme_preset") || preset;
      } catch (_error) {
        // localStorage may be unavailable in private mode; ignore.
      }
      applyTheme(mode, preset);
    });
  }

  function normalizeLevel(level) {
    const allowed = ["success", "info", "warning", "error"];
    return allowed.includes(level) ? level : "info";
  }

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
    const parsed = parseJson(headerValue);
    if (!parsed || typeof parsed !== "object") {
      return null;
    }
    return parsed["ui:feedback"] || null;
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
    if (
      key.startsWith("#") ||
      key.startsWith(".") ||
      key.startsWith("[")
    ) {
      return document.querySelector(key);
    }
    return document.querySelector(`[data-ui-feedback-slot="${key}"]`);
  }

  function resolveFeedbackTarget(element) {
    if (!element || !(element instanceof Element)) {
      return "global";
    }
    const source = element.closest("[data-ui-feedback-target]");
    if (!source) {
      return "global";
    }
    return source.dataset.uiFeedbackTarget || "global";
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
    applyTheme(getThemeMode(), getThemePreset());
    bindThemeStateSync();
    bindThemeStorageSync();
    bindDashboardLiveSync();
  });

  document.body.addEventListener("htmx:configRequest", function (event) {
    const token = getCookie("csrftoken");
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

  window.appShell = function appShell() {
    return {
      mobileSearch: false,
    };
  };
})();
