from django.test import TestCase
from django.urls import reverse


class TagApiRoutingTests(TestCase):
    def test_tag_autocomplete_route_is_under_single_api_prefix(self):
        self.assertEqual(reverse("tags:tag_autocomplete"), "/api/tag-autocomplete/")
        response = self.client.get(reverse("tags:tag_autocomplete"))
        self.assertEqual(response.status_code, 200)

    def test_category_autocomplete_route_is_under_single_api_prefix(self):
        self.assertEqual(
            reverse("tags:category_autocomplete"),
            "/api/category-autocomplete/",
        )
        response = self.client.get(reverse("tags:category_autocomplete"))
        self.assertEqual(response.status_code, 200)
