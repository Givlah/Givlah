from django.conf import settings
from django.db import models

from apps.listings.models import AvailabilityWindow, Listing
from apps.offers.models import HelperOffer, RecipientOffer, TransportOffer, Vehicle


class Plan(models.Model):
    """One proposed crew and time for one listing. A plan is never edited: any material change ends it."""

    class State(models.TextChoices):
        AWAITING_CONFIRMATIONS = "awaiting_confirmations", "Awaiting confirmations"
        READY = "ready", "Ready"
        AWAITING_HANDOVER = "awaiting_handover", "Awaiting handover record"
        HANDOVER_RECORDED = "handover_recorded", "Handover recorded"
        NEEDS_REVIEW = "needs_review", "Needs review"
        ENDED = "ended", "Ended"

    ACTIVE_STATES = (State.AWAITING_CONFIRMATIONS, State.READY, State.AWAITING_HANDOVER, State.NEEDS_REVIEW)
    # States in which the crew may see approved exact details.
    SHARING_STATES = (State.AWAITING_CONFIRMATIONS, State.READY, State.AWAITING_HANDOVER)

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="plans")
    state = models.CharField(max_length=30, choices=State.choices, default=State.AWAITING_CONFIRMATIONS)
    # start/end are copied, so a plan keeps its interval even if the owner later removes the window.
    window = models.ForeignKey(AvailabilityWindow, null=True, on_delete=models.SET_NULL, related_name="+")
    start = models.DateTimeField()
    end = models.DateTimeField()
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    recipient_offer = models.ForeignKey(RecipientOffer, on_delete=models.PROTECT, related_name="plans")
    transport_offer = models.ForeignKey(TransportOffer, on_delete=models.PROTECT, related_name="plans")
    helper_offer = models.ForeignKey(HelperOffer, null=True, blank=True, on_delete=models.PROTECT, related_name="plans")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    provider = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    helper = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    vehicle = models.ForeignKey(Vehicle, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    listing_revision = models.PositiveIntegerField()
    hold_expires_at = models.DateTimeField()
    reached_ready = models.BooleanField(default=False)
    ended_reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["listing"], condition=models.Q(state__in=[
                "awaiting_confirmations", "ready", "awaiting_handover", "needs_review"]),
                name="one_active_plan_per_listing"),
            models.CheckConstraint(condition=models.Q(start__lt=models.F("end")), name="plan_start_before_end"),
        ]

    def participant_ids(self):
        """Distinct people in the crew; someone filling two roles counts once."""
        ids = [self.owner_id, self.recipient_id, self.provider_id, self.helper_id]
        return list(dict.fromkeys(i for i in ids if i))

    def roles_of(self, user_id):
        roles = []
        if user_id == self.owner_id:
            roles.append("owner")
        if user_id == self.recipient_id:
            roles.append("recipient")
        if user_id == self.provider_id:
            roles.append("transport")
        if user_id == self.helper_id:
            roles.append("helper")
        return roles

    @property
    def is_active(self):
        return self.state in self.ACTIVE_STATES


class Reservation(models.Model):
    """A person or vehicle occupied for [start, end). Released reservations no longer block anything."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="reservations")
    resource = models.CharField(max_length=40)  # "user:<id>" or "vehicle:<id>"
    start = models.DateTimeField()
    end = models.DateTimeField()
    released = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["resource", "released"])]
        constraints = [models.UniqueConstraint(fields=["plan", "resource"], name="one_reservation_per_resource")]


class SharingApproval(models.Model):
    """The owner (pickup) or recipient (destination) agrees to show exact details to this plan's crew."""

    class Kind(models.TextChoices):
        PICKUP = "pickup", "Pickup details"
        DESTINATION = "destination", "Destination details"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="approvals")
    kind = models.CharField(max_length=12, choices=Kind.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "kind"], name="one_approval_per_kind")]


class Confirmation(models.Model):
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="confirmations")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "user"], name="one_confirmation_per_person")]


class HandoverRecord(models.Model):
    class Party(models.TextChoices):
        OWNER = "owner", "Owner"
        RECIPIENT = "recipient", "Recipient"

    class Outcome(models.TextChoices):
        HANDED_OVER = "handed_over", "The item was handed over"
        STAYED = "stayed", "The item stayed with the owner"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="handovers")
    party = models.CharField(max_length=10, choices=Party.choices)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    outcome = models.CharField(max_length=12, choices=Outcome.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["plan", "party"], name="one_record_per_party")]


class PlanEvent(models.Model):
    """Plan history. Never contains addresses or coordinates."""

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="events")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    kind = models.CharField(max_length=40)
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    LABELS = {
        "activated": "Crew invited", "approved_sharing": "Location shared with crew", "confirmed": "Confirmed",
        "ready": "Everyone confirmed", "ended": "Plan ended", "collection_started": "Collection time started",
        "needs_review": "Needs review", "recorded_handed_over": "Recorded: handed over",
        "recorded_stayed": "Recorded: stayed with owner", "retracted": "Record withdrawn",
        "handover_recorded": "Handover recorded by both", "reopened": "Item open for a new crew",
    }

    class Meta:
        ordering = ["created_at", "id"]

    @property
    def label(self):
        return self.LABELS.get(self.kind, self.kind)
