/**
 * theme-core.js — Shared Theme Management
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
        return document.documentElement.getAttribute("data-bs-theme") || "light";
    }

    function getThemePreset() {
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

        window.setInterval(sync, 15000);
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

    // Public API — consumed by admin/core.js, site/core.js, alpine-store.js
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
