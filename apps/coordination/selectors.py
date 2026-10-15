"""Permission-filtered reads for plans and exact locations."""

from datetime import timedelta

from django.db.models import Q

from apps.core import clock
from apps.listings.models import ListingPrivate
from apps.offers.models import HelperOffer, OfferState, RecipientOffer, RecipientPrivate, TransportOffer

from .models import Plan, SharingApproval

ACCESS_AFTER_END = timedelta(days=7)


def plan_for(user, plan_id):
    plan = (Plan.objects.select_related("listing", "listing__zone", "owner", "recipient", "provider", "helper",
                                        "vehicle", "recipient_offer__destination_zone")
            .filter(pk=plan_id).first())
    if plan is None or user.pk not in plan.participant_ids():
        return None
    return plan


def plans_for(user):
    return (Plan.objects.select_related("listing", "owner")
            .filter(Q(owner=user) | Q(recipient=user) | Q(provider=user) | Q(helper=user))
            .order_by("-created_at"))


def active_plan(listing):
    return Plan.objects.filter(listing=listing, state__in=Plan.ACTIVE_STATES).first()


def can_see_exact_locations(user, plan):
    """Crew members see exact details only while the plan is live, after both the owner and the
    recipient approved, and never more than seven days after the collection window ends."""
    if user.pk not in plan.participant_ids() or plan.state not in Plan.SHARING_STATES:
        return False
    if clock.now() >= plan.end + ACCESS_AFTER_END:
        return False
    kinds = set(plan.approvals.values_list("kind", flat=True))
    return {SharingApproval.Kind.PICKUP, SharingApproval.Kind.DESTINATION} <= kinds


def exact_locations(user, plan):
    """{'pickup': str, 'destination': str} for an authorized crew member, otherwise None."""
    if not can_see_exact_locations(user, plan):
        return None
    pickup = ListingPrivate.objects.filter(listing_id=plan.listing_id).values_list("pickup_details", flat=True).first()
    destination = RecipientPrivate.objects.filter(offer_id=plan.recipient_offer_id).values_list(
        "destination_details", flat=True).first()
    return {"pickup": pickup, "destination": destination}


def offers_on(listing):
    active = {"listing": listing, "state": OfferState.ACTIVE}
    return {
        "recipient": list(RecipientOffer.objects.filter(**active).select_related("user", "destination_zone")
                          .prefetch_related("windows")),
        "transport": list(TransportOffer.objects.filter(**active).select_related("user", "vehicle")
                          .prefetch_related("windows")),
        "helper": list(HelperOffer.objects.filter(**active).select_related("user").prefetch_related("windows")),
    }


def my_offers(user, listing=None):
    filters = {"user": user, "state": OfferState.ACTIVE}
    if listing is not None:
        filters["listing"] = listing
    return {
        "recipient": list(RecipientOffer.objects.filter(**filters).select_related("listing")),
        "transport": list(TransportOffer.objects.filter(**filters).select_related("listing", "vehicle")),
        "helper": list(HelperOffer.objects.filter(**filters).select_related("listing")),
    }

