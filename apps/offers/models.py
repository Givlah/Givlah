from django.conf import settings
from django.db import models

from apps.listings.models import AvailabilityWindow, Listing, Zone


class Vehicle(models.Model):
    """One declared vehicle. Offers reference it so the same car can't be booked twice under different names."""

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="vehicles")
    label = models.CharField(max_length=60, help_text="For example: grey hatchback, small van")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["owner", "label"], name="unique_vehicle_label")]

    def __str__(self):
        return self.label


class OfferState(models.TextChoices):
    ACTIVE = "active", "Active"
    WITHDRAWN = "withdrawn", "Withdrawn"


class Offer(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="%(class)ss")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="%(class)ss")
    windows = models.ManyToManyField(AvailabilityWindow, related_name="%(class)ss")
    state = models.CharField(max_length=10, choices=OfferState.choices, default=OfferState.ACTIVE)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        ordering = ["created_at", "id"]

    @property
    def is_active(self):
        return self.state == OfferState.ACTIVE


class RecipientOffer(Offer):
    destination_zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="+")

    class Meta(Offer.Meta):
        constraints = [models.UniqueConstraint(fields=["listing", "user"], condition=models.Q(state="active"),
                                               name="one_active_recipient_offer")]


class RecipientPrivate(models.Model):
    offer = models.OneToOneField(RecipientOffer, on_delete=models.CASCADE, related_name="private")
    destination_details = models.CharField(max_length=300)


class TransportOffer(Offer):
    class Mode(models.TextChoices):
        VEHICLE = "vehicle", "With a vehicle"
        CARRY = "carry", "Carry it locally (no vehicle)"

    mode = models.CharField(max_length=10, choices=Mode.choices)
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="offers")
    fit_declared = models.BooleanField(default=False)

    class Meta(Offer.Meta):
        constraints = [
            models.UniqueConstraint(fields=["listing", "user"], condition=models.Q(state="active"),
                                    name="one_active_transport_offer"),
            models.CheckConstraint(condition=models.Q(mode="carry", vehicle__isnull=True) | models.Q(mode="vehicle", vehicle__isnull=False),
                                   name="vehicle_matches_mode"),
        ]


class HelperOffer(Offer):
    class Meta(Offer.Meta):
        constraints = [models.UniqueConstraint(fields=["listing", "user"], condition=models.Q(state="active"),
                                               name="one_active_helper_offer")]
