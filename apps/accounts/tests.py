from django.test import Client, TestCase, override_settings
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

    @override_settings(DEMO_MODE=True)
    def test_invalid_or_inactive_accounts_do_not_change_session(self):
        self.client.force_login(self.demo)
        self.real.is_synthetic = True
        self.real.is_active = False
        self.real.save()
        for user_id in ("", "not-an-id", self.real.pk, 999999):
            with self.subTest(user_id=user_id):
                self.assertEqual(self.client.post(reverse("accounts:demo_switch"), {
                    "user_id": user_id,
                }).status_code, 404)
                self.assertEqual(self.client.session["_auth_user_id"], str(self.demo.pk))

    @override_settings(DEMO_MODE=True)
    def test_switch_requires_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("accounts:demo_switch"), {"user_id": self.demo.pk}).status_code, 403)
        self.assertNotIn("_auth_user_id", client.session)

    @override_settings(DEMO_MODE=True)
    def test_only_known_read_pages_are_return_destinations(self):
        for path in ("https://example.com/", "//example.com/", "/accounts/logout/", "/items/new/",
                     "/plans/1/confirm/", "/missing/", "/activity/?next=https://example.com"):
            with self.subTest(path=path):
                response = self.client.post(reverse("accounts:demo_switch"), {"user_id": self.demo.pk, "next": path})
                self.assertRedirects(response, reverse("listings:nearby"))
        response = self.client.post(reverse("accounts:demo_switch"), {
            "user_id": self.demo.pk, "next": reverse("listings:activity"),
        })
        self.assertRedirects(response, reverse("listings:activity"))

    def test_account_menu_is_demo_only_and_excludes_real_accounts(self):
        self.client.force_login(self.demo)
        with override_settings(DEMO_MODE=True):
            response = self.client.get(reverse("listings:activity"))
            self.assertContains(response, 'Try another demo person')
            self.assertContains(response, f'<option value="{self.demo.pk}" selected>Aina</option>')
            self.assertNotContains(response, f'<option value="{self.real.pk}"')
        with override_settings(DEMO_MODE=False):
            self.assertNotContains(self.client.get(reverse("listings:activity")), 'Try another demo person')


@override_settings(DEMO_MODE=True)
class DemoWalkthroughTests(TestCase):
    def setUp(self):
        from apps.coordination.tests import Scenario

        self.scenario = Scenario()
        self.listing, window = self.scenario.listing("O")
        offers = self.scenario.offers(self.listing, window)
        self.plan = self.scenario.activate(self.listing, window, *offers)
        self.outsider = self.scenario.user("X")
        User.objects.update(is_synthetic=True)
        self.url = reverse("coordination:plan", args=[self.plan.pk])

    def switch(self, user, path=None):
        return self.client.post(reverse("accounts:demo_switch"), {
            "user_id": user.pk, "next": path or self.url,
        }, follow=True)

    def test_switch_keeps_plan_and_each_person_must_confirm(self):
        from apps.coordination.models import Plan

        for user in (self.plan.owner, self.plan.recipient):
            response = self.switch(user)
            self.assertEqual(response.redirect_chain, [(self.url, 302)])
            self.assertNotContains(response, "Secret pickup of O")
            self.client.post(reverse("coordination:plan_action", args=[self.plan.pk, "approve"]))
        for index, user in enumerate((self.plan.owner, self.plan.recipient, self.plan.provider), 1):
            response = self.switch(user)
            self.assertContains(response, "Secret pickup of O")
            self.assertEqual(self.plan.confirmations.count(), index - 1)
            self.client.post(reverse("coordination:plan_action", args=[self.plan.pk, "confirm"]))
            self.plan.refresh_from_db()
            expected = Plan.State.READY if index == 3 else Plan.State.AWAITING_CONFIRMATIONS
            self.assertEqual(self.plan.state, expected)
            self.assertEqual(self.plan.confirmations.count(), index)

    def test_outsider_returns_nearby_without_private_plan_details(self):
        from apps.coordination import services

        services.approve_sharing(self.plan.owner, self.plan.pk)
        services.approve_sharing(self.plan.recipient, self.plan.pk)
        response = self.switch(self.outsider)
        self.assertEqual(response.redirect_chain, [(reverse("listings:nearby"), 302)])
        self.assertNotContains(response, "Secret pickup of O")
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_switch_from_owner_crew_page_goes_to_visible_item(self):
        response = self.switch(self.plan.recipient, reverse("coordination:crew", args=[self.listing.pk]))
        self.assertEqual(response.redirect_chain, [(reverse("listings:detail", args=[self.listing.pk]), 302)])
        response = self.switch(self.outsider, reverse("listings:detail", args=[self.listing.pk]))
        self.assertEqual(response.redirect_chain, [(reverse("listings:nearby"), 302)])


class SignupTests(TestCase):
    def test_signup_cannot_set_synthetic_flag(self):
        self.client.post(reverse("accounts:signup"), {
            "username": "neighbour", "display_name": "Nadia", "is_synthetic": "on",
            "password1": "a-Long-unique-pass-91", "password2": "a-Long-unique-pass-91",
        })
        user = User.objects.get(username="neighbour")
        self.assertFalse(user.is_synthetic)
        self.assertEqual(self.client.session["_auth_user_id"], str(user.pk))
