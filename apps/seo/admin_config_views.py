"""
SEO Admin Config Views - Re-export shim.

All views have been split into focused modules:
- seo_views_helpers: Private helper functions and constants
- seo_views_control: Control center shell + tab context builders
- seo_views_actions: POST handlers, CRUD, scan/job management
- seo_views_legacy: Legacy redirect views for backward compat
"""
from .seo_views_actions import *  # noqa: F403
from .seo_views_control import *  # noqa: F403
from .seo_views_helpers import *  # noqa: F403
from .seo_views_legacy import *  # noqa: F403
