from datetime import timedelta
from decimal import Decimal

from django import forms

from apps.core import clock

from .images import ImageRejected, sanitize_image
from .models import Listing, Zone

WINDOW_SLOTS = 3
MAX_PHOTOS = 3
MAX_DEADLINE_DAYS = 60
MAX_WINDOW_HOURS = 12


class LocalDateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultiplePhotoField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        return [super(MultiplePhotoField, self).clean(f, initial) for f in files]


class ListingForm(forms.Form):
    title = forms.CharField(max_length=80, help_text="For example: Wooden bookshelf")
    description = forms.CharField(max_length=1000, required=False, widget=forms.Textarea(attrs={"rows": 3}))
    condition = forms.ChoiceField(choices=Listing.Condition.choices)
    width_cm = forms.IntegerField(min_value=1, max_value=500, label="Width (cm)", widget=forms.NumberInput(attrs={"inputmode": "numeric"}))
    depth_cm = forms.IntegerField(min_value=1, max_value=500, label="Depth (cm)", widget=forms.NumberInput(attrs={"inputmode": "numeric"}))
    height_cm = forms.IntegerField(min_value=1, max_value=500, label="Height (cm)", widget=forms.NumberInput(attrs={"inputmode": "numeric"}))
    handling_notes = forms.CharField(max_length=200, required=False, label="Handling notes",
                                     help_text="For example: heavy, glass panel, comes apart into two pieces")
    needs_extra_helper = forms.BooleanField(required=False, label="Needs two people to carry",
                                            widget=forms.CheckboxInput(attrs={"role": "switch"}))
    zone = forms.ModelChoiceField(queryset=Zone.objects.none(), label="Neighbourhood area", empty_label="Choose your area",
                                  help_text="Shown publicly. Your exact pickup details are not.")
    pickup_details = forms.CharField(max_length=300, label="Exact pickup details (private)",
                                     help_text="Address and access notes. Shared only with a confirmed crew, after you approve.",
                                     widget=forms.Textarea(attrs={"rows": 2}))
    latitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)
    longitude = forms.DecimalField(required=False, max_digits=9, decimal_places=6, widget=forms.HiddenInput)
    deadline = forms.DateTimeField(widget=LocalDateTimeInput, label="Collect by")
    photos = MultiplePhotoField(required=False, label="Photos (1 to 3)",
                                widget=MultipleFileInput(attrs={"accept": "image/jpeg,image/png,image/webp", "capture": "environment"}))
    ownership_declared = forms.BooleanField(
        label="I own this item or have permission to give it away, and it is not electrical, a mattress or hazardous.",
    )
    action_token = forms.UUIDField(widget=forms.HiddenInput)

    def __init__(self, *args, require_photos=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.require_photos = require_photos
        self.fields["zone"].queryset = Zone.objects.select_related("locality")
        for i in range(1, WINDOW_SLOTS + 1):
            required = i == 1
            self.fields[f"window_{i}_start"] = forms.DateTimeField(required=required, widget=LocalDateTimeInput,
                                                                   label=f"Available from" if i == 1 else "Another time: from")
            self.fields[f"window_{i}_end"] = forms.DateTimeField(required=required, widget=LocalDateTimeInput, label="until")
        # Shown as required on create; clean_photos enforces it (the field itself accepts a list).
        self.fields["photos"].required = require_photos
        if not require_photos:
            self.fields["photos"].label = "Replace photos (1 to 3)"

    def window_pairs(self):
        return [(self[f"window_{i}_start"], self[f"window_{i}_end"]) for i in range(1, WINDOW_SLOTS + 1)]

    def clean_photos(self):
        files = self.cleaned_data.get("photos") or []
        if len(files) > MAX_PHOTOS:
            raise forms.ValidationError("Add at most 3 photos.")
        if self.require_photos and not files:
            raise forms.ValidationError("Add at least one photo of the item.")
        sanitized = []
        for f in files:
            try:
                sanitized.append(sanitize_image(f))
            except ImageRejected as exc:
                raise forms.ValidationError(f"{f.name}: {exc}")
        return sanitized

    def clean_deadline(self):
        deadline = self.cleaned_data["deadline"]
        now = clock.now()
        if deadline <= now:
            raise forms.ValidationError("Choose a time in the future.")
        if deadline > now + timedelta(days=MAX_DEADLINE_DAYS):
            raise forms.ValidationError(f"Choose a time within the next {MAX_DEADLINE_DAYS} days.")
        return deadline

    def clean(self):
        data = super().clean()
        lat, lng = data.get("latitude"), data.get("longitude")
        if (lat is None) != (lng is None):
            raise forms.ValidationError("Location was incomplete. Try again or enter the details manually.")
        if lat is not None and not (Decimal(-90) <= lat <= Decimal(90) and Decimal(-180) <= lng <= Decimal(180)):
            raise forms.ValidationError("Location was invalid. Try again or enter the details manually.")

        now = clock.now()
        deadline = data.get("deadline")
        windows = []
        for i in range(1, WINDOW_SLOTS + 1):
            start, end = data.get(f"window_{i}_start"), data.get(f"window_{i}_end")
            if start is None and end is None:
                continue
            if start is None or end is None:
                self.add_error(f"window_{i}_end" if start else f"window_{i}_start", "Enter both a start and an end time.")
                continue
            if start >= end:
                self.add_error(f"window_{i}_end", "The end must be after the start.")
            elif start < now:
                self.add_error(f"window_{i}_start", "Choose a time in the future.")
            elif end - start > timedelta(hours=MAX_WINDOW_HOURS):
                self.add_error(f"window_{i}_end", f"Keep each time window to {MAX_WINDOW_HOURS} hours or less.")
            elif deadline and end > deadline:
                self.add_error(f"window_{i}_end", "The window must end by the collect-by time.")
            else:
                windows.append((start, end))
        windows.sort()
        for (s1, e1), (s2, e2) in zip(windows, windows[1:]):
            if s2 < e1:
                raise forms.ValidationError("Time windows overlap. Merge them into one window.")
        data["windows"] = windows
        return data
