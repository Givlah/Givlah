from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.listings import selectors as listing_selectors
from apps.offers.forms import HelperOfferForm, RecipientOfferForm, TransportOfferForm
from apps.offers.models import Vehicle

from . import selectors, services
from .models import HandoverRecord, Plan

OFFER_FORMS = {
    "recipient": (RecipientOfferForm, "I'd like this", "Ask for this item"),
    "transport": (TransportOfferForm, "I can transport it", "Offer transport"),
    "helper": (HelperOfferForm, "I can help carry", "Offer to help carry"),
}


def _listing_or_404(user, pk):
    listing = listing_selectors.visible_listing(user, pk)
    if listing is None:
        raise Http404
    return listing


@login_required
def make_offer(request, pk, kind):
    if kind not in OFFER_FORMS:
        raise Http404
    listing = _listing_or_404(request.user, pk)
    form_class, heading, button = OFFER_FORMS[kind]
    form = form_class(request.POST or None, listing=listing, user=request.user)
    status = 200
    if request.method == "POST":
        if form.is_valid():
            data = form.cleaned_data
            windows = list(data["windows"])
            try:
                if kind == "recipient":
                    services.offer_to_receive(request.user, listing.pk, windows, data["destination_zone"],
                                              data["destination_details"])
                elif kind == "transport":
                    services.offer_transport(request.user, listing.pk, windows, data["mode"], data.get("vehicle"),
                                             data.get("new_vehicle", ""), data["fit_declared"])
                else:
                    services.offer_help(request.user, listing.pk, windows)
            except services.CoordinationError as exc:
                messages.error(request, exc.message)
                status = exc.status
            else:
                messages.success(request, "Thanks! Your offer is saved. You'll see an invitation here if a crew is proposed.")
                return redirect(listing)
        else:
            status = 400
    return render(request, "offers/form.html", {"listing": listing, "form": form, "heading": heading,
                                                "button": button, "kind": kind}, status=status)


@login_required
@require_POST
def withdraw_offer(request, kind, offer_id):
    if kind not in services.OFFER_MODELS:
        raise Http404
    try:
        offer = services.withdraw_offer(request.user, kind, offer_id)
    except services.NotAllowed:
        raise Http404
    messages.success(request, "Your offer is withdrawn.")
    return redirect(offer.listing)


@login_required
def crew(request, pk):
    """Owner's view of the best complete crews, and activation."""
    listing = _listing_or_404(request.user, pk)
    if listing.owner_id != request.user.pk:
        raise Http404
    status = 200
    if request.method == "POST":
        try:
            def as_int(name):
                value = request.POST.get(name) or ""
                return int(value) if value else None
            plan = services.activate(request.user, listing.pk, as_int("window"), as_int("recipient"),
                                     as_int("transport"), as_int("helper"), as_int("revision"))
        except services.CoordinationError as exc:
            messages.error(request, exc.message + (" Nothing was reserved." if exc.status == 409 else ""))
            status = exc.status
        except (TypeError, ValueError):
            messages.error(request, "That request was incomplete. Nothing was reserved.")
            status = 400
        else:
            messages.success(request, "Crew invited. Everyone now confirms for themselves.")
            return redirect("coordination:plan", plan_id=plan.pk)
        listing.refresh_from_db()
    plan = selectors.active_plan(listing)
    suggestion = services.suggest(listing) if plan is None and listing.is_open else None
    context = {"listing": listing, "suggestion": suggestion, "plan": plan, "best": None, "alternatives": []}
    if suggestion:
        people = {u.pk: u for u in User.objects.filter(pk__in=_people(suggestion))}
        vehicles = {v.pk: v for v in Vehicle.objects.filter(pk__in=_vehicles(suggestion))}
        show = lambda c: _candidate_view(c, people, vehicles, suggestion.conflicts.get(c.key, []))
        context["best"] = show(suggestion.selected) if suggestion.selected else None
        context["alternatives"] = [show(c) for c in suggestion.alternatives]
        titles = {l.id: l.title for l in suggestion.batch}
        context["batch_others"] = [titles[lid] for lid in suggestion.result.selected if lid != listing.id]
    return render(request, "coordination/crew.html", context, status=status)


