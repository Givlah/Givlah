"""Permission-filtered reads. Templates get private details only through these functions."""

from django.db.models import Prefetch

from apps.core import clock

from .models import Listing, ListingPrivate, Photo


def _with_public_relations(qs):
    from apps.offers.models import HelperOffer, OfferState, RecipientOffer, TransportOffer
    active = lambda model, attr: Prefetch(f"{model.__name__.lower()}s", to_attr=attr,
                                          queryset=model.objects.filter(state=OfferState.ACTIVE).select_related("user"))
    return qs.select_related("owner", "zone").prefetch_related(
        Prefetch("photos", queryset=Photo.objects.order_by("position", "id")), "windows",
        active(RecipientOffer, "active_recipients"), active(TransportOffer, "active_transports"),
        active(HelperOffer, "active_helpers"))


def nearby_listings():
    """Open listings anyone signed in can see. Excludes closed and expired ones."""
    return _with_public_relations(
        Listing.objects.filter(state=Listing.State.NEEDS_HELP, deadline__gt=clock.now()).defer(
            "description"))


def visible_listing(user, listing_id):
    """A listing the user may view, or None. Open listings are visible to everyone signed in;
    others only to their owner and the people involved."""
    qs = _with_public_relations(Listing.objects.filter(pk=listing_id))
    listing = qs.first()
    if listing is None:
        return None
    if listing.is_open or listing.owner_id == user.pk or _involved(user, listing):
        return listing
    return None


def _involved(user, listing):
    """People in a current or completed plan, or who made an offer, keep seeing the listing."""
    from apps.coordination.models import Plan
    from apps.offers.models import HelperOffer, RecipientOffer, TransportOffer
    plans = Plan.objects.filter(listing=listing).exclude(state=Plan.State.ENDED)
    if (plans.filter(recipient=user).exists() or plans.filter(provider=user).exists()
            or plans.filter(helper=user).exists()):
        return True
    return any(m.objects.filter(listing=listing, user=user).exists()
               for m in (RecipientOffer, TransportOffer, HelperOffer))


def my_listings(user):
    return _with_public_relations(Listing.objects.filter(owner=user)).order_by("-created_at")


def private_details_for(user, listing):
    """Exact pickup details, or None when the user may not see them."""
    if listing.owner_id != user.pk:
        return None
    return ListingPrivate.objects.filter(listing=listing).first()


def visible_photo(user, photo_uuid):
    photo = Photo.objects.select_related("listing").filter(uuid=photo_uuid).first()
    if photo is None:
        return None
    return photo if visible_listing(user, photo.listing_id) else None
