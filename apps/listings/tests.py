import hashlib
import io
import shutil
import tempfile
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.listings.images import ImageRejected, sanitize_image
from apps.listings.models import Listing, Locality, Zone

TEMP_MEDIA = tempfile.mkdtemp(prefix="givlah-test-media-")


def jpeg_with_gps(size=(2400, 1800), orientation=None):
    """A JPEG carrying GPS EXIF (and optionally an orientation tag), like a phone photo."""
    image = Image.new("RGB", size, (200, 120, 60))
    exif = Image.Exif()
    exif[0x8825] = {1: "N", 2: (3.0, 4.0, 5.0), 3: "E", 4: (101.0, 30.0, 0.0)}  # GPSInfo
    exif[0x010F] = "PhoneMaker"
    if orientation:
        exif[0x0112] = orientation
    buf = io.BytesIO()
    image.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def upload(data, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


class SanitizeImageTests(TestCase):
    def test_strips_gps_and_metadata_and_resizes(self):
        jpeg, width, height = sanitize_image(upload(jpeg_with_gps()))
        out = Image.open(io.BytesIO(jpeg))
        self.assertEqual(out.format, "JPEG")
        self.assertEqual((width, height), (1600, 1200))
        self.assertEqual(len(out.getexif()), 0)
        self.assertNotIn(b"PhoneMaker", jpeg)
        self.assertNotIn("exif", out.info)

    def test_applies_camera_orientation(self):
        # Orientation 6 means "rotate 90° clockwise to display": a landscape sensor image shows as portrait.
        _jpeg, width, height = sanitize_image(upload(jpeg_with_gps(size=(1200, 800), orientation=6)))
        self.assertEqual((width, height), (800, 1200))

    def test_rejects_disguised_non_image(self):
        with self.assertRaises(ImageRejected):
            sanitize_image(upload(b"<?php echo 'not a photo'; ?>" * 10, name="evil.jpg"))

    def test_rejects_unsupported_format(self):
        buf = io.BytesIO()
        Image.new("RGB", (50, 50)).save(buf, format="GIF")
        with self.assertRaises(ImageRejected):
            sanitize_image(upload(buf.getvalue(), name="anim.jpg"))

    def test_rejects_oversized_file(self):
        with self.assertRaises(ImageRejected):
            sanitize_image(upload(b"\xff\xd8" + b"0" * (5 * 1024 * 1024 + 1)))

    def test_rejects_too_many_pixels(self):
        buf = io.BytesIO()
        Image.new("L", (4000, 3001)).save(buf, format="PNG")  # 12,004,000 px, small file
        with self.assertRaises(ImageRejected):
            sanitize_image(upload(buf.getvalue(), name="big.png", content_type="image/png"))

    def test_rejects_truncated_image(self):
        with self.assertRaises(ImageRejected):
            sanitize_image(upload(jpeg_with_gps()[:2000]))

    def test_flattens_transparent_png(self):
        buf = io.BytesIO()
        Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(buf, format="PNG")
        jpeg, _w, _h = sanitize_image(upload(buf.getvalue(), name="t.png", content_type="image/png"))
        self.assertEqual(Image.open(io.BytesIO(jpeg)).getpixel((50, 50)), (255, 255, 255))


@override_settings(MEDIA_ROOT=TEMP_MEDIA)
class ListingFlowTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEMP_MEDIA, ignore_errors=True)

    def setUp(self):
        locality = Locality.objects.create(name="Testville")
        self.zone = Zone.objects.create(locality=locality, name="North", latitude="3.07", longitude="101.52")
        self.owner = User.objects.create_user("owner", password="pw-123456!", display_name="Olivia")
        self.other = User.objects.create_user("other", password="pw-123456!", display_name="Oscar")
        self.owner_client = Client()
        self.owner_client.force_login(self.owner)
        self.other_client = Client()
        self.other_client.force_login(self.other)

    def local(self, dt):
        return timezone.localtime(dt).strftime("%Y-%m-%dT%H:%M")

    def form_data(self, **overrides):
        start = timezone.now() + timedelta(days=1)
        data = {
            "action_token": str(uuid.uuid4()),
            "title": "Wooden bookshelf",
            "description": "Four shelves",
            "condition": "good",
            "width_cm": "90", "depth_cm": "30", "height_cm": "120",
            "handling_notes": "Heavy",
            "needs_extra_helper": "on",
            "zone": str(self.zone.pk),
            "pickup_details": "No. 12, Jalan Rahsia 7, secret gate code 4321",
            "latitude": "3.071234", "longitude": "101.521234",
            "deadline": self.local(start + timedelta(days=3)),
            "window_1_start": self.local(start),
            "window_1_end": self.local(start + timedelta(hours=2)),
            "ownership_declared": "on",
            "photos": [upload(jpeg_with_gps())],
        }
        data.update(overrides)
        return data

    def publish(self, **overrides):
        response = self.owner_client.post(reverse("listings:create"), self.form_data(**overrides))
        return response

    def test_publish_stores_public_and_private_fields_separately(self):
        response = self.publish()
        listing = Listing.objects.get()
        self.assertRedirects(response, listing.get_absolute_url())
        self.assertEqual(listing.state, Listing.State.NEEDS_HELP)
        self.assertEqual(listing.private.source, "gps")
        self.assertEqual(str(listing.private.latitude), "3.071234")
        self.assertEqual(listing.photos.count(), 1)
        self.assertEqual(listing.windows.count(), 1)
        stored = listing.photos.get().image.read()
        self.assertNotIn(b"PhoneMaker", stored)
        self.assertEqual(len(Image.open(io.BytesIO(stored)).getexif()), 0)

    def test_other_users_never_receive_private_details(self):
        self.publish()
        listing = Listing.objects.get()
        for url in (reverse("listings:nearby"), listing.get_absolute_url()):
            body = self.other_client.get(url).content.decode()
            self.assertIn("Wooden bookshelf", body)
            self.assertIn("North", body)
            for secret in ("Jalan Rahsia", "4321", "3.071234", "101.521234"):
                self.assertNotIn(secret, body)
        owner_body = self.owner_client.get(listing.get_absolute_url()).content.decode()
        self.assertIn("Jalan Rahsia", owner_body)
        self.assertNotIn("3.071234", owner_body)

    def test_manual_location_when_gps_unavailable(self):
        self.publish(latitude="", longitude="")
        private = Listing.objects.get().private
        self.assertEqual(private.source, "manual")
        self.assertIsNone(private.latitude)

    def test_half_supplied_coordinates_rejected(self):
        response = self.publish(longitude="")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Listing.objects.exists())

    def test_validation_error_keeps_other_fields(self):
        response = self.publish(title="", photos=[])
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn("Add at least one photo", body)
        self.assertIn("This field is required", body)
        self.assertIn('value="90"', body)
        self.assertIn("Jalan Rahsia", body)  # owner's own form, re-rendered to the owner only
        self.assertFalse(Listing.objects.exists())

    def test_window_rules(self):
        start = timezone.now() + timedelta(days=1)
        cases = {
            "end before start": {"window_1_start": self.local(start), "window_1_end": self.local(start - timedelta(hours=1))},
            "past start": {"window_1_start": self.local(timezone.now() - timedelta(hours=3)),
                           "window_1_end": self.local(timezone.now() + timedelta(hours=1))},
            "after deadline": {"deadline": self.local(start + timedelta(hours=1)),
                               "window_1_end": self.local(start + timedelta(hours=2))},
            "overlapping": {"window_2_start": self.local(start + timedelta(hours=1)),
                            "window_2_end": self.local(start + timedelta(hours=3))},
            "past deadline": {"deadline": self.local(timezone.now() - timedelta(hours=1))},
        }
        for name, overrides in cases.items():
            with self.subTest(name):
                response = self.publish(**overrides)
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Listing.objects.exists())

    def test_ownership_declaration_required(self):
        data = self.form_data()
        del data["ownership_declared"]
        self.owner_client.post(reverse("listings:create"), data)
        self.assertFalse(Listing.objects.exists())

    def test_too_many_photos_rejected(self):
        self.publish(photos=[upload(jpeg_with_gps(size=(200, 200)), name=f"{i}.jpg") for i in range(4)])
        self.assertFalse(Listing.objects.exists())

    def test_resubmitted_form_creates_one_listing(self):
        token = str(uuid.uuid4())
        first = self.publish(action_token=token)
        second = self.publish(action_token=token)
        self.assertEqual(Listing.objects.count(), 1)
        self.assertEqual(first["Location"], second["Location"])

    def test_synthetic_flag_comes_from_owner_not_form(self):
        self.publish(is_synthetic="on")
        self.assertFalse(Listing.objects.get().is_synthetic)

    def test_other_user_cannot_edit_or_close(self):
        self.publish()
        listing = Listing.objects.get()
        self.assertEqual(self.other_client.get(reverse("listings:edit", args=[listing.pk])).status_code, 403)
        data = self.form_data(title="Hijacked")
        data["revision"] = str(listing.revision)
        self.assertEqual(self.other_client.post(reverse("listings:edit", args=[listing.pk]), data).status_code, 403)
        self.assertEqual(self.other_client.post(reverse("listings:close", args=[listing.pk]),
                                                {"revision": listing.revision}).status_code, 403)
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Wooden bookshelf")
        self.assertEqual(listing.state, Listing.State.NEEDS_HELP)

    def test_edit_bumps_revision_and_rejects_stale_form(self):
        self.publish()
        listing = Listing.objects.get()
        url = reverse("listings:edit", args=[listing.pk])
        data = self.form_data(title="Tall bookshelf", photos=[])
        data["revision"] = "1"
        self.assertRedirects(self.owner_client.post(url, data), listing.get_absolute_url())
        listing.refresh_from_db()
        self.assertEqual((listing.title, listing.revision), ("Tall bookshelf", 2))
        self.assertEqual(listing.photos.count(), 1)  # kept when none uploaded
        stale = self.form_data(title="Old tab edit", photos=[])
        stale["revision"] = "1"
        self.owner_client.post(url, stale)
        listing.refresh_from_db()
        self.assertEqual(listing.title, "Tall bookshelf")

    def test_close_hides_listing_and_photo_from_others(self):
        self.publish()
        listing = Listing.objects.get()
        photo_url = reverse("listings:photo", args=[listing.photos.get().uuid])
        self.assertEqual(self.other_client.get(photo_url).status_code, 200)
        self.owner_client.post(reverse("listings:close", args=[listing.pk]), {"revision": listing.revision})
        listing.refresh_from_db()
        self.assertEqual(listing.state, Listing.State.CANCELLED)
        self.assertEqual(self.other_client.get(listing.get_absolute_url()).status_code, 404)
        self.assertEqual(self.other_client.get(photo_url).status_code, 404)
        self.assertNotContains(self.other_client.get(reverse("listings:nearby")), "Wooden bookshelf")
        self.assertEqual(self.owner_client.get(listing.get_absolute_url()).status_code, 200)

    def test_expired_listing_not_shown_nearby(self):
        self.publish()
        Listing.objects.update(deadline=timezone.now() - timedelta(minutes=1))
        self.assertNotContains(self.other_client.get(reverse("listings:nearby")), "Wooden bookshelf")
        self.assertContains(self.owner_client.get(reverse("listings:activity")), "Expired")

    def test_close_requires_post(self):
        self.publish()
        listing = Listing.objects.get()
        self.assertEqual(self.owner_client.get(reverse("listings:close", args=[listing.pk])).status_code, 405)

    def test_mutation_without_csrf_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.owner)
        response = csrf_client.post(reverse("listings:create"), self.form_data())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Listing.objects.exists())

    def test_pages_require_login(self):
        anonymous = Client()
        for url in (reverse("listings:nearby"), reverse("listings:create"), reverse("listings:activity")):
            self.assertEqual(anonymous.get(url).status_code, 302)


