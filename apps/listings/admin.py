from django.contrib import admin

from .models import Listing, Locality, Zone

# Listings are read-only in admin: every state change must go through services.


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "is_synthetic")


@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ("name", "locality", "latitude", "longitude")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "zone", "state", "deadline", "is_synthetic")
    list_filter = ("state", "is_synthetic")

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
