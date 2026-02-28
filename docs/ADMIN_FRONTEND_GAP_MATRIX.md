# Admin Frontend Gap Matrix (Second Pass)

Date: 2026-02-27  
Scope: HTMX + Alpine + Bootstrap behavior audit for admin pages and related workflows.

| Page / Area | HTMX Coverage | Alpine Coverage | Bootstrap Coverage | Gap Found | Fix Applied |
|---|---|---|---|---|---|
| `/admin/` dashboard | Medium | Low | Medium | Sidebar queue badges were static placeholders (`5`, `12`) and not tied to real queue data. | Replaced with live counts from `admin_nav_badges` context processor (cached, staff/admin scoped). |
| `/admin/posts/` workspace | High | Low | Medium | Pagination worked with HTMX swaps but did not update browser URL. | Added `hx-push-url="true"` on pagination links and HTMX attributes on filter form. |
| `/admin/comments/` workspace | High | Low | Medium | Same URL/history gap as posts workspace. | Added `hx-push-url="true"` on pagination links and HTMX attributes on filter form. |
| `/admin/posts/<id>/edit/` workspace editor | Low | Low | Medium | Status action buttons were not authoritative; taxonomy fields were missing; Tagulous/auto-taxonomy was not executed from this editor. | Reworked editor workflow: action-to-status mapping, taxonomy inputs (topic/tags/categories), canonical URL and publish flags, and `apply_auto_taxonomy_to_post` execution after save. |
| `/admin/blog/tagulous_post_tags/` | Low | N/A | Medium | Tagulous admin defaults did not expose strong filter/list controls for operations. | Upgraded Tagulous admins with explicit list displays, filters, ordering, readonly counters, and search fields. |
| `/admin/blog/tagulous_post_categories/` | Low | N/A | Medium | Tree taxonomy review lacked structured columns/filtering for hierarchy governance. | Added parent/level/path/count/protected visibility and filtering in `CategoryTagAdmin`. |
| `/admin/blog/tagulous_post_primary_topic/` | Low | N/A | Medium | Topic admin lacked curated list/search controls. | Added standardized flat tag admin controls via shared `FlatTagAdmin`. |
| `/admin/pages/page/` | Low | N/A | Medium | Page changelist filters were weaker than blog/tag workflows (missing author and published-time focus). | Expanded `PageAdmin` list display/search/filter coverage (author, nav label, published timestamp). |
| `/admin/auth/user/` and `/admin/auth/group/` | Low | N/A | Medium | Group admin had limited operational visibility; user filters were not aligned with staff workflows. | Strengthened `CustomUserAdmin` list/search/filter ordering and introduced `CustomGroupAdmin` with user/permission counts. |
| Default Django changelists (`users/groups/tagulous/pages`) | Low | N/A | Medium | Navigation/filter/search/sort/pagination forced full page reloads. | Added shared HTMX changelist partialization engine (merged into `js/admin/core.js`) to swap `#changelist` fragment with URL history support. |

## Data Reality Check

- Active Django connection is PostgreSQL `djangoblog` (`127.0.0.1:5432`) and currently contains **0 posts / 0 comments / 0 pages**.
- Cross-database scan with current credentials found historical content in another local DB: `postgreswl` with **57 posts**.

## Remaining Frontend Risks

- Default Django changelist pages (Tagulous/Users/Groups/Pages) still use full-page navigation; not all views are HTMX-partialized by design.
- Editor preview/focus buttons are UI stubs and currently non-destructive toggles only.
