(function () {
    "use strict";

    const SOURCE_SELECTOR = "textarea[data-summernote='markdown']";
    const INIT_MARKER = "summernoteBridgeReady";
    const FORM_BIND_MARKER = "summernoteBridgeSubmitBound";
    const MAX_RETRY = 40;
    const RETRY_DELAY_MS = 150;
    let retries = 0;

    function dependenciesReady() {
        return Boolean(
            window.jQuery &&
                window.jQuery.fn &&
                typeof window.jQuery.fn.summernote === "function" &&
                typeof window.TurndownService === "function"
        );
    }

    function summernotePluginButtons() {
        const plugins =
            window.jQuery &&
            window.jQuery.summernote &&
            window.jQuery.summernote.plugins
                ? window.jQuery.summernote.plugins
                : {};
        const buttons = [];
        if (plugins.cleaner) {
            buttons.push("cleaner");
        }
        if (plugins.imageAttributes) {
            buttons.push("imageAttributes");
        }
        return buttons;
    }

    function customButtons() {
        const $ = window.jQuery;

        const quoteIcon =
            '<svg class="sn-note-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="M6.4 3.5C3.9 4.1 2.7 5.8 2.7 8.4v3.9h4.1V8.1H4.8c.1-1.4.8-2.2 2.3-2.6l-.7-2zm6.7 0c-2.5.6-3.7 2.3-3.7 4.9v3.9h4.1V8.1h-2c.1-1.4.8-2.2 2.3-2.6l-.7-2z"/>' +
            "</svg>";
        const printIcon =
            '<svg class="sn-note-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">' +
            '<path fill="currentColor" d="M4 1.5h8v3H4z"/><path fill="currentColor" d="M4 10h8v4.5H4z"/>' +
            '<path fill="currentColor" d="M2 5.5h12c.8 0 1.5.7 1.5 1.5v3.5H13V8H3v2.5H.5V7c0-.8.7-1.5 1.5-1.5z"/>' +
            "</svg>";

        function printHtml(html, editorContainer) {
            const $frame = $('<iframe name="summernotePrintFrame" width="0" height="0" frameborder="0" src="about:blank" style="visibility:hidden"></iframe>');
            $frame.appendTo(editorContainer.parent());
            const $head = $frame.contents().find("head");
            $("style, link[rel=stylesheet]", document).each(function () {
                $head.append($(this).clone());
            });
            $frame.contents().find("body").html(html);
            window.setTimeout(function () {
                $frame[0].contentWindow.focus();
                $frame[0].contentWindow.print();
                $frame.remove();
            }, 200);
        }

        return {
            quote: function (context) {
                var ui = $.summernote && $.summernote.ui;
                if (!ui) { return $('<button class="note-btn">Quote</button>')[0]; }
                return ui
                    .button({
                        className: "note-btn-quote",
                        contents: quoteIcon,
                        tooltip: "Blockquote",
                        click: function () {
                            context.invoke("editor.formatBlock", "blockquote");
                        },
                    })
                    .render();
            },
            print: function (context) {
                var ui = $.summernote && $.summernote.ui;
                if (!ui) { return $('<button class="note-btn">Print</button>')[0]; }
                return ui
                    .button({
                        className: "note-btn-print",
                        contents: printIcon,
                        tooltip: "Print",
                        click: function () {
                            const html = context.invoke("code");
                            printHtml(html, context.layoutInfo.editor);
                        },
                    })
                    .render();
            },
        };
    }

    function createTurndownService() {
        const service = new window.TurndownService({
            headingStyle: "atx",
            codeBlockStyle: "fenced",
            bulletListMarker: "-",
            emDelimiter: "*",
        });
        if (window.turndownPluginGfm && typeof window.turndownPluginGfm.gfm === "function") {
            service.use(window.turndownPluginGfm.gfm);
        }
        // Keep rich-text specific tags as raw HTML so Summernote-only formatting survives markdown sync.
        service.keep([
            "span",
            "font",
            "table",
            "thead",
            "tbody",
            "tfoot",
            "tr",
            "th",
            "td",
            "colgroup",
            "col",
            "sup",
            "sub",
        ]);
        return service;
    }

    function markdownToHtml(markdownValue) {
        const markdown = (markdownValue || "").trim();
        if (!markdown) {
            return "";
        }
        if (window.marked && typeof window.marked.parse === "function") {
            return window.marked.parse(markdown);
        }
        return markdown;
    }

    function dispatchForHtmx(textarea) {
        // A single bubbling "input" event is enough for all HTMX triggers
        // and live-indicator listeners on the textarea.
        textarea.dispatchEvent(new Event("input", { bubbles: true }));
    }

    function normalizeMarkdown(value) {
        return (value || "").replace(/\n{3,}/g, "\n\n").trim();
    }

    /**
     * Force-apply critical layout styles on the Summernote toolbar, buttons,
     * and frame AFTER Summernote has built its DOM.
     *
     * Why JS in addition to CSS?
     * -  summernote-bs5.min.css loads AFTER our stylesheets (same <head>)
     *    so same-specificity rules from Summernote win the cascade.
     * -  Our CSS uses !important, but Summernote's JS may set inline styles
     *    during initialisation that interfere with layout.
     * -  style.setProperty(prop, val, 'important') creates inline !important
     *    declarations — the highest priority origin in the CSS cascade.
     *    Nothing can override these except another inline !important set later.
     *
     * This function is idempotent and safe to call multiple times.
     */
    function enforceToolbarStyles(host, height) {
        const editor = host.querySelector(".note-editor.note-frame");
        if (!editor) {
            return;
        }

        // ── Frame: undo .card padding, allow dropdowns to escape ──
        editor.style.setProperty("padding", "0", "important");
        editor.style.setProperty("overflow", "visible", "important");

        // Also strip the .card class that causes our global CSS bleeding
        // (belt-and-suspenders alongside the CSS :not() exclusion)
        editor.classList.remove("card");
        const toolbar = editor.querySelector(".note-toolbar");
        if (toolbar) {
            toolbar.classList.remove("card-header");
        }

        // ── Toolbar: the critical layout fix ──
        if (toolbar) {
            toolbar.style.setProperty("display", "flex", "important");
            toolbar.style.setProperty("flex-wrap", "wrap", "important");
            toolbar.style.setProperty("align-items", "center", "important");
            toolbar.style.setProperty("gap", "0.35rem", "important");
            toolbar.style.setProperty("padding", "0.5rem", "important");
            toolbar.style.setProperty("margin", "0", "important");
            toolbar.style.setProperty("margin-bottom", "0", "important");
            toolbar.style.setProperty("overflow", "visible", "important");
            toolbar.style.setProperty("font-weight", "normal", "important");
            toolbar.style.setProperty("font-size", "inherit", "important");
            toolbar.style.setProperty("max-height", "none", "important");
            toolbar.style.setProperty("height", "auto", "important");
            toolbar.style.setProperty("visibility", "visible", "important");
            // Force a reflow so the browser paints the corrected layout
            // before the user sees the toolbar in a half-rendered state.
            void toolbar.offsetHeight;
        }

        // ── Button groups: ensure they display inline-flex ──
        const groups = editor.querySelectorAll(".note-btn-group");
        groups.forEach(function (group) {
            group.style.setProperty("display", "inline-flex", "important");
            group.style.setProperty("align-items", "center", "important");
            group.style.setProperty("margin", "0", "important");
            group.style.setProperty("visibility", "visible", "important");
        });

        // ── Buttons: undo global .btn bloating ──
        const buttons = editor.querySelectorAll(".note-btn");
        buttons.forEach(function (btn) {
            btn.style.setProperty("padding", "0.35rem 0.55rem", "important");
            btn.style.setProperty("font-size", "0.875rem", "important");
            btn.style.setProperty("font-weight", "500", "important");
            btn.style.setProperty("min-height", "2rem", "important");
            btn.style.setProperty("line-height", "1", "important");
            btn.style.setProperty("white-space", "nowrap", "important");
        });

        // ── Editing area height: ensure Summernote's inline height sticks ──
        const editingArea = editor.querySelector(".note-editing-area");
        if (editingArea) {
            editingArea.style.setProperty("overflow", "hidden", "");
        }
        const editable = editor.querySelector(".note-editable");
        if (editable) {
            editable.style.setProperty("min-height", height + "px", "");
            editable.style.setProperty("overflow-y", "auto", "");
        }

        // ── Also strip Bootstrap's .card-block on editable ──
        if (editable) {
            editable.classList.remove("card-block");
        }
    }

    function initSingleEditor(textarea) {
        if (!textarea || textarea.dataset[INIT_MARKER] === "1") {
            return;
        }

        const host = document.createElement("div");
        host.className = "summernote-bridge-host";
        textarea.insertAdjacentElement("afterend", host);
        textarea.classList.add("summernote-source-hidden");

        const turndown = createTurndownService();
        const $host = window.jQuery(host);
        const pluginButtons = summernotePluginButtons();
        const hasImageAttributes = pluginButtons.includes("imageAttributes");
        const toolbarGroups = [
            ["style", ["style"]],
            ["font", ["bold", "italic", "underline", "strikethrough", "superscript", "subscript", "clear"]],
            ["fontname", ["fontname"]],
            ["fontsize", ["fontsize"]],
            ["color", ["color"]],
            ["para", ["ul", "ol", "paragraph", "quote", "height"]],
            ["table", ["table"]],
            ["insert", ["link", "picture", "video", "hr"]],
            ["history", ["undo", "redo"]],
            ["view", ["fullscreen", "codeview", "help", "print"]],
        ];
        if (pluginButtons.length) {
            toolbarGroups.splice(8, 0, ["plugins", pluginButtons]);
        }

        const editorHeight = Number.parseInt(textarea.dataset.summernoteHeight || "420", 10);
        const effectiveHeight = Number.isFinite(editorHeight) ? editorHeight : 420;
        $host.summernote({
            height: effectiveHeight,
            tabsize: 2,
            dialogsInBody: true,
            codemirror: window.CodeMirror
                ? {
                      mode: "text/html",
                      htmlMode: true,
                      lineNumbers: true,
                      lineWrapping: true,
                  }
                : null,
            styleTags: [
                "p",
                { title: "Blockquote", tag: "blockquote", className: "blockquote", value: "blockquote" },
                "pre",
                "h1",
                "h2",
                "h3",
                "h4",
                "h5",
                "h6",
            ],
            toolbar: toolbarGroups,
            buttons: customButtons(),
            cleaner: {
                action: "both",
                newline: "<br>",
            },
            imageAttributes: {
                icon: '<i class="bi bi-image"></i>',
                removeEmpty: false,
                disableUpload: false,
            },
            popover: {
                image: [
                    ["resize", ["resizeFull", "resizeHalf", "resizeQuarter", "resizeNone"]],
                    ["float", ["floatLeft", "floatRight", "floatNone"]],
                    ...(hasImageAttributes ? [["attributes", ["imageAttributes"]]] : []),
                    ["remove", ["removeMedia"]],
                ],
                link: [["link", ["linkDialogShow", "unlink"]]],
                air: [
                    ["color", ["color"]],
                    ["font", ["bold", "underline", "clear"]],
                    ["para", ["ul", "paragraph", "height"]],
                    ["table", ["table"]],
                    ["insert", ["link", "picture"]],
                ],
            },
            callbacks: {
                onInit: function () {
                    // Summernote's official "I'm fully ready" signal.
                    // Enforce toolbar styles once more after all plugins and
                    // toolbar buttons have been fully rendered.
                    enforceToolbarStyles(host, effectiveHeight);
                },
            },
        });

        // ── Force-fix toolbar layout AFTER Summernote creates its DOM ──
        // Run immediately, then again after a short delay to catch any
        // deferred Summernote rendering (plugin buttons, async toolbar paint).
        enforceToolbarStyles(host, effectiveHeight);
        window.setTimeout(function () {
            enforceToolbarStyles(host, effectiveHeight);
        }, 100);
        window.setTimeout(function () {
            enforceToolbarStyles(host, effectiveHeight);
        }, 500);

        const initialHtml = markdownToHtml(textarea.value);
        $host.summernote("code", initialHtml);

        const syncBackToMarkdown = function () {
            const html = ($host.summernote("code") || "").trim();
            let markdown = "";
            if (html && html !== "<p><br></p>") {
                markdown = normalizeMarkdown(turndown.turndown(html));
            }
            if (textarea.value === markdown) {
                return;
            }
            textarea.value = markdown;
            dispatchForHtmx(textarea);
        };

        // summernote.change already fires after paste and keyup — no need to double-bind.
        $host.on("summernote.change", syncBackToMarkdown);
        syncBackToMarkdown();

        const form = textarea.closest("form");
        if (form && form.dataset[FORM_BIND_MARKER] !== "1") {
            form.addEventListener("submit", function () {
                syncBackToMarkdown();
            });
            form.dataset[FORM_BIND_MARKER] = "1";
        }

        textarea.dataset[INIT_MARKER] = "1";
    }

    function initEditors(root) {
        const scope = root && root.querySelectorAll ? root : document;
        scope.querySelectorAll(SOURCE_SELECTOR).forEach(initSingleEditor);
    }

    function start(root) {
        if (dependenciesReady()) {
            initEditors(root);
            return;
        }
        if (retries >= MAX_RETRY) {
            return;
        }
        retries += 1;
        window.setTimeout(function () {
            start(root);
        }, RETRY_DELAY_MS);
    }

    document.addEventListener("DOMContentLoaded", function () {
        start(document);
    });

    document.body.addEventListener("htmx:afterSwap", function (event) {
        const target = event.detail && event.detail.target ? event.detail.target : document;
        start(target);
    });
})();