def _all_candidates(suggestion):
    return ([suggestion.selected] if suggestion.selected else []) + suggestion.alternatives


def _people(suggestion):
    ids = set()
    for c in _all_candidates(suggestion):
        ids |= {c.recipient.user_id, c.transport.user_id} | ({c.helper.user_id} if c.helper else set())
    return ids


def _vehicles(suggestion):
    return {c.transport.vehicle_id for c in _all_candidates(suggestion) if c.transport.vehicle_id}


def _candidate_view(c, people, vehicles, conflicts):
    return {
        "window": c.window, "recipient_id": c.recipient.id, "transport_id": c.transport.id,
        "helper_id": c.helper.id if c.helper else None,
        "recipient_user": people[c.recipient.user_id], "transport_user": people[c.transport.user_id],
        "helper_user": people[c.helper.user_id] if c.helper else None,
        "vehicle": vehicles.get(c.transport.vehicle_id), "conflicts": conflicts,
    }


def _plan_or_404(user, plan_id):
    services.reconcile()
    plan = selectors.plan_for(user, plan_id)
    if plan is None:
        raise Http404
    return plan


@login_required
def plan_detail(request, plan_id, status=200):
    plan = _plan_or_404(request.user, plan_id)
    me = request.user.pk
    approvals = {a.kind: a for a in plan.approvals.all()}
    confirmed = set(plan.confirmations.values_list("user_id", flat=True))
    records = {r.party: r for r in plan.handovers.all()}
    crew = []
    for role, person in (("Giving the item", plan.owner), ("Receiving it", plan.recipient),
                         ("Transport", plan.provider), ("Helping carry", plan.helper)):
        if person:
            crew.append({"role": role, "person": person, "confirmed": person.pk in confirmed, "me": person.pk == me})
    my_party = "owner" if me == plan.owner_id else "recipient" if me == plan.recipient_id else None
    return render(request, "coordination/plan.html", {
        "plan": plan,
        "crew": crew,
        "approvals": approvals,
        "both_approved": len(approvals) >= 2,
        "i_confirmed": me in confirmed,
        "can_approve": plan.state == Plan.State.AWAITING_CONFIRMATIONS and (
            (me == plan.owner_id and "pickup" not in approvals) or (me == plan.recipient_id and "destination" not in approvals)),
        "i_share": me in (plan.owner_id, plan.recipient_id),
        "locations": selectors.exact_locations(request.user, plan),
        "my_party": my_party,
        "my_record": records.get(my_party) if my_party else None,
        "records": records,
        "outcomes": HandoverRecord.Outcome.choices,
        "events": plan.events.select_related("actor"),
        "my_roles": plan.roles_of(me),
    }, status=status)


ACTIONS = {
    "approve": (lambda u, p, r: services.approve_sharing(u, p), "Thanks. Your exact location will be shown to this crew."),
    "confirm": (lambda u, p, r: services.confirm(u, p), "Confirmed."),
    "decline": (lambda u, p, r: services.leave(u, p, "declined"), "You've left this plan. Everyone has been released."),
    "revoke": (lambda u, p, r: services.leave(u, p, "revoked"), "Location sharing stopped. This plan has ended."),
    "handover": (lambda u, p, r: services.record_handover(u, p, r.POST.get("outcome", "")), "Recorded."),
    "retract": (lambda u, p, r: services.retract_handover(u, p), "Your record was withdrawn."),
}


@login_required
@require_POST
def plan_action(request, plan_id, action):
    if action not in ACTIONS:
        raise Http404
    run, success = ACTIONS[action]
    try:
        run(request.user, plan_id, request)
    except services.NotAllowed:
        raise Http404
    except services.CoordinationError as exc:
        messages.error(request, exc.message + " Nothing was changed." if exc.status == 409 else exc.message)
        return plan_detail(request, plan_id, status=exc.status)
    messages.success(request, success)
    return redirect(reverse("coordination:plan", args=[plan_id]))
