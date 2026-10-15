from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class GivlahUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Givlah", {"fields": ("display_name", "is_synthetic")}),)
    list_display = ("username", "display_name", "is_synthetic", "is_staff")
