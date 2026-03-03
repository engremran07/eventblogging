/* =============================================================================
   ADMIN.JS  ADMIN WORKSPACE UTILITIES
   =============================================================================
   Consolidated from: core.js, workspace.js, control.js
   Contains:
     1. Admin core (theme glyph toggle, HTMX CSRF, changelist partialization)
     2. Workspace (filter forms, SEO meters, bulk actions, category drag-drop)
     3. SEO control panel (section switching, scan job monitoring)
   ============================================================================= */


/* ============================================================================
   MERGED FROM: core.js
   ============================================================================ */

(function () {
    "use strict";

    // â”€â”€ Shared theme utilities loaded from theme-core.js â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    var TC = window.ThemeCore;
    window.adminGetCookie = TC.getCookie;

    // â”€â”€ Admin-only: FontAwesome sun/moon glyph toggle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    function applyThemeGlyph(mode) {
        var nextMode = mode === "dark" ? "dark" : "light";
        document.querySelectorAll("[data-theme-glyph]").forEach(function (element) {
            element.classList.toggle("fa-sun", nextMode === "dark");
            element.classList.toggle("fa-moon", nextMode !== "dark");
        });
    }

    // Register glyph toggle as a post-apply hook on the shared theme core
    TC.onAfterApply(applyThemeGlyph);

    // â”€â”€ Admin-only: POST toggle to server â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

    // â”€â”€ TOPBAR SCROLL ELEVATION â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


/* ============================================================================
   MERGED FROM: workspace.js
   ============================================================================ */

(function () {
    "use strict";

    function debounce(fn, delay) {
        let timerId = null;
        return function debounced(...args) {
            window.clearTimeout(timerId);
            timerId = window.setTimeout(() => fn.apply(this, args), delay);
        };
    }

    function getCsrfToken() {
        if (typeof window.adminGetCookie === "function") {
            return window.adminGetCookie("csrftoken") || "";
        }
        return "";
    }

    function buildFilteredUrl(form) {
        const baseUrl = form.dataset.filterUrl || form.getAttribute("action") || window.location.pathname;
        const params = new URLSearchParams(new FormData(form));

        params.delete("page");
        for (const [key, value] of Array.from(params.entries())) {
            if (!String(value).trim()) {
                params.delete(key);
            }
        }

        const query = params.toString();
        return query ? `${baseUrl}?${query}` : baseUrl;
    }

    function applyFilters(form) {
        const targetSelector = form.dataset.filterTarget;
        const requestUrl = buildFilteredUrl(form);
        const target = targetSelector ? document.querySelector(targetSelector) : null;

        if (!target || !window.htmx) {
            window.location.href = requestUrl;
            return;
        }

        htmx.ajax("GET", requestUrl, {
            target,
            swap: "innerHTML",
        });
        window.history.replaceState({}, "", requestUrl);
    }

    function initFilterForms(root) {
        const forms = root.querySelectorAll("form[data-workspace-filter]");
        forms.forEach((form) => {
            if (form.dataset.bound === "true") {
                return;
            }
            form.dataset.bound = "true";

            const debouncedApply = debounce(() => applyFilters(form), 320);

            form.addEventListener("change", (event) => {
                if (event.target.matches("select")) {
                    applyFilters(form);
                }
            });

            form.querySelectorAll("[data-filter-live]").forEach((input) => {
                input.addEventListener("input", debouncedApply);
            });

            form.addEventListener("submit", (event) => {
                event.preventDefault();
                applyFilters(form);
            });
        });
    }

    function initSeoScoreMeters(root) {
        root.querySelectorAll("[data-seo-score]").forEach((meter) => {
            const fill = meter.querySelector(".workspace-score-fill");
            const rawScore = Number.parseInt(meter.dataset.seoScore || "0", 10);
            const score = Number.isNaN(rawScore) ? 0 : Math.min(Math.max(rawScore, 0), 100);

            if (!fill) {
                return;
            }

            fill.style.width = `${score}%`;
            fill.classList.remove("is-mid", "is-good");
            if (score >= 80) {
                fill.classList.add("is-good");
            } else if (score >= 50) {
                fill.classList.add("is-mid");
            }
        });
    }

    function getSelectedPostIds(scope) {
        return Array.from(scope.querySelectorAll("[data-select-post]:checked"))
            .map((node) => node.value)
            .filter(Boolean);
    }

    function updateBulkBar(scope) {
        const selectedIds = getSelectedPostIds(scope);
        const bulkBar = scope.querySelector("[data-posts-bulkbar]");
        const countLabel = scope.querySelector("[data-posts-selected-count]");
        const actionButtons = scope.querySelectorAll("[data-posts-bulk-action]");

        if (!bulkBar || !countLabel) {
            return;
        }

        countLabel.textContent = `${selectedIds.length} selected`;
        bulkBar.hidden = selectedIds.length === 0;
        actionButtons.forEach((button) => {
            button.disabled = selectedIds.length === 0;
        });
    }

    function refreshPostsTable() {
        const workspace = document.querySelector('[data-admin-workspace="posts"]');
        const target = document.querySelector("#posts-table-container");
        if (!workspace || !target || !window.htmx) {
            window.location.reload();
            return;
        }

        const listUrl = workspace.dataset.listUrl || window.location.pathname;
        const requestUrl = `${listUrl}${window.location.search}`;

        htmx.ajax("GET", requestUrl, {
            target,
            swap: "innerHTML",
        });
    }

    async function executePostBulkAction(scope, action) {
        const selectedIds = getSelectedPostIds(scope);
        if (!selectedIds.length) {
            return;
        }

        if (action === "delete") {
            const confirmed = window.confirm("Delete selected posts? This action cannot be undone.");
            if (!confirmed) {
                return;
            }
        }

        const bulkUrl = scope.dataset.bulkUrl;
        if (!bulkUrl) {
            return;
        }

        const csrfToken = getCsrfToken();
        const formData = new FormData();
        formData.append("bulk_action", action);
        selectedIds.forEach((postId) => {
            formData.append("selected_posts", postId);
        });

        const response = await fetch(bulkUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "X-CSRFToken": csrfToken,
                "HX-Request": "true",
                "X-Requested-With": "XMLHttpRequest",
            },
            body: formData,
        });

        if (response.ok || response.status === 204) {
            refreshPostsTable();
            return;
        }

        console.error("Bulk action failed", response.status);
    }

    function initPostsBulkScope(root) {
        const scopes = root.querySelectorAll("[data-posts-bulk]");
        scopes.forEach((scope) => {
            if (scope.dataset.bound === "true") {
                return;
            }
            scope.dataset.bound = "true";

            const selectAll = scope.querySelector("[data-select-all-posts]");
            if (selectAll) {
                selectAll.addEventListener("change", () => {
                    scope.querySelectorAll("[data-select-post]").forEach((checkbox) => {
                        checkbox.checked = selectAll.checked;
                    });
                    updateBulkBar(scope);
                });
            }

            scope.querySelectorAll("[data-select-post]").forEach((checkbox) => {
                checkbox.addEventListener("change", () => {
                    if (!selectAll) {
                        updateBulkBar(scope);
                        return;
                    }
                    const boxes = scope.querySelectorAll("[data-select-post]");
                    const selected = scope.querySelectorAll("[data-select-post]:checked");
                    selectAll.checked = boxes.length > 0 && selected.length === boxes.length;
                    updateBulkBar(scope);
                });
            });

            scope.querySelectorAll("[data-posts-bulk-action]").forEach((button) => {
                button.addEventListener("click", () => {
                    executePostBulkAction(scope, button.dataset.postsBulkAction || "");
                });
            });

            updateBulkBar(scope);
        });
    }

    function notifyWorkspace(level, message) {
        const safeMessage = String(message || "").trim();
        if (!safeMessage) {
            return;
        }

        if (window.Alpine && typeof window.Alpine.store === "function") {
            const uiStore = window.Alpine.store("ui");
            if (uiStore && typeof uiStore.notify === "function") {
                uiStore.notify(level || "info", safeMessage);
                return;
            }
        }

        if (level === "error") {
            console.error(safeMessage);
        } else {
            console.info(safeMessage);
        }
    }

    function clearCategoryDragState(scope) {
        scope.querySelectorAll("[data-category-row].is-drag-target").forEach((row) => {
            row.classList.remove("is-drag-target");
        });
        scope.querySelectorAll("[data-category-row].is-dragging").forEach((row) => {
            row.classList.remove("is-dragging");
        });
        const rootDropZone = scope.querySelector("[data-category-drop-root]");
        if (rootDropZone) {
            rootDropZone.classList.remove("is-drag-target");
        }
    }

    const categoryAutoScrollState = new WeakMap();

    function resolveCategoryScrollTarget(scope) {
        const candidates = [];
        const tableScroll = scope.querySelector(".workspace-table-scroll");
        if (tableScroll) {
            candidates.push(tableScroll);
        }
        candidates.push(scope);

        for (const candidate of candidates) {
            if (!candidate || !window.getComputedStyle) {
                continue;
            }
            const styles = window.getComputedStyle(candidate);
            const overflowY = styles ? styles.overflowY : "";
            const scrollableByStyle = overflowY === "auto" || overflowY === "scroll" || overflowY === "overlay";
            if (scrollableByStyle && candidate.scrollHeight > candidate.clientHeight + 1) {
                return candidate;
            }
        }

        return document.scrollingElement || document.documentElement;
    }

    function getScrollViewportRect(scrollTarget) {
        const pageTarget = document.scrollingElement || document.documentElement;
        if (scrollTarget === pageTarget || scrollTarget === document.body || scrollTarget === document.documentElement) {
            return {
                top: 0,
                bottom: window.innerHeight,
            };
        }
        return scrollTarget.getBoundingClientRect();
    }

    function scrollTargetBy(scrollTarget, deltaY) {
        if (!deltaY) {
            return;
        }
        const pageTarget = document.scrollingElement || document.documentElement;
        if (scrollTarget === pageTarget || scrollTarget === document.body || scrollTarget === document.documentElement) {
            window.scrollBy(0, deltaY);
            return;
        }
        const beforeTop = scrollTarget.scrollTop;
        scrollTarget.scrollTop += deltaY;
        const consumed = scrollTarget.scrollTop !== beforeTop;
        if (!consumed) {
            window.scrollBy(0, deltaY);
        }
    }

    function stepCategoryAutoScroll(scope) {
        const state = categoryAutoScrollState.get(scope);
        if (!state || !state.active) {
            return;
        }

        const rect = getScrollViewportRect(state.scrollTarget);
        const threshold = 80;
        const maxStep = 18;
        const pointerY = state.pointerY;
        let deltaY = 0;

        if (pointerY <= rect.top + threshold) {
            const ratio = Math.min(1, (rect.top + threshold - pointerY) / threshold);
            deltaY = -Math.max(4, Math.round(maxStep * ratio));
        } else if (pointerY >= rect.bottom - threshold) {
            const ratio = Math.min(1, (pointerY - (rect.bottom - threshold)) / threshold);
            deltaY = Math.max(4, Math.round(maxStep * ratio));
        }

        scrollTargetBy(state.scrollTarget, deltaY);
        state.rafId = window.requestAnimationFrame(() => stepCategoryAutoScroll(scope));
    }

    function startCategoryAutoScroll(scope, initialPointerY) {
        stopCategoryAutoScroll(scope);
        const state = {
            active: true,
            pointerY: Number.isFinite(initialPointerY) ? initialPointerY : Math.round(window.innerHeight / 2),
            scrollTarget: resolveCategoryScrollTarget(scope),
            rafId: 0,
        };
        categoryAutoScrollState.set(scope, state);
        state.rafId = window.requestAnimationFrame(() => stepCategoryAutoScroll(scope));
    }

    function updateCategoryAutoScrollPointer(scope, pointerY) {
        const state = categoryAutoScrollState.get(scope);
        if (!state || !state.active || !Number.isFinite(pointerY)) {
            return;
        }
        state.pointerY = pointerY;
    }

    function stopCategoryAutoScroll(scope) {
        const state = categoryAutoScrollState.get(scope);
        if (!state) {
            return;
        }
        state.active = false;
        if (state.rafId) {
            window.cancelAnimationFrame(state.rafId);
        }
        categoryAutoScrollState.delete(scope);
    }

    function refreshCategoriesTable(scope) {
        const target = document.querySelector("#categories-table-container");
        if (!target || !window.htmx) {
            window.location.reload();
            return;
        }

        const listUrl = scope.dataset.listUrl || window.location.pathname;
        const requestUrl = `${listUrl}${window.location.search}`;
        htmx.ajax("GET", requestUrl, {
            target,
            swap: "innerHTML",
        });
    }

    async function reparentCategory(scope, categoryId, parentId) {
        const endpoint = scope.dataset.reparentUrl || "";
        if (!endpoint) {
            return;
        }
        if (scope.dataset.reparenting === "true") {
            return;
        }

        const formData = new FormData();
        formData.append("category_id", String(categoryId));
        formData.append("parent_id", parentId ? String(parentId) : "");

        scope.dataset.reparenting = "true";
        try {
            const response = await fetch(endpoint, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });

            let payload = {};
            try {
                payload = await response.json();
            } catch (_error) {
                payload = {};
            }

            if (!response.ok || payload.ok === false) {
                notifyWorkspace("error", payload.message || "Category move failed.");
                return;
            }

            notifyWorkspace("success", payload.message || "Category hierarchy updated.");
            refreshCategoriesTable(scope);
        } catch (_error) {
            notifyWorkspace("error", "Category move failed due to a network error.");
        } finally {
            scope.dataset.reparenting = "false";
        }
    }

    function bindCategoryRow(scope, row) {
        if (!row || row.dataset.bound === "true") {
            return;
        }
        row.dataset.bound = "true";

        row.addEventListener("dragstart", (event) => {
            const categoryId = row.dataset.categoryId;
            if (!categoryId || !event.dataTransfer) {
                return;
            }
            row.classList.add("is-dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", categoryId);
            startCategoryAutoScroll(scope, event.clientY);
        });

        row.addEventListener("dragend", () => {
            clearCategoryDragState(scope);
            stopCategoryAutoScroll(scope);
        });

        row.addEventListener("dragover", (event) => {
            updateCategoryAutoScrollPointer(scope, event.clientY);
            const draggedId = event.dataTransfer ? event.dataTransfer.getData("text/plain") : "";
            if (!draggedId || draggedId === row.dataset.categoryId) {
                return;
            }
            event.preventDefault();
            row.classList.add("is-drag-target");
        });

        row.addEventListener("dragleave", () => {
            row.classList.remove("is-drag-target");
        });

        row.addEventListener("drop", async (event) => {
            event.preventDefault();
            const draggedId = event.dataTransfer ? event.dataTransfer.getData("text/plain") : "";
            const parentId = row.dataset.categoryId || "";
            clearCategoryDragState(scope);
            stopCategoryAutoScroll(scope);

            if (!draggedId || !parentId || draggedId === parentId) {
                return;
            }

            await reparentCategory(scope, draggedId, parentId);
        });
    }

    function initCategoriesDragAndDrop(root) {
        const scopes = root.querySelectorAll("[data-categories-tree]");
        scopes.forEach((scope) => {
            if (scope.dataset.dragDropBound === "true") {
                return;
            }
            scope.dataset.dragDropBound = "true";

            scope.addEventListener("dragover", (event) => {
                updateCategoryAutoScrollPointer(scope, event.clientY);
            });

            scope.querySelectorAll("[data-category-row]").forEach((row) => {
                bindCategoryRow(scope, row);
            });

            const rootDropZone = scope.querySelector("[data-category-drop-root]");
            if (rootDropZone) {
                rootDropZone.addEventListener("dragover", (event) => {
                    updateCategoryAutoScrollPointer(scope, event.clientY);
                    const draggedId = event.dataTransfer
                        ? event.dataTransfer.getData("text/plain")
                        : "";
                    if (!draggedId) {
                        return;
                    }
                    event.preventDefault();
                    rootDropZone.classList.add("is-drag-target");
                });

                rootDropZone.addEventListener("dragleave", () => {
                    rootDropZone.classList.remove("is-drag-target");
                });

                rootDropZone.addEventListener("drop", async (event) => {
                    event.preventDefault();
                    const draggedId = event.dataTransfer
                        ? event.dataTransfer.getData("text/plain")
                        : "";
                    clearCategoryDragState(scope);
                    stopCategoryAutoScroll(scope);
                    if (!draggedId) {
                        return;
                    }
                    await reparentCategory(scope, draggedId, "");
                });
            }
        });
    }

    // ── Media bulk select / delete ─────────────────────────────────────────
    function getSelectedMediaIds(scope) {
        return Array.from(scope.querySelectorAll("[data-select-media]:checked"))
            .map((node) => node.value)
            .filter(Boolean);
    }

    function updateMediaBulkBar(scope) {
        const selectedIds = getSelectedMediaIds(scope);
        const deleteBtn = scope.querySelector("[data-media-bulk-delete]");
        if (!deleteBtn) return;
        deleteBtn.style.display = selectedIds.length > 0 ? "" : "none";
        deleteBtn.disabled = selectedIds.length === 0;
        const icon = '<i class="fas fa-trash"></i> ';
        deleteBtn.innerHTML = selectedIds.length > 0
            ? `${icon}Delete Selected (${selectedIds.length})`
            : `${icon}Delete Selected`;
    }

    async function executeMediaBulkDelete(scope) {
        const selectedIds = getSelectedMediaIds(scope);
        if (!selectedIds.length) return;

        const confirmed = window.confirm(
            `Delete ${selectedIds.length} file(s)? This cannot be undone.`
        );
        if (!confirmed) return;

        const bulkUrl = scope.dataset.bulkUrl;
        if (!bulkUrl) return;

        const csrfToken = getCsrfToken();
        const formData = new FormData();
        formData.append("action", "delete");
        selectedIds.forEach((id) => formData.append("selected", id));

        try {
            const response = await fetch(bulkUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "X-CSRFToken": csrfToken,
                    "HX-Request": "true",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body: formData,
            });

            if (response.ok) {
                // Refresh the media browser via HTMX
                const browserTarget = document.querySelector("#media-browser-content");
                if (browserTarget && window.htmx) {
                    htmx.ajax("GET", window.location.href, {
                        target: browserTarget,
                        swap: "innerHTML",
                    });
                } else {
                    window.location.reload();
                }
            } else {
                console.error("Media bulk delete failed", response.status);
            }
        } catch (err) {
            console.error("Media bulk delete error", err);
        }
    }

    function initMediaBulkScope(root) {
        const scopes = root.querySelectorAll("[data-media-bulk]");
        scopes.forEach((scope) => {
            if (scope.dataset.mediaBound === "true") return;
            scope.dataset.mediaBound = "true";

            const selectAll = scope.querySelector("[data-select-all-media]");
            if (selectAll) {
                selectAll.addEventListener("change", () => {
                    scope.querySelectorAll("[data-select-media]").forEach((cb) => {
                        cb.checked = selectAll.checked;
                    });
                    updateMediaBulkBar(scope);
                });
            }

            scope.querySelectorAll("[data-select-media]").forEach((cb) => {
                cb.addEventListener("change", () => {
                    if (selectAll) {
                        const all = scope.querySelectorAll("[data-select-media]");
                        const checked = scope.querySelectorAll("[data-select-media]:checked");
                        selectAll.checked = all.length > 0 && checked.length === all.length;
                    }
                    updateMediaBulkBar(scope);
                });
            });

            const deleteBtn = scope.querySelector("[data-media-bulk-delete]");
            if (deleteBtn) {
                deleteBtn.addEventListener("click", () => {
                    executeMediaBulkDelete(scope);
                });
            }

            updateMediaBulkBar(scope);
        });
    }

    function initializeWorkspace(root) {
        const scope = root && root.querySelectorAll ? root : document;
        initFilterForms(scope);
        initSeoScoreMeters(scope);
        initPostsBulkScope(scope);
        initMediaBulkScope(scope);
        initCategoriesDragAndDrop(scope);
    }

    document.addEventListener("DOMContentLoaded", () => {
        initializeWorkspace(document);
    });

    document.body.addEventListener("htmx:afterSwap", (event) => {
        const target = event.detail && event.detail.target ? event.detail.target : document;
        initializeWorkspace(target);
    });

    // ── CTRL+S / CMD+S — save current editor form as draft ──────────────────
    document.addEventListener("keydown", (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === "s") {
            const draftBtn = document.querySelector(".post-editor-form button[value='draft']");
            if (!draftBtn) return;
            e.preventDefault();
            draftBtn.click();
            notifyWorkspace("success", "Saving draft\u2026");
        }
    });

    // ── HTMX row-removal animation ─────────────────────────────────────────
    // Add .is-removing to a <tr> before HTMX removes it so CSS can play the
    // row-remove keyframe before the DOM node disappears.
    document.body.addEventListener("htmx:beforeSwap", (event) => {
        const target = event.detail && event.detail.target;
        if (!target) return;
        const row = target.closest("tr");
        if (row && event.detail.xhr && event.detail.xhr.status === 200) {
            row.classList.add("is-removing");
        }
    });
})();


