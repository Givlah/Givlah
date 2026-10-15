"""Coordination commands. The only code that writes offers, plans, reservations, approvals,
confirmations and handover records.

Every write runs in one short transaction. SQLite is configured with IMMEDIATE transactions,
so writers are serialized and each one re-checks state after taking the write lock.
"""

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction

from apps.core import clock
from apps.listings.models import Listing
from apps.offers.models import HelperOffer, OfferState, RecipientOffer, RecipientPrivate, TransportOffer, Vehicle

from . import matcher
from .models import Confirmation, HandoverRecord, Plan, PlanEvent, Reservation, SharingApproval

HOLD_MINUTES = 20
OPEN_FOR_OFFERS = (Listing.State.NEEDS_HELP, Listing.State.AWAITING_CONFIRMATIONS, Listing.State.READY)


class CoordinationError(Exception):
    """A request that can't be applied. ``message`` is safe to show to the user."""

    status = 400

    def __init__(self, message):
        super().__init__(message)
        self.message = message


class NotAllowed(CoordinationError):
    status = 403


class Stale(CoordinationError):
    """The thing changed since the page was loaded; show current state (HTTP 409)."""

    status = 409


# ---------------------------------------------------------------- time-based state


def reconcile():
    """Apply every time-based transition that is due. Called inside each write and before reads,
    so no background worker is needed and an old page can't keep a hold alive."""
    now = clock.now()
    with transaction.atomic():
        for plan in Plan.objects.select_related("listing").filter(
                state=Plan.State.AWAITING_CONFIRMATIONS, hold_expires_at__lte=now):
            _end_plan(plan, "The hold expired before everyone confirmed.", None)
        for plan in Plan.objects.select_related("listing").filter(state=Plan.State.READY, start__lte=now):
            plan.state = Plan.State.AWAITING_HANDOVER
            plan.save(update_fields=["state"])
            _set_listing_state(plan.listing, Listing.State.AWAITING_HANDOVER)
            PlanEvent.objects.create(plan=plan, kind="collection_started")


def _set_listing_state(listing, state):
    listing.state = state
    listing.save(update_fields=["state", "updated_at"])


def _end_plan(plan, reason, actor, listing_state=Listing.State.NEEDS_HELP):
    """End a plan before collection starts: release every hold and revoke all access."""
    plan.state = Plan.State.ENDED
    plan.ended_reason = reason
    plan.save(update_fields=["state", "ended_reason"])
    plan.reservations.update(released=True)
    if listing_state:
        _set_listing_state(plan.listing, listing_state)
    PlanEvent.objects.create(plan=plan, actor=actor, kind="ended", note=reason)


def _to_review(plan, reason, actor):
    """After collection may have started: never relist automatically; ask both parties what happened."""
    plan.state = Plan.State.NEEDS_REVIEW
    plan.save(update_fields=["state"])
    _set_listing_state(plan.listing, Listing.State.NEEDS_REVIEW)
    PlanEvent.objects.create(plan=plan, actor=actor, kind="needs_review", note=reason)


def _active_plan(listing):
    return Plan.objects.filter(listing=listing, state__in=Plan.ACTIVE_STATES).first()


def invalidate_for_listing_change(listing, actor, reason, listing_state=Listing.State.NEEDS_HELP):
    """Called by listing services when the owner edits or closes a listing. Must run inside their transaction."""
    plan = _active_plan(listing)
    if plan is None:
        return
    if plan.state in (Plan.State.AWAITING_CONFIRMATIONS, Plan.State.READY):
        _end_plan(plan, reason, actor, listing_state)
    else:
        raise CoordinationError("A collection has already started for this item. Record what happened first.")


# ---------------------------------------------------------------- offers


def _offer_target(listing_id, user):
    listing = Listing.objects.select_for_update().get(pk=listing_id)
    if listing.state not in OPEN_FOR_OFFERS or listing.deadline <= clock.now():
        raise CoordinationError("This item is no longer open for offers.")
    return listing


def _check_windows(listing, windows):
    if not windows:
        raise CoordinationError("Choose at least one time.")
    now = clock.now()
    for w in windows:
        if w.listing_id != listing.pk or w.start <= now:
            raise Stale("Those times are no longer available. Choose again.")


