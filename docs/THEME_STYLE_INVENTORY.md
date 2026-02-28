# Theme + Template Inventory

Generated: 2026-02-27 12:27:27

## Centralized Theme Sources
- static/css/tokens.css (canonical design tokens)
- static/css/design-system.css (legacy compatibility aliases only)
- static/css/base.css (base element styling using tokens)
- static/css/components.css (shared UI components + Summernote bridge skin)
- static/css/layout.css (admin shell + topbar/sidebar layout)
- static/css/site/core.css (frontend site shell + blog-specific styling)
- static/css/admin/control.css (SEO/admin control plane styling)

## Rich Editor Integration
- templates/partials/summernote_assets.html (shared CDN bundle for Summernote + Turndown + Marked)
- static/js/summernote-bridge.js (Summernote <-> Markdown sync bridge)

## Color Token Families (Canonical + Alias)
- Canonical: --bg, --surface-1/2/3, --border, --border-focus, --text-primary/secondary/muted/inverse, --accent, --accent-hover, --success, --warning, --danger, --info
- Alias compatibility: --color-bg/*, --color-primary-*, --color-secondary-*, --color-success-*, --color-warning-*, --color-danger-*, --color-info-*, --color-gray-*
- Legacy aliases mapped: --sp-*, --r-*, --text-1/2/3, --accent-dim, --topbar-h

## Static Files (17)
```text
static\css\admin\control.css
static\css\admin\dashboard.css
static\css\admin\workspace.css
static\css\base.css
static\css\components.css
static\css\design-system.css
static\css\layout.css
static\css\site\core.css
static\css\tokens.css
static\img\home-logo.svg
static\js\admin\control.js
static\js\admin\core.js
static\js\admin\workspace.js
static\js\alpine-store.js
static\js\site\alpine-htmx-utils.js
static\js\site\core.js
static\js\summernote-bridge.js
```

## Template Files (80)
```text
templates\admin\admin_password_reset_email.html
templates\admin\auth\user\double_delete_confirmation.html
templates\admin\auth_alert.html
templates\admin\auth_form.html
templates\admin\base_site.html
templates\admin\comments\comment_item.html
templates\admin\comments\list.html
templates\admin\comments\table.html
templates\admin\dashboard.html
templates\admin\groups\list.html
templates\admin\groups\table.html
templates\admin\index.html
templates\admin\pages\list.html
templates\admin\pages\table.html
templates\admin\partials\sidebar.html
templates\admin\partials\topbar.html
templates\admin\posts\editor.html
templates\admin\posts\list.html
templates\admin\posts\table.html
templates\admin\settings.html
templates\admin\taxonomy\categories_list.html
templates\admin\taxonomy\categories_table.html
templates\admin\taxonomy\flat_list.html
templates\admin\taxonomy\flat_table.html
templates\admin\users\list.html
templates\admin\users\table.html
templates\base.html
templates\blog\dashboard.html
templates\blog\home.html
templates\blog\partials\category_tree.html
templates\blog\partials\comment_list.html
templates\blog\partials\comments_section.html
templates\blog\partials\editor_preview.html
templates\blog\partials\feed_panel.html
templates\blog\partials\newsletter_panel.html
templates\blog\partials\post_card.html
templates\blog\partials\post_card_reactions.html
templates\blog\partials\post_list.html
templates\blog\partials\quick_preview_content.html
templates\blog\partials\reaction_bar.html
templates\blog\partials\search_suggestions.html
templates\blog\post_confirm_delete.html
templates\blog\post_detail.html
templates\blog\post_form.html
templates\blog\post_revisions.html
templates\components\alert.html
templates\components\badge.html
templates\components\button.html
templates\components\card.html
templates\components\data_table.html
templates\components\modal.html
templates\components\stat_widget.html
templates\components\toast.html
templates\maintenance.html
templates\pages\page_confirm_delete.html
templates\pages\page_detail.html
templates\pages\page_form.html
templates\pages\page_list.html
templates\pages\page_manage.html
templates\pages\page_revisions.html
templates\pages\partials\editor_preview.html
templates\partials\summernote_assets.html
templates\policies\policy_detail.html
templates\policies\policy_index.html
templates\registration\login.html
templates\registration\profile.html
templates\registration\register.html
templates\robots.txt
templates\seo\admin\base.html
templates\seo\admin\control.html
templates\seo\admin\partials\seo_control_interlinking.html
templates\seo\admin\partials\seo_control_results.html
templates\seo\admin\partials\seo_control_scan.html
templates\seo\admin\partials\seo_control_settings.html
templates\seo\admin\partials\seo_control_suggestions.html
templates\seo\admin\queue_edit.html
templates\seo\partials\live_check_panel.html
templates\sitemap.xml
templates\sitemap.xsl
templates\sitemap_index.xml
```

## Notes
- tokens.css remains single source of truth for runtime theming.
- design-system.css now only supplies compatibility aliases and animation/z-index helpers.
- SEO control templates are visually normalized with token-based admin styles.
- Rich editor now writes Markdown back to source fields for SEO/audit compatibility.
