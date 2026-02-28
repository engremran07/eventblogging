# Admin UI Deep Audit

Generated: 2026-02-27 12:34:31

## Findings
- Unified admin shell anchor: `templates/admin/base_site.html` + `static/css/tokens.css`, `design-system.css`, `base.css`, `components.css`, `layout.css`.
- Workspace views add `static/css/admin/workspace.css`; dashboard adds `static/css/admin/dashboard.css`; SEO control adds `static/css/admin/control.css`.
- SEO duplicate flash rendering existed in `templates/seo/admin/base.html` and was removed (now single message source from base shell).
- Search icon overlap risk addressed in `static/css/layout.css` by increasing input left padding and non-interactive icon.
- Admin profile navigation in sidebar/topbar now stays inside admin workspace (`admin_users_list`) to avoid style context drift.

## Admin CSS Files (3)
```text
D:\DjangoBlog\static\css\admin\control.css
D:\DjangoBlog\static\css\admin\dashboard.css
D:\DjangoBlog\static\css\admin\workspace.css
```

## Admin JS Files (3)
```text
D:\DjangoBlog\static\js\admin\control.js
D:\DjangoBlog\static\js\admin\core.js
D:\DjangoBlog\static\js\admin\workspace.js
```

## Admin Template Matrix (34)
| Template | Extends admin/base_site | CSS refs | JS refs | Inline style attrs |
|---|---|---|---|---:|
| D:\DjangoBlog\templates\admin\admin_password_reset_email.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\auth\user\double_delete_confirmation.html | yes | - | - | 1 |
| D:\DjangoBlog\templates\admin\auth_alert.html | yes | - | - | 0 |
| D:\DjangoBlog\templates\admin\auth_form.html | yes | - | - | 0 |
| D:\DjangoBlog\templates\admin\base_site.html | no | css/base.css, css/components.css, css/design-system.css, css/layout.css, css/tokens.css | js/admin/core.js, js/alpine-store.js | 0 |
| D:\DjangoBlog\templates\admin\comments\comment_item.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\comments\list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\comments\table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\dashboard.html | yes | - | - | 20 |
| D:\DjangoBlog\templates\admin\groups\list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\groups\table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\index.html | yes | css/admin/dashboard.css | - | 0 |
| D:\DjangoBlog\templates\admin\pages\list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\pages\table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\partials\sidebar.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\partials\topbar.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\posts\editor.html | yes | - | - | 32 |
| D:\DjangoBlog\templates\admin\posts\list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\posts\table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\settings.html | yes | css/admin/workspace.css | - | 0 |
| D:\DjangoBlog\templates\admin\taxonomy\categories_list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\taxonomy\categories_table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\taxonomy\flat_list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\taxonomy\flat_table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\admin\users\list.html | yes | css/admin/workspace.css | js/admin/workspace.js | 0 |
| D:\DjangoBlog\templates\admin\users\table.html | no | - | - | 0 |
| D:\DjangoBlog\templates\seo\admin\base.html | yes | css/admin/control.css | js/admin/control.js | 0 |
| D:\DjangoBlog\templates\seo\admin\control.html | no | - | - | 0 |
| D:\DjangoBlog\templates\seo\admin\partials\seo_control_interlinking.html | no | - | - | 1 |
| D:\DjangoBlog\templates\seo\admin\partials\seo_control_results.html | no | - | - | 0 |
| D:\DjangoBlog\templates\seo\admin\partials\seo_control_scan.html | no | - | - | 1 |
| D:\DjangoBlog\templates\seo\admin\partials\seo_control_settings.html | no | - | - | 0 |
| D:\DjangoBlog\templates\seo\admin\partials\seo_control_suggestions.html | no | - | - | 1 |
| D:\DjangoBlog\templates\seo\admin\queue_edit.html | no | - | - | 0 |

## Recommendations
- Keep `tokens.css` as single source of truth; use compatibility aliases only for legacy selectors.
- Continue reducing inline styles in `templates/admin/posts/editor.html` by moving to shared classes in `workspace.css`.
- Keep SEO and workspace sections on the same button/table badge semantics through `control.css` + `workspace.css` token rules.
