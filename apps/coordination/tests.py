"""Coordination service checks against the real database (G02, G10-G18)."""

import threading
from datetime import timedelta
from unittest import mock

from django.db import connection
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.core.clock import frozen_time
from apps.listings.models import AvailabilityWindow, Listing, ListingPrivate, Locality, Zone

from . import selectors, services
from .models import Plan, PlanEvent, Reservation

BASE = timezone.now().replace(microsecond=0) + timedelta(days=2)


class Scenario:
    """Fictional people and items for a test (O owner, R recipient, P provider, H helper)."""

    def __init__(self):
        locality = Locality.objects.create(name="Test locality", is_synthetic=True)
        self.zone = Zone.objects.create(locality=locality, name="Zone A", latitude="3.0", longitude="101.0")
        self.users = {}

    def user(self, name):
        if name not in self.users:
            self.users[name] = User.objects.create_user(name.lower(), password="pw-123456!", display_name=name)
        return self.users[name]

    def listing(self, owner, title="Shelf", needs_helper=False, start_h=0, hours=2, deadline_h=48):
        listing = Listing.objects.create(
            owner=self.user(owner), title=title, condition="good", width_cm=90, depth_cm=30, height_cm=120,
            needs_extra_helper=needs_helper, ownership_declared=True, zone=self.zone,
            deadline=BASE + timedelta(hours=deadline_h))
        ListingPrivate.objects.create(listing=listing, pickup_details=f"Secret pickup of {owner}", source="manual")
        window = AvailabilityWindow.objects.create(listing=listing, start=BASE + timedelta(hours=start_h),
                                                   end=BASE + timedelta(hours=start_h + hours))
        return listing, window

    def offers(self, listing, window, recipient="R", provider="P", helper=None, vehicle="Van"):
        r = services.offer_to_receive(self.user(recipient), listing.pk, [window], self.zone, f"Secret drop-off of {recipient}")
        mode = "vehicle" if vehicle else "carry"
        t = services.offer_transport(self.user(provider), listing.pk, [window], mode, None, vehicle or "", True)
        h = services.offer_help(self.user(helper), listing.pk, [window]) if helper else None
        return r, t, h

    def activate(self, listing, window, r, t, h=None):
        listing.refresh_from_db()
        return services.activate(listing.owner, listing.pk, window.pk, r.pk, t.pk, h.pk if h else None, listing.revision)

    def make_ready(self, plan):
        services.approve_sharing(plan.owner, plan.pk)
        services.approve_sharing(plan.recipient, plan.pk)
        for uid in plan.participant_ids():
            services.confirm(User.objects.get(pk=uid), plan.pk)
        plan.refresh_from_db()
        return plan


def active_reservations(plan):
    return Reservation.objects.filter(plan=plan, released=False).count()


