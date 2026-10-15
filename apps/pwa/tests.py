import json

from django.test import TestCase


class PwaTests(TestCase):
    def test_manifest_is_installable_shape(self):
        response = self.client.get("/manifest.webmanifest")
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        data = json.loads(response.content)
        self.assertEqual(data["display"], "standalone")
        self.assertEqual(data["start_url"], "/")
        sizes = {icon["sizes"] for icon in data["icons"]}
        self.assertTrue({"192x192", "512x512"} <= sizes)
        self.assertTrue(any(icon.get("purpose") == "maskable" for icon in data["icons"]))

    def test_service_worker_never_caches_pages_or_photos(self):
        response = self.client.get("/sw.js")
        self.assertEqual(response["Content-Type"], "application/javascript")
        body = response.content.decode()
        self.assertIn('"/offline/"', body)
        self.assertIn('url.pathname.startsWith("/static/")', body)
        self.assertNotIn("/photos/", body)
        self.assertNotIn("cache.put", body)

    def test_offline_page_has_no_personal_content(self):
        response = self.client.get("/offline/")
        self.assertContains(response, "You're offline")
        self.assertNotContains(response, "csrfmiddlewaretoken")
