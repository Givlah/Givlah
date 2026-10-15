"""Matcher checks (G04-G09). Pure data, no database."""

import itertools
import random
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from . import matcher
from .matcher import Busy, ListingIn, OfferIn, WindowIn

NOW = datetime(2026, 11, 2, 0, 0, tzinfo=timezone.utc)
T = lambda h: NOW + timedelta(hours=h)


def listing(lid, owner, windows, needs_helper=False, deadline_h=200, created_h=0):
    return ListingIn(lid, owner, needs_helper, T(deadline_h), T(created_h),
                     tuple(WindowIn(wid, T(s), T(e)) for wid, s, e in windows))


def offer(oid, lid, user, window_ids, vehicle=None, fit=True):
    return OfferIn(oid, lid, user, frozenset(window_ids), vehicle, fit)


class CandidateGenerationTests(SimpleTestCase):
    def test_missing_roles_are_explained(self):  # G04
        l = listing(1, owner=100, windows=[(1, 10, 12)], needs_helper=True)
        cands, reasons = matcher.generate(l, [], [], [], [], NOW)
        self.assertEqual(cands, [])
        self.assertEqual(len(reasons), 3)
        self.assertIn("No one has asked for it yet.", reasons)
        self.assertIn("No one has offered transport yet.", reasons)
        self.assertIn("Needs a second person to help carry.", reasons)

    def test_undeclared_fit_never_counts(self):  # G04
        l = listing(1, 100, [(1, 10, 12)])
        cands, reasons = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 300, [1], fit=False)], [], [], NOW)
        self.assertEqual(cands, [])
        self.assertIn("Transport offered, but no one has confirmed the item fits.", reasons)

    def test_no_shared_time(self):  # G04
        l = listing(1, 100, [(1, 10, 12), (2, 14, 16)])
        cands, reasons = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 300, [2])], [], [], NOW)
        self.assertEqual(cands, [])
        self.assertEqual(reasons, ["The offers don't share a common collection time."])

    def test_past_windows_and_windows_after_deadline_ignored(self):  # G04
        l = listing(1, 100, [(1, -3, -1), (2, 10, 12)], deadline_h=11)
        cands, reasons = matcher.generate(l, [offer(1, 1, 200, [1, 2])], [offer(2, 1, 300, [1, 2])], [], [], NOW)
        self.assertEqual(cands, [])
        self.assertIn("No upcoming collection time is left before the deadline.", reasons)

    def test_recipient_can_transport_and_is_counted_once(self):  # G05
        l = listing(1, 100, [(1, 10, 12)])
        cands, _ = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 200, [1], vehicle=7)], [], [], NOW)
        self.assertEqual(len(cands), 1)
        self.assertEqual(cands[0].resources, frozenset({"user:100", "user:200", "vehicle:7"}))

    def test_carry_locally_needs_no_vehicle(self):  # G05
        l = listing(1, 100, [(1, 10, 12)])
        cands, _ = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 300, [1])], [], [], NOW)
        self.assertEqual(cands[0].resources, frozenset({"user:100", "user:200", "user:300"}))

    def test_extra_helper_must_be_a_different_person(self):  # G05
        l = listing(1, 100, [(1, 10, 12)], needs_helper=True)
        recipients, transports = [offer(1, 1, 200, [1])], [offer(2, 1, 300, [1])]
        cands, reasons = matcher.generate(l, recipients, transports, [offer(3, 1, 300, [1])], [], NOW)
        self.assertEqual(cands, [])
        self.assertIn("must be someone other than", reasons[0])
        cands, _ = matcher.generate(l, recipients, transports, [offer(3, 1, 300, [1]), offer(4, 1, 400, [1])], [], NOW)
        self.assertEqual([c.helper.user_id for c in cands], [400])

    def test_overlapping_commitment_blocks_even_with_different_window_ids(self):  # G06
        l = listing(1, 100, [(1, 10, 12)])
        busy = [Busy("user:300", T(11), T(13))]  # another plan, different window, overlapping time
        cands, reasons = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 300, [1])], [], busy, NOW)
        self.assertEqual(cands, [])
        self.assertIn("already committed", reasons[0])

    def test_adjacent_commitment_allowed(self):  # G06: [10,12) and [12,14) don't overlap
        l = listing(1, 100, [(1, 10, 12)])
        busy = [Busy("user:300", T(12), T(14)), Busy("vehicle:7", T(8), T(10))]
        cands, _ = matcher.generate(l, [offer(1, 1, 200, [1])], [offer(2, 1, 300, [1], vehicle=7)], [], busy, NOW)
        self.assertEqual(len(cands), 1)


