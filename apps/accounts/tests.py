from django.test import TestCase, override_settings
from django.urls import reverse

from .models import User


class DemoSwitchTests(TestCase):
    def setUp(self):
        self.demo = User.objects.create(username="demo_aina", display_name="Aina", is_synthetic=True)
        self.real = User.objects.create_user("real", password="pw-123456!", display_name="Real")

    @override_settings(DEMO_MODE=False)
    def test_switch_unavailable_outside_demo_mode(self):
        response = self.client.post(reverse("accounts:demo_switch"), {"user_id": self.demo.pk})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertNotContains(self.client.get(reverse("accounts:login")), "Demo accounts")

    @override_settings(DEMO_MODE=True)
    def test_switch_only_to_synthetic_accounts(self):
        response = self.client.post(reverse("accounts:demo_switch"), {"user_id": self.real.pk})
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.client.post(reverse("accounts:demo_switch"), {"user_id": self.demo.pk})
        self.assertEqual(self.client.session["_auth_user_id"], str(self.demo.pk))

    @override_settings(DEMO_MODE=True)
    def test_switch_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:demo_switch")).status_code, 405)


class SignupTests(TestCase):
    def test_signup_cannot_set_synthetic_flag(self):
        self.client.post(reverse("accounts:signup"), {
            "username": "neighbour", "display_name": "Nadia", "is_synthetic": "on",
            "password1": "a-Long-unique-pass-91", "password2": "a-Long-unique-pass-91",
        })
        user = User.objects.get(username="neighbour")
        self.assertFalse(user.is_synthetic)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