def offer_to_receive(user, listing_id, windows, destination_zone, destination_details):
    with transaction.atomic():
        reconcile()
        listing = _offer_target(listing_id, user)
        if listing.owner_id == user.pk:
            raise NotAllowed("You can't ask for your own item.")
        _check_windows(listing, windows)
        if RecipientOffer.objects.filter(listing=listing, user=user, state=OfferState.ACTIVE).exists():
            raise CoordinationError("You've already asked for this item.")
        offer = RecipientOffer.objects.create(listing=listing, user=user, destination_zone=destination_zone)
        offer.windows.set(windows)
        RecipientPrivate.objects.create(offer=offer, destination_details=destination_details)
    return offer


def offer_transport(user, listing_id, windows, mode, vehicle=None, new_vehicle_label="", fit_declared=False):
    with transaction.atomic():
        reconcile()
        listing = _offer_target(listing_id, user)
        _check_windows(listing, windows)
        if not fit_declared:
            raise CoordinationError("Confirm the item fits and you can do the whole trip.")
        if TransportOffer.objects.filter(listing=listing, user=user, state=OfferState.ACTIVE).exists():
            raise CoordinationError("You've already offered transport for this item.")
        if mode == TransportOffer.Mode.VEHICLE:
            if vehicle is not None and vehicle.owner_id != user.pk:
                raise NotAllowed("That vehicle isn't yours.")
            if vehicle is None:
                label = new_vehicle_label.strip()
                if not label:
                    raise CoordinationError("Choose or add the vehicle you'll use.")
                vehicle, _ = Vehicle.objects.get_or_create(owner=user, label=label)
        else:
            vehicle = None
        offer = TransportOffer.objects.create(listing=listing, user=user, mode=mode, vehicle=vehicle, fit_declared=True)
        offer.windows.set(windows)
    return offer


def offer_help(user, listing_id, windows):
    with transaction.atomic():
        reconcile()
        listing = _offer_target(listing_id, user)
        if not listing.needs_extra_helper:
            raise CoordinationError("This item doesn't need an extra helper.")
        if listing.owner_id == user.pk:
            raise NotAllowed("The owner is already part of the collection.")
        _check_windows(listing, windows)
        if HelperOffer.objects.filter(listing=listing, user=user, state=OfferState.ACTIVE).exists():
            raise CoordinationError("You've already offered to help carry this item.")
        offer = HelperOffer.objects.create(listing=listing, user=user)
        offer.windows.set(windows)
    return offer


OFFER_MODELS = {"recipient": RecipientOffer, "transport": TransportOffer, "helper": HelperOffer}


def withdraw_offer(user, kind, offer_id):
    model = OFFER_MODELS[kind]
    with transaction.atomic():
        reconcile()
        offer = model.objects.select_related("listing").filter(pk=offer_id).first()
        if offer is None or offer.user_id != user.pk:
            raise NotAllowed("That offer isn't yours.")
        if offer.state != OfferState.ACTIVE:
            return offer
        offer.state = OfferState.WITHDRAWN
        offer.revision += 1
        offer.save(update_fields=["state", "revision"])
        field = {"recipient": "recipient_offer", "transport": "transport_offer", "helper": "helper_offer"}[kind]
        plan = Plan.objects.select_related("listing").filter(**{field: offer}, state__in=Plan.ACTIVE_STATES).first()
        if plan:
            name = user.display_name or user.username
            if plan.state in (Plan.State.AWAITING_CONFIRMATIONS, Plan.State.READY):
                _end_plan(plan, f"{name} withdrew their offer.", user)
            elif plan.state == Plan.State.AWAITING_HANDOVER:
                _to_review(plan, f"{name} withdrew after the collection time started.", user)
    return offer


# ---------------------------------------------------------------- suggestions


@dataclass
class Suggestion:
    status: str
    listing: Listing
    batch: list            # listings considered together
    result: matcher.Result
    selected: object        # Candidate for this listing in the best overall set, or None
    alternatives: list      # other feasible candidates for this listing
    reasons: list
    conflicts: dict         # candidate key -> [listing titles it would stop from being planned]


def _window_inputs(listing):
    return tuple(matcher.WindowIn(w.id, w.start, w.end) for w in listing.windows.all())