class SolveTests(SimpleTestCase):
    def witness(self):
        """G07: same interval; A needs P+X, B needs P+Y, C needs Q+X; everyone else distinct.
        P and Q are transport providers, X and Y are extra helpers."""
        P, Q, X, Y = 900, 901, 902, 903
        listings = [listing(1, 101, [(1, 10, 12)], True, deadline_h=50),   # A: earliest deadline
                    listing(2, 102, [(2, 10, 12)], True, deadline_h=60),   # B
                    listing(3, 103, [(3, 10, 12)], True, deadline_h=70)]   # C
        recipients = [offer(1, 1, 201, [1]), offer(2, 2, 202, [2]), offer(3, 3, 203, [3])]
        transports = [offer(11, 1, P, [1]), offer(12, 2, P, [2]), offer(13, 3, Q, [3])]
        helpers = [offer(21, 1, X, [1]), offer(22, 2, Y, [2]), offer(23, 3, X, [3])]
        return listings, recipients, transports, helpers

    def test_independent_witness_beats_scarcity_greedy(self):  # G07
        listings, recipients, transports, helpers = self.witness()
        result = matcher.solve(listings, recipients, transports, helpers, [], NOW)
        self.assertEqual(result.status, "ok")
        self.assertEqual(sorted(result.selected), [2, 3])
        # A deadline-first greedy takes A, which uses both P and X, and then nothing else fits.
        greedy, used = [], set()
        for l in listings:
            for c in result.candidates[l.id]:
                if not (c.resources & used):
                    greedy.append(l.id)
                    used |= c.resources
                    break
        self.assertEqual(greedy, [1])
        self.assertEqual(brute_force_count(listings, recipients, transports, helpers, []), 2)

    def test_ties_prefer_earlier_deadline(self):
        l1 = listing(1, 101, [(1, 10, 12)], deadline_h=80)
        l2 = listing(2, 102, [(2, 10, 12)], deadline_h=40)
        result = matcher.solve([l1, l2], [offer(1, 1, 201, [1]), offer(2, 2, 202, [2])],
                               [offer(3, 1, 900, [1]), offer(4, 2, 900, [2])], [], [], NOW)
        self.assertEqual(list(result.selected), [2])

    def test_existing_commitments_are_never_displaced(self):  # G15
        l = listing(1, 101, [(1, 10, 12)])
        busy = [Busy("user:900", T(9), T(11))]
        result = matcher.solve([l], [offer(1, 1, 201, [1])], [offer(2, 1, 900, [1])], [], busy, NOW)
        self.assertEqual(result.selected, {})

    def test_over_limit_is_explicit(self):  # G09
        many = [listing(i, 100 + i, [(i, 10, 12)]) for i in range(1, 10)]
        result = matcher.solve(many, [], [], [], [], NOW)
        self.assertEqual(result.status, "over_limit")
        self.assertEqual(result.selected, {})

    def test_too_many_candidates_is_explicit(self):  # G09
        l = listing(1, 100, [(1, 10, 12), (2, 12, 14), (3, 14, 16)])
        recipients = [offer(i, 1, 200 + i, [1, 2, 3]) for i in range(1, 4)]
        transports = [offer(10 + i, 1, 300 + i, [1, 2, 3]) for i in range(1, 4)]  # 3 x 3 x 3 = 27 candidates
        result = matcher.solve([l], recipients, transports, [], [], NOW)
        self.assertEqual(result.status, "over_limit")
        self.assertEqual(result.selected, {})

    def test_timeout_never_claims_optimum(self):  # G09
        listings, recipients, transports, helpers = self.witness()
        ticks = itertools.count()
        result = matcher.solve(listings, recipients, transports, helpers, [], NOW, time_budget=2,
                               clock=lambda: next(ticks))
        self.assertEqual(result.status, "incomplete")

    def test_maximum_size_solves_within_five_seconds(self):  # G09
        import time
        rng = random.Random(9)
        listings, recipients, transports, helpers = random_instance(rng, n_listings=8, max_candidates=24)
        started = time.perf_counter()
        result = matcher.solve(listings, recipients, transports, helpers, [], NOW)
        elapsed = time.perf_counter() - started
        self.assertEqual(result.status, "ok")
        self.assertLess(elapsed, 5)

    def test_agrees_with_brute_force_on_generated_inputs(self):  # G08
        rng = random.Random(2026)
        checked = ties = 0
        for _ in range(300):
            listings, recipients, transports, helpers = random_instance(rng)
            busy = [Busy(f"user:{rng.choice([900, 901, 902, 903])}", T(rng.choice([9, 10, 11])), T(rng.choice([12, 13])))
                    ] if rng.random() < 0.3 else []
            result = matcher.solve(listings, recipients, transports, helpers, busy, NOW)
            if result.status != "ok":
                continue
            expected, n_optimal = brute_force(listings, recipients, transports, helpers, busy)
            self.assertEqual(len(result.selected), expected)
            self.assertTrue(valid_selection(result.selected.values()))
            checked += 1
            ties += n_optimal > 1
        self.assertGreater(checked, 200)
        print(f"\n  G08: {checked} generated cases matched brute force; {ties} had tied optima")