DEMO_MEDIA = tempfile.mkdtemp(prefix="givlah-test-media-")
DEMO_PHOTO_FILES = {"Wooden bookshelf": "wooden-bookshelf.jpg", "Folding study table": "folding-study-table.jpg",
                    "Rattan armchair": "rattan-armchair.jpg"}


@override_settings(MEDIA_ROOT=DEMO_MEDIA)
class DemoDataTests(TestCase):
    """load_demo gives each demo item its own photo, and pages show that photo."""

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(DEMO_MEDIA, ignore_errors=True)

    def setUp(self):
        call_command("load_demo", stdout=io.StringIO())
        self.client.force_login(User.objects.get(username="demo_hafiz"))  # offered to help carry the bookshelf

    def test_each_demo_listing_stores_its_own_sanitized_photo(self):
        listings = Listing.objects.filter(is_synthetic=True)
        self.assertEqual(sorted(listing.title for listing in listings), sorted(DEMO_PHOTO_FILES))
        stored = set()
        for listing in listings:
            photo = listing.photos.get()
            with photo.image.open("rb") as f:
                data = f.read()
            image = Image.open(io.BytesIO(data))
            source = Image.open(settings.BASE_DIR / "apps" / "listings" / "demo_photos" / DEMO_PHOTO_FILES[listing.title])
            self.assertEqual(image.format, "JPEG")
            self.assertEqual(len(image.getexif()), 0)
            # The supplied photos are under the 1600 px limit, so the sanitizer keeps their size.
            self.assertEqual((image.size, (photo.width, photo.height)), (source.size, source.size))
            stored.add(hashlib.sha256(data).digest())
        self.assertEqual(len(stored), 3)

    def test_pages_show_the_listing_photo(self):
        shelf = Listing.objects.get(title="Wooden bookshelf")
        photo_url = reverse("listings:photo", args=[shelf.photos.get().uuid])
        nearby = self.client.get(reverse("listings:nearby"))
        self.assertContains(nearby, photo_url)
        self.assertNotContains(nearby, "images/slots/item-card.png")
        detail = self.client.get(shelf.get_absolute_url())
        self.assertContains(detail, f'src="{photo_url}" alt="Photo 1 of Wooden bookshelf"')
        self.assertNotContains(detail, "images/slots/item-detail.png")
        activity = self.client.get(reverse("listings:activity"))
        self.assertContains(activity, photo_url)
        self.assertNotContains(activity, "images/slots/item-thumbnail.png")
        response = self.client.get(photo_url)
        self.assertEqual((response.status_code, response["Content-Type"]), (200, "image/jpeg"))

    def test_listing_without_photo_shows_parcel_illustration(self):
        shelf = Listing.objects.get(title="Wooden bookshelf")
        shelf.photos.all().delete()
        self.assertContains(self.client.get(reverse("listings:nearby")), "images/slots/item-card.png", count=1)
        self.assertContains(self.client.get(shelf.get_absolute_url()), "images/slots/item-detail.png", count=1)
        self.assertContains(self.client.get(reverse("listings:activity")), "images/slots/item-thumbnail.png", count=1)