def _listing_input(listing):
    return matcher.ListingIn(listing.id, listing.owner_id, listing.needs_extra_helper, listing.deadline,
                             listing.created_at, _window_inputs(listing))


def _offer_inputs(listing_ids):
    def windows(o):
        return frozenset(w.id for w in o.windows.all())
    active = {"listing_id__in": listing_ids, "state": OfferState.ACTIVE}
    recipients = [matcher.OfferIn(o.id, o.listing_id, o.user_id, windows(o))
                  for o in RecipientOffer.objects.filter(**active).prefetch_related("windows")]
    transports = [matcher.OfferIn(o.id, o.listing_id, o.user_id, windows(o), o.vehicle_id, o.fit_declared)
                  for o in TransportOffer.objects.filter(**active).prefetch_related("windows")]
    helpers = [matcher.OfferIn(o.id, o.listing_id, o.user_id, windows(o))
               for o in HelperOffer.objects.filter(**active).prefetch_related("windows")]
    return recipients, transports, helpers


def _busy(exclude_listing_ids=()):
    return [matcher.Busy(r.resource, r.start, r.end)
            for r in Reservation.objects.filter(released=False).exclude(plan__listing_id__in=exclude_listing_ids)]


def _resources_of(listing, offers_by_listing):
    keys = {f"user:{listing.owner_id}"}
    for o in offers_by_listing.get(listing.id, []):
        keys.add(f"user:{o.user_id}")
        if o.vehicle_id:
            keys.add(f"vehicle:{o.vehicle_id}")
    return keys


def batch_for(listing):
    """The open listings that compete with this one for the same people or vehicles.

    Listings outside this connected group can't affect each other's plans, so solving the group
    exactly gives the same answer as solving everything together."""
    now = clock.now()
    open_listings = list(Listing.objects.filter(state=Listing.State.NEEDS_HELP, deadline__gt=now)
                         .prefetch_related("windows"))
    if listing.id not in {l.id for l in open_listings}:
        return [listing]
    recipients, transports, helpers = _offer_inputs([l.id for l in open_listings])
    by_listing = {}
    for o in recipients + transports + helpers:
        by_listing.setdefault(o.listing_id, []).append(o)
    resources = {l.id: _resources_of(l, by_listing) for l in open_listings}
    group, frontier, keys = {listing.id}, [listing.id], set(resources[listing.id])
    while frontier:
        frontier = []
        for l in open_listings:
            if l.id not in group and resources[l.id] & keys:
                group.add(l.id)
                frontier.append(l.id)
                keys |= resources[l.id]
    return [l for l in open_listings if l.id in group]


def suggest(listing):
    """Suggestions reserve nothing; the owner must choose one to activate it."""
    reconcile()
    batch = batch_for(listing)
    ids = [l.id for l in batch]
    recipients, transports, helpers = _offer_inputs(ids)
    result = matcher.solve([_listing_input(l) for l in batch], recipients, transports, helpers,
                           _busy(), clock.now())
    titles = {l.id: l.title for l in batch}
    cands = result.candidates.get(listing.id, [])
    selected = result.selected.get(listing.id)
    alternatives = [c for c in cands if selected is None or c.key != selected.key]
    conflicts = {}
    for cand in cands:
        blocked = [titles[lid] for lid, other in result.selected.items()
                   if lid != listing.id and cand.resources & other.resources
                   and matcher.overlaps(cand.window.start, cand.window.end, other.window.start, other.window.end)]
        if blocked:
            conflicts[cand.key] = blocked
    return Suggestion(result.status, listing, batch, result, selected, alternatives,
                      result.reasons.get(listing.id, []), conflicts)


# ---------------------------------------------------------------- activation