def random_instance(rng, n_listings=None, max_candidates=24):
    """Small instances drawn from a shared pool of people so roles combine and compete."""
    while True:
        n = n_listings or rng.randint(1, 5)
        people = [900, 901, 902, 903, 904]
        listings, recipients, transports, helpers = [], [], [], []
        oid = 1
        for lid in range(1, n + 1):
            windows = [(lid * 10 + k, 10 + 2 * k + rng.choice([0, 1]), 12 + 2 * k + rng.choice([0, 1])) for k in range(rng.randint(1, 2))]
            l = listing(lid, rng.choice(people + [100 + lid]), windows, needs_helper=rng.random() < 0.4,
                        deadline_h=rng.randint(20, 90), created_h=rng.randint(-50, 0))
            listings.append(l)
            wids = [w.id for w in l.windows]
            for _ in range(rng.randint(0, 2)):
                recipients.append(offer(oid, lid, rng.choice(people + [200 + lid]), rng.sample(wids, rng.randint(1, len(wids))))); oid += 1
            for _ in range(rng.randint(0, 2)):
                transports.append(offer(oid, lid, rng.choice(people), rng.sample(wids, rng.randint(1, len(wids))),
                                        vehicle=rng.choice([None, 1, 2]), fit=rng.random() < 0.9)); oid += 1
            for _ in range(rng.randint(0, 2) if l.needs_helper else 0):
                helpers.append(offer(oid, lid, rng.choice(people), rng.sample(wids, rng.randint(1, len(wids))))); oid += 1
        total = sum(len(matcher.generate(l, [o for o in recipients if o.listing_id == l.id],
                                         [o for o in transports if o.listing_id == l.id],
                                         [o for o in helpers if o.listing_id == l.id], [], NOW)[0]) for l in listings)
        if total <= max_candidates:
            return listings, recipients, transports, helpers


def valid_selection(cands):
    cands = list(cands)
    for a, b in itertools.combinations(cands, 2):
        if a.resources & b.resources and matcher.overlaps(a.window.start, a.window.end, b.window.start, b.window.end):
            return False
    return True


def brute_force(listings, recipients, transports, helpers, busy):
    """Independent reference: enumerate every role assignment directly (not via matcher.generate)
    and every subset of listings; return (best count, number of optimal assignments)."""
    per_listing = []
    for l in listings:
        opts = [None]
        for w in l.windows:
            if not (w.start > NOW and w.end <= l.deadline):
                continue
            for r in recipients:
                for t in transports:
                    for h in (helpers if l.needs_helper else [None]):
                        if r.listing_id != l.id or t.listing_id != l.id or (h and h.listing_id != l.id):
                            continue
                        if r.user_id == l.owner_id or not t.fit_declared:
                            continue
                        if not (w.id in r.window_ids and w.id in t.window_ids and (h is None or w.id in h.window_ids)):
                            continue
                        if h and h.user_id in (l.owner_id, r.user_id, t.user_id):
                            continue
                        res = {f"user:{l.owner_id}", f"user:{r.user_id}", f"user:{t.user_id}"}
                        if h:
                            res.add(f"user:{h.user_id}")
                        if t.vehicle_id:
                            res.add(f"vehicle:{t.vehicle_id}")
                        if any(b.resource in res and w.start < b.end and b.start < w.end for b in busy):
                            continue
                        opts.append((w, res))
        per_listing.append(opts)
    best, count = 0, 0
    for combo in itertools.product(*per_listing):
        chosen = [c for c in combo if c]
        ok = all(not (a[1] & b[1]) or not (a[0].start < b[0].end and b[0].start < a[0].end)
                 for a, b in itertools.combinations(chosen, 2))
        if not ok:
            continue
        if len(chosen) > best:
            best, count = len(chosen), 1
        elif len(chosen) == best:
            count += 1
    return best, count


def brute_force_count(*args):
    return brute_force(*args)[0]
