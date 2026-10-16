from django import forms
from django.utils import timezone
from django.utils.formats import date_format

from apps.core import clock
from apps.listings.models import Zone

from .models import TransportOffer, Vehicle


def _local_label(w):
    # Same wording as the times shown on item and plan screens, e.g. "Sun 18 Oct, 10:00 a.m. – 12:00 p.m.".
    start, end = timezone.localtime(w.start), timezone.localtime(w.end)
    label = f"{date_format(start, 'D j M, g:i a')} – {date_format(end, 'g:i a')}"
    if start.date() != end.date():
        label += f" ({date_format(end, 'D j M')})"
    return label


class OfferForm(forms.Form):
    windows = forms.ModelMultipleChoiceField(queryset=None, widget=forms.CheckboxSelectMultiple,
                                             label="When can you do the whole collection?",
                                             error_messages={"required": "Choose at least one time."})

    def __init__(self, *args, listing, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.listing, self.user = listing, user
        self.fields["windows"].queryset = listing.windows.filter(start__gt=clock.now())
        self.fields["windows"].label_from_instance = _local_label


class RecipientOfferForm(OfferForm):
    destination_zone = forms.ModelChoiceField(queryset=Zone.objects.all(), label="Your neighbourhood area", empty_label="Choose your area",
                                              help_text="Shown to neighbours planning the trip.")
    destination_details = forms.CharField(max_length=300, label="Where it should go (private)",
                                          widget=forms.Textarea(attrs={"rows": 2}),
                                          help_text="Your address and access notes. Shared only with a confirmed crew, after you approve.")


class TransportOfferForm(OfferForm):
    mode = forms.ChoiceField(choices=TransportOffer.Mode.choices, widget=forms.RadioSelect, label="How")
    vehicle = forms.ModelChoiceField(queryset=Vehicle.objects.none(), required=False, label="Your vehicle",
                                     empty_label="Choose a saved vehicle")
    new_vehicle = forms.CharField(max_length=60, required=False, label="Or add a vehicle",
                                  help_text="For example: grey hatchback, small van. No plate numbers.")
    fit_declared = forms.BooleanField(label="I've checked the item's size and can transport it for the whole time I chose, "
                                            "including loading and the trip.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["vehicle"].queryset = Vehicle.objects.filter(owner=self.user)
        if not self.fields["vehicle"].queryset.exists():
            del self.fields["vehicle"]

    def clean(self):
        data = super().clean()
        if data.get("mode") == TransportOffer.Mode.VEHICLE:
            if not data.get("vehicle") and not (data.get("new_vehicle") or "").strip():
                self.add_error("new_vehicle", "Choose or add the vehicle you'll use.")
        return data


class HelperOfferForm(OfferForm):
    pass