class PlanLifecycleTests(TestCase):
    def setUp(self):
        self.s = Scenario()
        self.listing, self.window = self.s.listing("O", needs_helper=True)
        self.r, self.t, self.h = self.s.offers(self.listing, self.window, helper="H")

    def test_representative_path_reaches_ready_only_after_everyone(self):  # G12
        plan = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        self.assertEqual(plan.state, Plan.State.AWAITING_CONFIRMATIONS)
        self.assertEqual(active_reservations(plan), 5)  # O, R, P, H and the van
        O, R, P, H = (self.s.user(n) for n in "ORPH")
        with self.assertRaises(services.CoordinationError):
            services.confirm(P, plan.pk)  # confirmation waits for both location approvals
        services.approve_sharing(O, plan.pk)
        self.assertIsNone(selectors.exact_locations(P, plan))  # one approval is not enough
        services.approve_sharing(R, plan.pk)
        self.assertEqual(selectors.exact_locations(P, plan),
                         {"pickup": "Secret pickup of O", "destination": "Secret drop-off of R"})
        for person in (O, R, P):
            plan = services.confirm(person, plan.pk)
            self.assertEqual(plan.state, Plan.State.AWAITING_CONFIRMATIONS)
        plan = services.confirm(H, plan.pk)
        self.assertEqual(plan.state, Plan.State.READY)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.READY)

    def test_only_location_owners_approve_and_outsiders_are_rejected(self):  # G02, G12
        plan = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        with self.assertRaises(services.NotAllowed):
            services.approve_sharing(self.s.user("P"), plan.pk)
        outsider = self.s.user("X")
        for action in (services.approve_sharing, services.confirm, services.leave):
            with self.assertRaises(services.NotAllowed):
                action(outsider, plan.pk)
        self.s.make_ready(plan)
        self.assertIsNone(selectors.plan_for(outsider, plan.pk))
        self.assertIsNone(selectors.exact_locations(outsider, plan))

    def test_only_owner_activates(self):  # G02
        self.listing.refresh_from_db()
        with self.assertRaises(services.NotAllowed):
            services.activate(self.s.user("R"), self.listing.pk, self.window.pk, self.r.pk, self.t.pk, self.h.pk,
                              self.listing.revision)

    def test_hold_expiry_releases_everything(self):  # G13
        with frozen_time(BASE - timedelta(hours=5)):
            plan = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
            services.approve_sharing(plan.owner, plan.pk)
        with frozen_time(BASE - timedelta(hours=5) + timedelta(minutes=21)):
            services.reconcile()
            plan.refresh_from_db()
            self.assertEqual(plan.state, Plan.State.ENDED)
            self.assertEqual(active_reservations(plan), 0)
            with self.assertRaises(services.Stale):
                services.confirm(plan.recipient, plan.pk)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.NEEDS_HELP)

    def test_hold_never_outlives_collection_start(self):  # G13
        with frozen_time(BASE - timedelta(minutes=5)):
            plan = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
            self.assertEqual(plan.hold_expires_at, BASE)
        with frozen_time(BASE):
            services.reconcile()
            plan.refresh_from_db()
            self.assertEqual(plan.state, Plan.State.ENDED)

    def test_pre_start_withdrawal_releases_and_needs_fresh_confirmations(self):  # G14
        other, other_window = self.s.listing("O2", title="Table", start_h=5)
        o_r, o_t, _ = self.s.offers(other, other_window, recipient="R2", provider="P2", vehicle="Car")
        unrelated = self.s.make_ready(self.s.activate(other, other_window, o_r, o_t))
        plan = self.s.make_ready(self.s.activate(self.listing, self.window, self.r, self.t, self.h))
        services.withdraw_offer(self.s.user("P"), "transport", self.t.pk)
        plan.refresh_from_db()
        self.assertEqual(plan.state, Plan.State.ENDED)
        self.assertEqual(active_reservations(plan), 0)
        self.assertIsNone(selectors.exact_locations(self.s.user("H"), plan))
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.NEEDS_HELP)
        unrelated.refresh_from_db()
        self.assertEqual(unrelated.state, Plan.State.READY)
        # A new provider steps in; nobody's earlier confirmation carries over.
        t2 = services.offer_transport(self.s.user("Q"), self.listing.pk, [self.window], "carry", None, "", True)
        new_plan = self.s.activate(self.listing, self.window, self.r, t2, self.h)
        self.assertEqual(new_plan.confirmations.count(), 0)
        self.assertEqual(new_plan.approvals.count(), 0)

    def test_stale_activation_reserves_nothing(self):  # G14
        self.listing.refresh_from_db()
        old_revision = self.listing.revision
        Listing.objects.filter(pk=self.listing.pk).update(revision=old_revision + 1)
        with self.assertRaises(services.Stale):
            services.activate(self.listing.owner, self.listing.pk, self.window.pk, self.r.pk, self.t.pk, self.h.pk,
                              old_revision)
        self.assertFalse(Plan.objects.exists())
        self.assertFalse(Reservation.objects.exists())

    def test_owner_edit_invalidates_plan(self):  # G14
        plan = self.s.make_ready(self.s.activate(self.listing, self.window, self.r, self.t, self.h))
        from apps.listings import services as listing_services
        self.listing.refresh_from_db()
        data = {"title": "Shelf (taller)", "description": "", "condition": "good", "width_cm": 90, "depth_cm": 30,
                "height_cm": 150, "handling_notes": "", "needs_extra_helper": True, "zone": self.s.zone,
                "deadline": self.listing.deadline, "pickup_details": "Secret pickup of O", "latitude": None,
                "longitude": None, "windows": [(self.window.start, self.window.end)], "photos": []}
        listing_services.update_listing(self.listing.owner, self.listing.pk, self.listing.revision, data)
        plan.refresh_from_db()
        self.assertEqual(plan.state, Plan.State.ENDED)
        self.assertEqual(active_reservations(plan), 0)

    def test_repeated_activation_returns_the_same_plan(self):  # G11
        first = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        second = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(Plan.objects.count(), 1)

    def test_failure_mid_activation_rolls_back_everything(self):  # G11
        self.listing.refresh_from_db()
        with mock.patch.object(PlanEvent.objects, "create", side_effect=RuntimeError("disk full")):
            with self.assertRaises(RuntimeError):
                self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        self.assertFalse(Plan.objects.exists())
        self.assertFalse(Reservation.objects.exists())
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.NEEDS_HELP)

    def test_repeated_confirmation_is_harmless(self):  # G11
        plan = self.s.activate(self.listing, self.window, self.r, self.t, self.h)
        services.approve_sharing(plan.owner, plan.pk)
        services.approve_sharing(plan.recipient, plan.pk)
        services.confirm(plan.provider, plan.pk)
        services.confirm(plan.provider, plan.pk)
        self.assertEqual(plan.confirmations.count(), 1)

    def test_ready_plans_block_new_plans_for_the_same_people(self):  # G15
        self.s.make_ready(self.s.activate(self.listing, self.window, self.r, self.t, self.h))
        other, other_window = self.s.listing("O2", title="Table", start_h=1)  # overlaps by one hour
        o_r, o_t, _ = self.s.offers(other, other_window, recipient="R2", provider="P", vehicle="Van")
        suggestion = services.suggest(other)
        self.assertIsNone(suggestion.selected)
        self.assertIn("already committed", suggestion.reasons[0])
        with self.assertRaises(services.Stale):
            self.s.activate(other, other_window, o_r, o_t)

    def test_unselected_users_never_get_private_fields_via_pages(self):  # G02, G12
        plan = self.s.make_ready(self.s.activate(self.listing, self.window, self.r, self.t, self.h))
        outsider = Client()
        outsider.force_login(self.s.user("X"))
        self.assertEqual(outsider.get(reverse("coordination:plan", args=[plan.pk])).status_code, 404)
        body = outsider.get(self.listing.get_absolute_url())
        self.assertNotContains(body, "Secret", status_code=body.status_code)
        crew = Client()
        crew.force_login(self.s.user("H"))
        page = crew.get(reverse("coordination:plan", args=[plan.pk]))
        self.assertContains(page, "Secret pickup of O")
        self.assertContains(page, "Secret drop-off of R")


