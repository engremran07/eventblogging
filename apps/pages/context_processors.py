import logging

from core.models import FeatureControlSettings

from .models import Page

logger = logging.getLogger(__name__)


POLICY_SLUGS = {"privacy-policy", "terms-of-service", "cookie-policy"}


def navigation_pages(request):
    try:
        controls = FeatureControlSettings.get_solo()
        pages = (
            Page.objects.published()
            .filter(show_in_navigation=True)
            .only("title", "slug", "nav_label", "nav_order")
            .order_by("nav_order", "title")[:12]
        )
        if not controls.enable_policy_pages:
            pages = pages.exclude(slug__in=POLICY_SLUGS)
    except Exception:
        logger.warning("Failed to load navigation pages for context processor", exc_info=True)
        pages = []
    return {"navigation_pages": pages}
