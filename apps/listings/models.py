import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse

from apps.core import clock


class Locality(models.Model):
    name = models.CharField(max_length=80, unique=True)
    is_synthetic = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "localities"

    def __str__(self):
        return self.name


class Zone(models.Model):
    """A public neighbourhood area. Its representative point is public; listing locations are not."""

    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, related_name="zones")
    name = models.CharField(max_length=80)
    latitude = models.DecimalField(max_digits=8, decimal_places=5)
    longitude = models.DecimalField(max_digits=8, decimal_places=5)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["locality", "name"], name="unique_zone_name")]

    def __str__(self):
        return self.name


class Listing(models.Model):
    class State(models.TextChoices):
        NEEDS_HELP = "needs_help", "Needs help"
        AWAITING_CONFIRMATIONS = "awaiting_confirmations", "Awaiting confirmations"
        READY = "ready", "Ready"
        AWAITING_HANDOVER = "awaiting_handover", "Awaiting handover record"
        HANDOVER_RECORDED = "handover_recorded", "Handover recorded"
        NEEDS_REVIEW = "needs_review", "Needs review"
        CANCELLED = "cancelled", "Closed"

    class Condition(models.TextChoices):
        LIKE_NEW = "like_new", "Like new"
        GOOD = "good", "Good, light wear"
        WORN = "worn", "Worn but usable"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="listings")
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=1000, blank=True)
    condition = models.CharField(max_length=20, choices=Condition.choices)
    width_cm = models.PositiveSmallIntegerField()
    depth_cm = models.PositiveSmallIntegerField()
    height_cm = models.PositiveSmallIntegerField()
    handling_notes = models.CharField(max_length=200, blank=True)
    needs_extra_helper = models.BooleanField(default=False)
    ownership_declared = models.BooleanField(default=False)
    zone = models.ForeignKey(Zone, on_delete=models.PROTECT, related_name="listings")
    deadline = models.DateTimeField()
    state = models.CharField(max_length=30, choices=State.choices, default=State.NEEDS_HELP)
    # Copied from the owner at creation; never taken from form input.
    is_synthetic = models.BooleanField(default=False)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["deadline", "created_at", "id"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("listings:detail", args=[self.pk])

    @property
    def is_expired(self):
        return self.state == self.State.NEEDS_HELP and self.deadline <= clock.now()

    @property
    def status_label(self):
        return "Expired" if self.is_expired else self.get_state_display()

    @property
    def is_open(self):
        return self.state == self.State.NEEDS_HELP and not self.is_expired

    @property
    def missing_roles(self):
        """What's still needed, from active offers (prefetched by listing selectors)."""
        missing = []
        if not getattr(self, "active_recipients", None):
            missing.append("someone who wants it")
        transports = getattr(self, "active_transports", None) or []
        if not transports:
            missing.append("transport")
        elif not any(t.fit_declared for t in transports):
            missing.append("transport that fits")
        if self.needs_extra_helper and not getattr(self, "active_helpers", None):
            missing.append("a second person to carry")
        return missing

    @property
    def is_editable(self):
        """Editable until collection starts. Editing a listing with a crew ends that plan."""
        return (self.state in (self.State.NEEDS_HELP, self.State.AWAITING_CONFIRMATIONS, self.State.READY)
                and not self.is_expired)


class ListingPrivate(models.Model):
    """Exact pickup details, kept apart from public listing fields."""

    class Source(models.TextChoices):
        GPS = "gps", "Phone location, confirmed by owner"
        MANUAL = "manual", "Entered manually"

    listing = models.OneToOneField(Listing, on_delete=models.CASCADE, related_name="private")
    pickup_details = models.CharField(max_length=300)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices)


def photo_path(instance, filename):
    return f"photos/{instance.uuid.hex}.jpg"


class Photo(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    image = models.FileField(upload_to=photo_path)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]


class AvailabilityWindow(models.Model):
    """A time the owner can hand the item over. Intervals are half-open: [start, end)."""

    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="windows")
    start = models.DateTimeField()
    end = models.DateTimeField()

    class Meta:
        ordering = ["start"]
        constraints = [models.CheckConstraint(condition=models.Q(start__lt=models.F("end")), name="window_start_before_end")]