class OutcomeTests(TestCase):
    def setUp(self):
        self.s = Scenario()
        self.listing, self.window = self.s.listing("O")
        r, t, _ = self.s.offers(self.listing, self.window)
        self.plan = self.s.make_ready(self.s.activate(self.listing, self.window, r, t))
        self.t = t
        self.O, self.R, self.P = (self.s.user(n) for n in "ORP")
        self.started = BASE + timedelta(minutes=30)

    def test_handover_needs_both_records(self):  # G17
        with frozen_time(BASE - timedelta(minutes=1)):
            with self.assertRaises(services.Stale):
                services.record_handover(self.O, self.plan.pk, "handed_over")  # too early
        with frozen_time(self.started):
            plan = services.record_handover(self.O, self.plan.pk, "handed_over")
            self.assertEqual(plan.state, Plan.State.AWAITING_HANDOVER)
            services.record_handover(self.O, self.plan.pk, "handed_over")  # identical repeat
            with self.assertRaises(services.NotAllowed):
                services.record_handover(self.P, self.plan.pk, "handed_over")  # helpers/providers can't report
            plan = services.record_handover(self.R, self.plan.pk, "handed_over")
        self.assertEqual(plan.state, Plan.State.HANDOVER_RECORDED)
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.HANDOVER_RECORDED)
        self.assertEqual(plan.handovers.count(), 2)
        # Early reporting doesn't free the occupied interval (owner, recipient, provider, van).
        self.assertEqual(active_reservations(plan), 4)

    def test_retraction_removes_completion(self):  # G17
        with frozen_time(self.started):
            services.record_handover(self.O, self.plan.pk, "handed_over")
            services.record_handover(self.R, self.plan.pk, "handed_over")
            plan = services.retract_handover(self.R, self.plan.pk)
        self.assertEqual(plan.state, Plan.State.NEEDS_REVIEW)

    def test_disagreement_needs_review(self):  # G17
        with frozen_time(self.started):
            services.record_handover(self.O, self.plan.pk, "handed_over")
            plan = services.record_handover(self.R, self.plan.pk, "stayed")
        self.assertEqual(plan.state, Plan.State.NEEDS_REVIEW)

    def test_never_ready_plan_cannot_complete(self):  # G17
        listing, window = self.s.listing("O3", title="Lamp table", start_h=10)
        r, t, _ = self.s.offers(listing, window, recipient="R3", provider="P3", vehicle=None)
        plan = self.s.activate(listing, window, r, t)
        with frozen_time(BASE + timedelta(hours=10, minutes=5)):
            with self.assertRaises(services.CoordinationError):
                services.record_handover(listing.owner, plan.pk, "handed_over")

    def test_late_withdrawal_goes_to_review_not_relisting(self):  # G16
        with frozen_time(self.started):
            services.withdraw_offer(self.P, "transport", self.t.pk)
            self.plan.refresh_from_db()
            self.assertEqual(self.plan.state, Plan.State.NEEDS_REVIEW)
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.state, Listing.State.NEEDS_REVIEW)
            self.assertIsNone(selectors.exact_locations(self.R, self.plan))  # access revoked
            self.assertEqual(active_reservations(self.plan), 4)  # occupied interval kept
            services.record_handover(self.O, self.plan.pk, "stayed")
            self.listing.refresh_from_db()
            self.assertEqual(self.listing.state, Listing.State.NEEDS_REVIEW)  # one party isn't enough
            services.record_handover(self.R, self.plan.pk, "stayed")
        self.listing.refresh_from_db()
        self.assertEqual(self.listing.state, Listing.State.NEEDS_HELP)

    def test_exact_location_access_ends_seven_days_after_collection(self):  # G18
        with frozen_time(self.plan.end + timedelta(days=6)):
            self.assertIsNotNone(selectors.exact_locations(self.P, self.plan))
        with frozen_time(self.plan.end + timedelta(days=7)):
            self.assertIsNone(selectors.exact_locations(self.P, self.plan))