/* ============================================================================
   MERGED FROM: control.js
   ============================================================================ */

(function () {
    "use strict";

    let monitoredJobId = null;
    let monitorIntervalId = null;

    function stopMonitoring() {
        if (monitorIntervalId) {
            window.clearInterval(monitorIntervalId);
            monitorIntervalId = null;
        }
        monitoredJobId = null;
    }

    function monitorScanCard(card) {
        const progressUrl = card.getAttribute("data-progress-url");
        const jobId = card.getAttribute("data-job-id");
        if (!progressUrl) {
            return;
        }
        if (jobId && monitoredJobId === jobId && monitorIntervalId) {
            return;
        }
        stopMonitoring();
        monitoredJobId = jobId;
        const statusNode = card.querySelector("[data-job-status]");
        const progressBar = card.querySelector("[data-job-progress-bar]");
        const progressText = card.querySelector("[data-job-progress-text]");
        const countsNode = card.querySelector("[data-job-counts]");
        const currentNode = card.querySelector("[data-job-current-item]");

        async function refresh() {
            let payload = null;
            try {
                const response = await fetch(progressUrl, {
                    headers: { "X-Requested-With": "XMLHttpRequest" },
                    credentials: "same-origin",
                });
                if (!response.ok) {
                    return false;
                }
                payload = await response.json();
            } catch (_error) {
                return false;
            }
            const status = String(payload.status || "");
            const percent = Number(payload.progress_percent || 0);
            if (statusNode) {
                statusNode.textContent = status;
            }
            if (progressBar) {
                progressBar.style.width = percent + "%";
            }
            if (progressText) {
                progressText.textContent = percent + "%";
            }
            if (countsNode) {
                countsNode.textContent = payload.processed_items + "/" + payload.total_items + " processed";
            }
            if (currentNode) {
                const item = payload.current_item || {};
                if (item.object_id) {
                    currentNode.textContent = "Working on " + item.content_type__model + " #" + item.object_id;
                } else {
                    currentNode.textContent = "";
                }
            }
            return status === "queued" || status === "running";
        }

        monitorIntervalId = window.setInterval(async function () {
            const keepPolling = await refresh();
            if (!keepPolling) {
                stopMonitoring();
            }
        }, 2000);
    }

    // SEO control tab activation — sync nav pills with HTMX tab loads
    document.addEventListener('htmx:afterSwap', function(e) {
        if (e.detail.target && e.detail.target.id === 'seo-tab-content') {
            var nav = document.querySelector('.admin-control-nav');
            if (!nav) return;
            var pills = nav.querySelectorAll('.admin-control-nav-item');
            pills.forEach(function(pill) {
                pill.classList.remove('active');
                // Match active pill based on the hx-get URL containing the section name
                var url = e.detail.requestConfig && e.detail.requestConfig.path;
                if (url && pill.getAttribute('hx-get') && pill.getAttribute('hx-get').indexOf(url.split('/').slice(-2, -1)[0]) !== -1) {
                    pill.classList.add('active');
                }
            });
        }
        // Re-attach scan monitor on any swap containing a scan card
        var target = e.detail && e.detail.target ? e.detail.target : null;
        if (target) {
            var scanCard = target.querySelector("[data-seo-scan-monitor='true']");
            if (scanCard) {
                monitorScanCard(scanCard);
            }
        }
    });

    document.addEventListener("DOMContentLoaded", function () {
        const scanCard = document.querySelector("[data-seo-scan-monitor='true']");
        if (scanCard) {
            monitorScanCard(scanCard);
        }
    });
})();