def activate(user, listing_id, window_id, recipient_offer_id, transport_offer_id, helper_offer_id, listing_revision):
    """Owner turns a suggestion into a held plan. All-or-nothing: on any conflict nothing is reserved."""
    with transaction.atomic():
        reconcile()
        now = clock.now()
        listing = Listing.objects.select_for_update().prefetch_related("windows").get(pk=listing_id)
        if listing.owner_id != user.pk:
            raise NotAllowed("Only the owner can choose a crew.")
        existing = _active_plan(listing)
        if (existing and existing.window_id == window_id and existing.recipient_offer_id == recipient_offer_id
                and existing.transport_offer_id == transport_offer_id and existing.helper_offer_id == helper_offer_id):
            return existing  # repeated submission of the same choice: return the committed result
        if listing.revision != listing_revision:
            raise Stale("The listing changed since you looked. Here is the current suggestion.")
        if listing.state != Listing.State.NEEDS_HELP or listing.deadline <= now:
            raise Stale("This item isn't waiting for a crew any more.")
        if _active_plan(listing):
            raise Stale("A crew is already being confirmed for this item.")

        recipients, transports, helpers = _offer_inputs([listing.id])
        pick = lambda offers, oid: next((o for o in offers if o.id == oid), None)
        r, t = pick(recipients, recipient_offer_id), pick(transports, transport_offer_id)
        h = pick(helpers, helper_offer_id) if helper_offer_id else None
        if r is None or t is None or (helper_offer_id and h is None):
            raise Stale("Someone in that crew has withdrawn. Here is the current suggestion.")
        cands, _ = matcher.generate(_listing_input(listing), [r], [t], [h] if h else [], _busy(), now)
        cand = next((c for c in cands if c.window.id == window_id and (c.helper.id if c.helper else None) == helper_offer_id), None)
        if cand is None:
            raise Stale("That crew can no longer do that time. Here is the current suggestion.")

        recipient_offer = RecipientOffer.objects.get(pk=r.id)
        transport_offer = TransportOffer.objects.get(pk=t.id)
        helper_offer = HelperOffer.objects.get(pk=h.id) if h else None
        plan = Plan.objects.create(
            listing=listing, window_id=cand.window.id, start=cand.window.start, end=cand.window.end,
            owner_id=listing.owner_id, recipient_offer=recipient_offer, transport_offer=transport_offer,
            helper_offer=helper_offer, recipient_id=r.user_id, provider_id=t.user_id,
            helper_id=h.user_id if h else None, vehicle_id=t.vehicle_id, listing_revision=listing.revision,
            hold_expires_at=min(now + timedelta(minutes=HOLD_MINUTES), cand.window.start))
        Reservation.objects.bulk_create(
            Reservation(plan=plan, resource=key, start=cand.window.start, end=cand.window.end)
            for key in sorted(cand.resources))
        _set_listing_state(listing, Listing.State.AWAITING_CONFIRMATIONS)
        PlanEvent.objects.create(plan=plan, actor=user, kind="activated")
    return plan


# ---------------------------------------------------------------- crew actions


def _load_plan(plan_id, user):
    plan = Plan.objects.select_related("listing").filter(pk=plan_id).first()
    if plan is None or user.pk not in plan.participant_ids():
        raise NotAllowed("You're not part of this collection.")
    return plan


def _require_pending(plan):
    if plan.state != Plan.State.AWAITING_CONFIRMATIONS:
        raise Stale("This plan has changed. Here is its current state.")


def approve_sharing(user, plan_id):
    """Owner approves showing pickup details; recipient approves destination details."""
    with transaction.atomic():
        reconcile()
        plan = _load_plan(plan_id, user)
        _require_pending(plan)
        kinds = []
        if user.pk == plan.owner_id:
            kinds.append(SharingApproval.Kind.PICKUP)
        if user.pk == plan.recipient_id:
            kinds.append(SharingApproval.Kind.DESTINATION)
        if not kinds:
            raise NotAllowed("Only the owner and recipient share exact locations.")
        for kind in kinds:
            SharingApproval.objects.get_or_create(plan=plan, kind=kind, defaults={"user": user})
        PlanEvent.objects.create(plan=plan, actor=user, kind="approved_sharing")
    return plan


def confirm(user, plan_id):
    with transaction.atomic():
        reconcile()
        plan = _load_plan(plan_id, user)
        _require_pending(plan)
        if plan.approvals.count() < 2:
            raise CoordinationError("Confirmation opens once the owner and recipient both approve sharing their locations.")
        _, created = Confirmation.objects.get_or_create(plan=plan, user=user)
        if created:
            PlanEvent.objects.create(plan=plan, actor=user, kind="confirmed")
        confirmed = set(plan.confirmations.values_list("user_id", flat=True))
        if set(plan.participant_ids()) <= confirmed:
            plan.state = Plan.State.READY
            plan.reached_ready = True
            plan.save(update_fields=["state", "reached_ready"])
            _set_listing_state(plan.listing, Listing.State.READY)
            PlanEvent.objects.create(plan=plan, kind="ready")
    return plan