class ConcurrentActivationTests(TransactionTestCase):
    """G10: two real database connections race to book the same provider."""

    def test_only_one_conflicting_activation_succeeds(self):
        s = Scenario()
        a, wa = s.listing("OA", title="Chair")
        b, wb = s.listing("OB", title="Desk")
        ra, ta, _ = s.offers(a, wa, recipient="RA", provider="P", vehicle="Van")
        rb, tb, _ = s.offers(b, wb, recipient="RB", provider="P", vehicle="Van")
        barrier, outcomes = threading.Barrier(2), []

        def run(listing, window, r, t):
            try:
                barrier.wait()
                outcomes.append(("ok", s.activate(listing, window, r, t).pk))
            except services.Stale as exc:
                outcomes.append(("stale", exc.message))
            except Exception as exc:  # e.g. database busy beyond the timeout
                outcomes.append(("error", repr(exc)))
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=args) for args in ((a, wa, ra, ta), (b, wb, rb, tb))]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        kinds = sorted(k for k, _ in outcomes)
        self.assertEqual(kinds, ["ok", "stale"], outcomes)
        self.assertEqual(Plan.objects.count(), 1)
        winner = Plan.objects.get()
        self.assertEqual(Reservation.objects.count(), 4)  # owner, recipient, provider, van of the winner only
        self.assertFalse(Reservation.objects.exclude(plan=winner).exists())

    def test_disjoint_activations_both_succeed(self):
        s = Scenario()
        a, wa = s.listing("OA", title="Chair")
        b, wb = s.listing("OB", title="Desk")
        ra, ta, _ = s.offers(a, wa, recipient="RA", provider="PA", vehicle="Van")
        rb, tb, _ = s.offers(b, wb, recipient="RB", provider="PB", vehicle="Car")
        barrier, outcomes = threading.Barrier(2), []

        def run(listing, window, r, t):
            try:
                barrier.wait()
                outcomes.append(s.activate(listing, window, r, t).pk)
            finally:
                connection.close()

        threads = [threading.Thread(target=run, args=args) for args in ((a, wa, ra, ta), (b, wb, rb, tb))]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual(Plan.objects.count(), 2)
