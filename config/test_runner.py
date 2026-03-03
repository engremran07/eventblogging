from django.conf import settings
from django.test.runner import DiscoverRunner


class FirstPartyDiscoverRunner(DiscoverRunner):
    """Avoid duplicate package discovery under the top-level `apps` namespace."""

    FIRST_PARTY_APPS = {"blog", "comments", "core", "media", "pages", "seo", "tags"}

    def build_suite(self, test_labels=None, extra_tests=None, **kwargs):
        if test_labels:
            return super().build_suite(test_labels, extra_tests=extra_tests, **kwargs)

        labels = [app for app in settings.INSTALLED_APPS if app in self.FIRST_PARTY_APPS]
        return super().build_suite(labels, extra_tests=extra_tests, **kwargs)
