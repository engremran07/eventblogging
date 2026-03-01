(function () {
    "use strict";

    // ── Shared theme utilities loaded from theme-core.js ────────────────────
    var TC = window.ThemeCore;
    window.adminGetCookie = TC.getCookie;

    // ── Admin-only: FontAwesome sun/moon glyph toggle ───────────────────────
    function applyThemeGlyph(mode) {
        var nextMode = mode === "dark" ? "dark" : "light";
        document.querySelectorAll("[data-theme-glyph]").forEach(function (element) {
            element.classList.toggle("fa-sun", nextMode === "dark");
            element.classList.toggle("fa-moon", nextMode !== "dark");
        });
    }

    // Register glyph toggle as a post-apply hook on the shared theme core
    TC.onAfterApply(applyThemeGlyph);

    // ── Admin-only: POST toggle to server ───────────────────────────────────
    function postThemeToggle(url) {
        return fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": TC.getCookie("csrftoken") || "",
                "X-Requested-With": "XMLHttpRequest",
            },
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("theme_toggle_failed");
            }
            return response.json();
        });
    }

    function bindThemeToggleButton() {
        document.addEventListener("click", function (event) {
            var button = event.target.closest("[data-theme-toggle]");
            if (!button) {
                return;
            }
            event.preventDefault();

            var toggleUrl = document.body && document.body.dataset
                ? document.body.dataset.adminThemeToggleUrl || ""
                : "";
            var nextMode = TC.getThemeMode() === "dark" ? "light" : "dark";
            button.disabled = true;

            var done = function () { button.disabled = false; };

            if (toggleUrl) {
                postThemeToggle(toggleUrl)
                    .then(function (payload) {
                        TC.applyTheme(
                            payload.mode || nextMode,
                            payload.preset || TC.getThemePreset(),
                            payload.css_variables || null
                        );
                    })
                    .catch(function () {
                        TC.applyTheme(nextMode, TC.getThemePreset());
                    })
                    .finally(done);
            } else {
                TC.applyTheme(nextMode, TC.getThemePreset());
                done();
            }
        });
    }

    function bindHtmxCsrfHeader() {
        if (!window.htmx || !document.body) {
            return;
        }
        document.body.addEventListener("htmx:configRequest", function (event) {
            var token = TC.getCookie("csrftoken");
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
        TC.applyTheme(TC.getThemeMode(), TC.getThemePreset());
        bindHtmxCsrfHeader();
        bindThemeToggleButton();
        TC.bindThemeStateSync();
        TC.bindThemeStorageSync();
        bindChangelistPartialization();
        bindTopbarScrollElevation();
    });
})();
