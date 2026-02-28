# Comments Audit Matrix (Second Pass)

Date: 2026-02-27  
Scope: comment domain data flow, moderation logic, admin workflows, and real queue behavior.

| Area | Finding | Impact | Fix |
|---|---|---|---|
| Comment creation workflow | New comments were effectively always approved. | Moderation queue could remain artificially empty and badge counts looked stale. | Added real moderation gate via `FeatureControlSettings.moderate_comments`; non-managers are queued when enabled. |
| Global comment controls | Global comments toggle existed in settings model but was not enforced in comment create path. | “Comments disabled” could be bypassed by direct post. | Enforced `FeatureControlSettings.enable_comments` in `comment_create`. |
| Pending comment visibility | Non-manager authenticated users could not see their own pending comments. | Author experience mismatch after submitting moderated comments. | Updated comment queryset logic so users can see their own pending comments while public users still only see approved comments. |
| Default comment admin | Changelist lacked stronger moderation operations (filters/actions/select_related). | Slower moderation and weaker auditability at scale. | Expanded `CommentAdmin` with approval status, bulk approve/unapprove actions, richer filters/search, ordering, and select_related. |
| Custom admin comments workspace | Filter structure only covered status + search. | Hard to isolate moderation by post and run deterministic review passes. | Added post-scoped filter and sort options to comments workspace list/filter form. |
| Admin settings page comments section | Comment toggles were effectively placeholder-only. | UI state did not guarantee backend behavior. | Wired `allow_comments` and `moderate_comments` POST handling to `FeatureControlSettings` persistence. |

## Result

- Pending comment queues are now real operational signals, not static placeholders.
- Comment moderation behavior is deterministic and settings-driven.
- Admin comments workflows now support post-specific review and clearer bulk moderation.
