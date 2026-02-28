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

    function setActiveSection(section) {
        document.querySelectorAll("#seo-control-tabs .nav-link").forEach(function (link) {
            const isActive = (link.getAttribute("data-control-section") || "") === section;
            link.classList.toggle("active", isActive);
        });
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

    function bindSectionSwapHandlers() {
        document.body.addEventListener("htmx:beforeRequest", function (event) {
            const source = event.detail && event.detail.elt ? event.detail.elt : null;
            if (!source) {
                return;
            }
            const section = source.getAttribute("data-control-section");
            if (section) {
                setActiveSection(section);
            }
        });

        document.body.addEventListener("htmx:afterSwap", function (event) {
            const target = event.detail && event.detail.target ? event.detail.target : null;
            if (!target || target.id !== "seo-control-section") {
                return;
            }
            const requestPath = event.detail.pathInfo && event.detail.pathInfo.requestPath
                ? event.detail.pathInfo.requestPath
                : "";
            const sectionMatch = requestPath.match(/\/section\/([a-z-]+)\//);
            if (sectionMatch) {
                const activeSection = sectionMatch[1];
                setActiveSection(activeSection);
            }
            const scanCard = target.querySelector("[data-seo-scan-monitor='true']");
            if (scanCard) {
                monitorScanCard(scanCard);
            } else {
                stopMonitoring();
            }
        });
    }

    document.addEventListener("DOMContentLoaded", function () {
        bindSectionSwapHandlers();
        const activeLink = document.querySelector("#seo-control-tabs .nav-link.active");
        if (activeLink) {
            setActiveSection(activeLink.getAttribute("data-control-section") || "");
        }
        const scanCard = document.querySelector("[data-seo-scan-monitor='true']");
        if (scanCard) {
            monitorScanCard(scanCard);
        }
    });
})();
