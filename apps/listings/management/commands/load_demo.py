"""Create a clearly labelled synthetic locality, accounts and listings for local demos."""

from datetime import timedelta
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core import clock
from apps.coordination.models import Plan
from apps.core.models import ActionToken
from apps.coordination import services as coordination
from apps.listings import services
from apps.listings.images import sanitize_image
from apps.listings.models import Listing, Locality, Zone

LOCALITY = "Taman Contoh (demo township)"
ZONES = [
    ("Cempaka (demo)", "3.07210", "101.51840"),
    ("Kenanga (demo)", "3.07650", "101.52690"),
    ("Melati (demo)", "3.06620", "101.52380"),
    ("Seroja (demo)", "3.08110", "101.51450"),
]
PEOPLE = [("demo_aina", "Aina"), ("demo_ravi", "Ravi"), ("demo_meiling", "Mei Ling"), ("demo_hafiz", "Hafiz")]
DEMO_PHOTOS = Path(__file__).resolve().parents[2] / "demo_photos"


def demo_photo(filename):
    """A ready-made photo of a demo item. It goes through the same sanitizer as any upload."""
    return SimpleUploadedFile(filename, (DEMO_PHOTOS / filename).read_bytes(), content_type="image/jpeg")


class Command(BaseCommand):
    help = "Load synthetic demo data. --reset first removes existing synthetic listings (never real data)."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")

    @transaction.atomic
    def handle(self, *args, reset=False, **options):
        if reset:
            deleted = 0
            Plan.objects.filter(listing__is_synthetic=True).delete()
            for listing in Listing.objects.filter(is_synthetic=True):
                for photo in listing.photos.all():
                    photo.image.delete(save=False)
                listing.delete()
                deleted += 1
            self.stdout.write(f"Removed {deleted} synthetic listings.")

        locality, _ = Locality.objects.get_or_create(name=LOCALITY, defaults={"is_synthetic": True})
        zones = {}
        for name, lat, lng in ZONES:
            zones[name], _ = Zone.objects.get_or_create(locality=locality, name=name,
                                                        defaults={"latitude": lat, "longitude": lng})
        users = {}
        for username, display in PEOPLE:
            user, created = User.objects.get_or_create(username=username,
                                                       defaults={"display_name": display, "is_synthetic": True})
            if created:
                user.set_unusable_password()
                user.save()
            users[display] = user

        if Listing.objects.filter(is_synthetic=True).exists():
            self.stdout.write("Synthetic listings already exist; use --reset to recreate them.")
            return

        now = timezone.localtime(clock.now()).replace(minute=0, second=0, microsecond=0)
        day = now + timedelta(days=2)
        items = [
            (users["Aina"], "Wooden bookshelf", "Solid shelf, four levels. Small scratch on one side.", "good",
             (90, 30, 120), "Heavy; best carried by two people", True, zones["Cempaka (demo)"], "wooden-bookshelf.jpg"),
            (users["Ravi"], "Folding study table", "Folds flat. Fits in a car boot.", "like_new",
             (100, 50, 75), "", False, zones["Melati (demo)"], "folding-study-table.jpg"),
            (users["Mei Ling"], "Rattan armchair", "Comfortable reading chair, cushion included.", "worn",
             (70, 70, 85), "Light but bulky", False, zones["Kenanga (demo)"], "rattan-armchair.jpg"),
        ]
        created = {}
        for owner, title, description, condition, (w, d, h), notes, helper, zone, photo_file in items:
            photo = sanitize_image(demo_photo(photo_file))
            created[title] = services.publish_listing(owner, {
                "action_token": ActionToken.new(), "title": title, "description": description,
                "condition": condition, "width_cm": w, "depth_cm": d, "height_cm": h,
                "handling_notes": notes, "needs_extra_helper": helper, "zone": zone,
                "deadline": day + timedelta(days=3), "pickup_details": f"Demo address for {owner.display_name}",
                "latitude": None, "longitude": None,
                "windows": [(day.replace(hour=10), day.replace(hour=12)), (day.replace(hour=17), day.replace(hour=19))],
                "photos": [photo],
            })
        # Offers that compete for Mei Ling's van in the morning window, so the planner has to
        # spread the two collections across different times.
        shelf, table = created["Wooden bookshelf"], created["Folding study table"]
        shelf_morning = shelf.windows.order_by("start")[0]
        table_windows = list(table.windows.order_by("start"))
        coordination.offer_to_receive(users["Ravi"], shelf.pk, [shelf_morning], zones["Melati (demo)"],
                                      "Demo drop-off for Ravi")
        coordination.offer_transport(users["Mei Ling"], shelf.pk, [shelf_morning], "vehicle", None, "Small van (demo)", True)
        coordination.offer_help(users["Hafiz"], shelf.pk, [shelf_morning])
        coordination.offer_to_receive(users["Aina"], table.pk, table_windows, zones["Cempaka (demo)"],
                                      "Demo drop-off for Aina")
        van = users["Mei Ling"].vehicles.get()
        coordination.offer_transport(users["Mei Ling"], table.pk, table_windows, "vehicle", van, "", True)
        self.stdout.write(self.style.SUCCESS(f"Loaded {len(items)} synthetic listings and offers in {LOCALITY}."))
