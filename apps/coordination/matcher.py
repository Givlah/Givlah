"""Turn stored offers into complete collection arrangements across listings.

Pure functions over plain data: no database access, so results can be checked against
an independent brute-force enumeration. Intervals are half-open: [start, end).
"""

import time
from dataclasses import dataclass, field

MAX_LISTINGS = 8
MAX_CANDIDATES = 24
TIME_BUDGET_SECONDS = 5.0


@dataclass(frozen=True)
class WindowIn:
    id: int
    start: object
    end: object


@dataclass(frozen=True)
class ListingIn:
    id: int
    owner_id: int
    needs_helper: bool
    deadline: object
    created_at: object
    windows: tuple  # of WindowIn


@dataclass(frozen=True)
class OfferIn:
    id: int
    listing_id: int
    user_id: int
    window_ids: frozenset
    vehicle_id: int | None = None  # transport offers only
    fit_declared: bool = True       # transport offers only


@dataclass(frozen=True)
class Busy:
    resource: str
    start: object
    end: object


@dataclass(frozen=True)
class Candidate:
    listing_id: int
    window: WindowIn
    recipient: OfferIn
    transport: OfferIn
    helper: OfferIn | None
    resources: frozenset  # "user:<id>" and "vehicle:<id>"

    @property
    def key(self):
        return (self.window.start, self.window.id, self.recipient.id, self.transport.id,
                self.helper.id if self.helper else 0)


@dataclass
class Result:
    status: str  # "ok", "over_limit" or "incomplete"
    selected: dict = field(default_factory=dict)     # listing_id -> Candidate
    candidates: dict = field(default_factory=dict)   # listing_id -> [Candidate]
    reasons: dict = field(default_factory=dict)      # listing_id -> [str] for listings with no candidate


def overlaps(a_start, a_end, b_start, b_end):
    return a_start < b_end and b_start < a_end


def _resources(listing, recipient, transport, helper):
    people = {listing.owner_id, recipient.user_id, transport.user_id}
    if helper:
        people.add(helper.user_id)
    keys = {f"user:{p}" for p in people}
    if transport.vehicle_id:
        keys.add(f"vehicle:{transport.vehicle_id}")
    return frozenset(keys)


def _blocked(resources, window, busy):
    return [b for b in busy if b.resource in resources and overlaps(window.start, window.end, b.start, b.end)]


def generate(listing, recipients, transports, helpers, busy, now):
    """All eligible complete candidates for one listing, plus reasons when there are none."""
    windows = [w for w in listing.windows if w.start > now and w.end <= listing.deadline]
    reasons = []
    if not windows:
        reasons.append("No upcoming collection time is left before the deadline.")
    recipients = [r for r in recipients if r.user_id != listing.owner_id]
    if not recipients:
        reasons.append("No one has asked for it yet.")
    fit = [t for t in transports if t.fit_declared]
    if not transports:
        reasons.append("No one has offered transport yet.")
    elif not fit:
        reasons.append("Transport offered, but no one has confirmed the item fits.")
    if listing.needs_helper and not helpers:
        reasons.append("Needs a second person to help carry.")
    if reasons:
        return [], reasons

    candidates = []
    shared_time = helper_clash = busy_clash = False
    for w in windows:
        for r in recipients:
            if w.id not in r.window_ids:
                continue
            for t in fit:
                if w.id not in t.window_ids:
                    continue
                helper_options = [None]
                if listing.needs_helper:
                    in_time = [h for h in helpers if w.id in h.window_ids]
                    helper_options = [h for h in in_time if h.user_id not in {listing.owner_id, r.user_id, t.user_id}]
                    helper_clash = helper_clash or (bool(in_time) and not helper_options)
                if helper_options:
                    shared_time = True
                for h in helper_options:
                    res = _resources(listing, r, t, h)
                    if _blocked(res, w, busy):
                        busy_clash = True
                        continue
                    candidates.append(Candidate(listing.id, w, r, t, h, res))
    if not candidates:
        if busy_clash:
            reasons.append("The people or vehicle offered are already committed to another collection at those times.")
        elif helper_clash:
            reasons.append("The extra helper must be someone other than the owner, recipient and transport provider.")
        elif not shared_time:
            reasons.append("The offers don't share a common collection time.")
    candidates.sort(key=lambda c: c.key)
    return candidates, reasons


def _priority(listing):
    return (listing.deadline, listing.created_at, listing.id)


def solve(listings, recipients, transports, helpers, busy, now, time_budget=TIME_BUDGET_SECONDS, clock=time.monotonic):
    """Choose at most one candidate per listing, maximizing complete collections without any
    person or vehicle in two overlapping trips. Equal counts prefer earlier deadlines, then
    older listings, then stable IDs (earlier windows and offers first)."""
    if len(listings) > MAX_LISTINGS:
        return Result("over_limit")

    by_listing = lambda offers, lid: [o for o in offers if o.listing_id == lid]
    result = Result("ok")
    order = sorted(listings, key=_priority)
    for listing in order:
        cands, reasons = generate(listing, by_listing(recipients, listing.id), by_listing(transports, listing.id),
                                  by_listing(helpers, listing.id), busy, now)
        result.candidates[listing.id] = cands
        if not cands:
            result.reasons[listing.id] = reasons
    if sum(len(c) for c in result.candidates.values()) > MAX_CANDIDATES:
        return Result("over_limit", candidates=result.candidates, reasons=result.reasons)

    plannable = [l for l in order if result.candidates[l.id]]
    best = {"count": -1, "choice": {}}
    deadline = clock() + time_budget
    timed_out = False

    def compatible(cand, chosen):
        return all(not (cand.resources & other.resources) or
                   not overlaps(cand.window.start, cand.window.end, other.window.start, other.window.end)
                   for other in chosen.values())

    def search(i, chosen):
        nonlocal timed_out
        if clock() > deadline:
            timed_out = True
            return
        if len(chosen) + (len(plannable) - i) <= best["count"]:
            return
        if i == len(plannable):
            best["count"], best["choice"] = len(chosen), dict(chosen)
            return
        listing = plannable[i]
        for cand in result.candidates[listing.id]:
            if compatible(cand, chosen):
                chosen[listing.id] = cand
                search(i + 1, chosen)
                del chosen[listing.id]
                if timed_out:
                    return
        search(i + 1, chosen)

    search(0, {})
    result.selected = best["choice"]
    if timed_out:
        result.status = "incomplete"
    return result