def leave(user, plan_id, reason="declined"):
    """Decline, revoke sharing or drop out. Before the start this ends the plan for everyone;
    afterwards it sends the item to review instead of relisting it."""
    with transaction.atomic():
        reconcile()
        plan = _load_plan(plan_id, user)
        name = user.display_name or user.username
        text = {"declined": f"{name} declined.", "revoked": f"{name} stopped sharing their location."}[reason]
        if plan.state in (Plan.State.AWAITING_CONFIRMATIONS, Plan.State.READY):
            _end_plan(plan, text, user)
        elif plan.state == Plan.State.AWAITING_HANDOVER:
            _to_review(plan, text, user)
        else:
            raise Stale("This plan has already finished.")
    return plan


# ---------------------------------------------------------------- outcome


def record_handover(user, plan_id, outcome):
    with transaction.atomic():
        reconcile()
        plan = _load_plan(plan_id, user)
        if user.pk == plan.owner_id:
            party = HandoverRecord.Party.OWNER
        elif user.pk == plan.recipient_id:
            party = HandoverRecord.Party.RECIPIENT
        else:
            raise NotAllowed("Only the owner and the recipient record the handover.")
        if not plan.reached_ready:
            raise CoordinationError("This plan was never confirmed by everyone, so it can't be completed.")
        if plan.state not in (Plan.State.AWAITING_HANDOVER, Plan.State.NEEDS_REVIEW, Plan.State.HANDOVER_RECORDED):
            raise Stale("The handover can be recorded once the collection time starts.")
        if outcome not in HandoverRecord.Outcome.values:
            raise CoordinationError("Choose what happened.")
        record, created = HandoverRecord.objects.get_or_create(plan=plan, party=party,
                                                               defaults={"user": user, "outcome": outcome})
        if not created and record.outcome != outcome:
            record.outcome = outcome
            record.save(update_fields=["outcome"])
        elif not created:
            return plan  # identical repeat
        PlanEvent.objects.create(plan=plan, actor=user, kind=f"recorded_{outcome}")
        _settle_outcome(plan, user)
    return plan


def retract_handover(user, plan_id):
    with transaction.atomic():
        reconcile()
        plan = _load_plan(plan_id, user)
        deleted, _ = HandoverRecord.objects.filter(plan=plan, user=user).delete()
        if deleted:
            PlanEvent.objects.create(plan=plan, actor=user, kind="retracted")
            if plan.state == Plan.State.HANDOVER_RECORDED:
                _to_review(plan, "A handover record was withdrawn.", user)
    return plan


def _settle_outcome(plan, actor):
    outcomes = dict(plan.handovers.values_list("party", "outcome"))
    owner, recipient = outcomes.get("owner"), outcomes.get("recipient")
    if owner is None or recipient is None:
        return
    if owner == recipient == HandoverRecord.Outcome.HANDED_OVER:
        plan.state = Plan.State.HANDOVER_RECORDED
        plan.save(update_fields=["state"])
        _set_listing_state(plan.listing, Listing.State.HANDOVER_RECORDED)
        PlanEvent.objects.create(plan=plan, kind="handover_recorded")
    elif owner == recipient == HandoverRecord.Outcome.STAYED:
        # Both agree the item is still with the owner: it can look for a new crew.
        # Occupied intervals stay recorded; old offers are re-checked, never recommitted.
        plan.state = Plan.State.ENDED
        plan.ended_reason = "Owner and recipient both recorded that the item stayed with the owner."
        plan.save(update_fields=["state", "ended_reason"])
        _set_listing_state(plan.listing, Listing.State.NEEDS_HELP)
        PlanEvent.objects.create(plan=plan, kind="reopened", note=plan.ended_reason)
    elif plan.state != Plan.State.NEEDS_REVIEW:
        _to_review(plan, "The owner and recipient recorded different outcomes.", actor)
