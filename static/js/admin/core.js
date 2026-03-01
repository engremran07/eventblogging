(function () {
    "use strict";

    function getCookie(name) {
        const cookieValue = document.cookie
            .split("; ")
            .find((row) => row.startsWith(name + "="));
        return cookieValue ? decodeURIComponent(cookieValue.split("=")[1]) : null;
    }
    window.adminGetCookie = getCookie;

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
        Object.entries(cssVariables).forEach(function ([variableName, variableValue]) {
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
        const nextMode = mode === "dark" ? "dark" : "light";
        document.querySelectorAll("[data-theme-logo]").forEach(function (element) {
            const lightLogo = element.dataset.logoLight || element.getAttribute("src") || "";
            const darkLogo = element.dataset.logoDark || lightLogo;
            const nextSource = nextMode === "dark" ? darkLogo : lightLogo;
            if (nextSource && element.getAttribute("src") !== nextSource) {
                element.setAttribute("src", nextSource);
            }
        });
    }

    function applyThemeGlyph(mode) {
        const nextMode = mode === "dark" ? "dark" : "light";
        document.querySelectorAll("[data-theme-glyph]").forEach(function (element) {
            element.classList.toggle("fa-sun", nextMode === "dark");
            element.classList.toggle("fa-moon", nextMode !== "dark");
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

        applyThemeGlyph(safeMode);
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

    async function postThemeToggle(url) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": getCookie("csrftoken") || "",
                "X-Requested-With": "XMLHttpRequest",
            },
        });
        if (!response.ok) {
            throw new Error("theme_toggle_failed");
        }
        return response.json();
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

    function bindThemeToggleButton() {
        document.addEventListener("click", async function (event) {
            const button = event.target.closest("[data-theme-toggle]");
            if (!button) {
                return;
            }
            event.preventDefault();

            const toggleUrl = document.body?.dataset?.adminThemeToggleUrl || "";
            const nextMode = getThemeMode() === "dark" ? "light" : "dark";
            button.disabled = true;

            try {
                if (toggleUrl) {
                    const payload = await postThemeToggle(toggleUrl);
                    applyTheme(
                        payload.mode || nextMode,
                        payload.preset || getThemePreset(),
                        payload.css_variables || null
                    );
                } else {
                    applyTheme(nextMode, getThemePreset());
                }
            } catch (_error) {
                applyTheme(nextMode, getThemePreset());
            } finally {
                button.disabled = false;
            }
        });
    }

    function bindThemeStateSync() {
        const stateUrl = document.body?.dataset?.themeStateUrl || "";
        if (!stateUrl) {
            return;
        }

        let inFlight = false;

        const sync = async function () {
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

    function bindHtmxCsrfHeader() {
        if (!window.htmx || !document.body) {
            return;
        }
        document.body.addEventListener("htmx:configRequest", function (event) {
            const token = getCookie("csrftoken");
            if (token) {
                event.detail.headers["X-CSRFToken"] = token;
            }
        });
    }

    function getChangelistRoot() {
        return document.querySelector("#changelist");
    }

    function isChangelistPage() {
        return Boolean(getChangelistRoot());
    }

    function sameChangelistPath(url) {
        try {
            const parsed = new URL(url, window.location.origin);
            return (
                parsed.origin === window.location.origin
                && parsed.pathname === window.location.pathname
            );
        } catch (_error) {
            return false;
        }
    }

    function requestChangelist(url, pushUrl) {
        const target = getChangelistRoot();
        if (!target || !window.htmx) {
            window.location.href = url;
            return;
        }

        htmx.ajax("GET", url, {
            target,
            swap: "outerHTML",
            select: "#changelist",
        });

        if (pushUrl) {
            window.history.pushState({ adminChangelist: true }, "", url);
        }
    }

    function onChangelistLinkClick(event) {
        if (!isChangelistPage()) {
            return;
        }

        const link = event.target.closest("#changelist a[href]");
        if (!link || link.target || link.hasAttribute("download")) {
            return;
        }

        const href = link.getAttribute("href");
        if (!href || href.startsWith("#") || href.startsWith("javascript:")) {
            return;
        }
        if (!sameChangelistPath(link.href)) {
            return;
        }

        event.preventDefault();
        requestChangelist(link.href, true);
    }

    function onChangelistSearchSubmit(event) {
        if (!isChangelistPage()) {
            return;
        }

        const form = event.target;
        if (!(form instanceof HTMLFormElement) || form.id !== "changelist-search") {
            return;
        }

        event.preventDefault();
        const base = new URL(window.location.pathname, window.location.origin);
        const params = new URLSearchParams(new FormData(form));
        for (const [key, value] of Array.from(params.entries())) {
            if (!String(value).trim()) {
                params.delete(key);
            }
        }
        const query = params.toString();
        const url = query ? `${base.toString()}?${query}` : base.toString();
        requestChangelist(url, true);
    }

    function onChangelistPopState() {
        if (!isChangelistPage()) {
            return;
        }
        requestChangelist(window.location.href, false);
    }

    function bindChangelistPartialization() {
        document.addEventListener("click", onChangelistLinkClick);
        document.addEventListener("submit", onChangelistSearchSubmit);
        window.addEventListener("popstate", onChangelistPopState);
    }

    // ── TOPBAR SCROLL ELEVATION ────────────────────────────────────────────────
    // Adds .topbar-elevated to the admin topbar when the page is scrolled so CSS
    // can apply a glassmorphism / shadow upgrade via the workspace.css class.
    function bindTopbarScrollElevation() {
        const topbar = document.querySelector(".workspace-topbar, .admin-topbar, [data-topbar]");
        if (!topbar) return;
        const update = () => {
            topbar.classList.toggle("topbar-elevated", window.scrollY > 8);
        };
        window.addEventListener("scroll", update, { passive: true });
        update();
    }

    document.addEventListener("DOMContentLoaded", function () {
        applyTheme(getThemeMode(), getThemePreset());
        bindHtmxCsrfHeader();
        bindThemeToggleButton();
        bindThemeStateSync();
        bindThemeStorageSync();
        bindChangelistPartialization();
        bindTopbarScrollElevation();
    });
})();
