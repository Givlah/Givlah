"""Listing commands. Views call these; nothing else writes listing state."""

from dataclasses import dataclass

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from apps.core import clock
from apps.core.models import ActionToken

from .models import AvailabilityWindow, Listing, ListingPrivate, Photo


class StaleRevision(Exception):
    """The listing changed since the form was loaded."""


class NotAllowed(Exception):
    pass


class ListingClosed(Exception):
    pass


@dataclass
class Duplicate:
    result_url: str


def _private_fields(data):
    gps = data.get("latitude") is not None
    return {
        "pickup_details": data["pickup_details"],
        "latitude": data.get("latitude"),
        "longitude": data.get("longitude"),
        "source": ListingPrivate.Source.GPS if gps else ListingPrivate.Source.MANUAL,
    }


def _public_fields(data):
    return {k: data[k] for k in ("title", "description", "condition", "width_cm", "depth_cm", "height_cm",
                                 "handling_notes", "needs_extra_helper", "zone", "deadline")}


def _save_photos(listing, photos):
    for position, (jpeg, width, height) in enumerate(photos):
        photo = Photo(listing=listing, position=position, width=width, height=height)
        photo.image.save(f"{photo.uuid.hex}.jpg", ContentFile(jpeg), save=False)
        photo.save()


def publish_listing(user, data):
    """Create a published listing. Returns the Listing, or Duplicate if this form was already submitted."""
    existing = ActionToken.objects.filter(token=data["action_token"], user=user).first()
    if existing:
        return Duplicate(existing.result_url)
    try:
        with transaction.atomic():
            listing = Listing.objects.create(owner=user, ownership_declared=True,
                                             is_synthetic=user.is_synthetic, **_public_fields(data))
            ListingPrivate.objects.create(listing=listing, **_private_fields(data))
            AvailabilityWindow.objects.bulk_create(
                AvailabilityWindow(listing=listing, start=s, end=e) for s, e in data["windows"])
            _save_photos(listing, data["photos"])
            ActionToken.objects.create(token=data["action_token"], user=user, result_url=listing.get_absolute_url())
    except IntegrityError:
        existing = ActionToken.objects.filter(token=data["action_token"], user=user).first()
        if existing:
            return Duplicate(existing.result_url)
        raise
    return listing


def update_listing(user, listing_id, revision, data):
    """Edit an open listing. A material edit bumps the revision so stale forms and plans are rejected."""
    with transaction.atomic():
        listing = Listing.objects.get(pk=listing_id)
        if listing.owner_id != user.pk:
            raise NotAllowed
        if not listing.is_open:
            raise ListingClosed
        if listing.revision != revision:
            raise StaleRevision
        for field, value in _public_fields(data).items():
            setattr(listing, field, value)
        listing.revision += 1
        listing.save()
        ListingPrivate.objects.update_or_create(listing=listing, defaults=_private_fields(data))
        listing.windows.all().delete()
        AvailabilityWindow.objects.bulk_create(
            AvailabilityWindow(listing=listing, start=s, end=e) for s, e in data["windows"])
        if data["photos"]:
            old = list(listing.photos.all())
            _save_photos(listing, data["photos"])
            for photo in old:
                photo.image.delete(save=False)
                photo.delete()
    return listing


def close_listing(user, listing_id, revision):
    with transaction.atomic():
        listing = Listing.objects.get(pk=listing_id)
        if listing.owner_id != user.pk:
            raise NotAllowed
        if listing.state != Listing.State.NEEDS_HELP:
            raise ListingClosed
        if listing.revision != revision:
            raise StaleRevision
        listing.state = Listing.State.CANCELLED
        listing.closed_at = clock.now()
        listing.revision += 1
        listing.save()
    return listing
