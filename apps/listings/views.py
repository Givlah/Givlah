import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.models import ActionToken

from . import selectors, services
from .forms import ListingForm
from .models import Zone


def _zone_points():
    """Public zone representative points, used by the browser to suggest the nearest area."""
    return json.dumps([{"id": z.pk, "name": z.name, "lat": float(z.latitude), "lng": float(z.longitude)}
                       for z in Zone.objects.all()])


@login_required
def nearby(request):
    from apps.coordination.services import reconcile
    reconcile()
    return render(request, "listings/nearby.html", {"listings": selectors.nearby_listings()})


@login_required
def create(request):
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES)
        if form.is_valid():
            result = services.publish_listing(request.user, form.cleaned_data)
            if isinstance(result, services.Duplicate):
                return redirect(result.result_url)
            messages.success(request, "Your item is published. Neighbours can now offer to help.")
            return redirect(result)
    else:
        form = ListingForm(initial={"action_token": ActionToken.new()})
    return render(request, "listings/form.html", {"form": form, "zone_points": _zone_points(), "editing": False})


@login_required
def detail(request, pk):
    listing = selectors.visible_listing(request.user, pk)
    if listing is None:
        raise Http404
    from apps.coordination import selectors as coordination_selectors, services as coordination_services
    coordination_services.reconcile()
    listing = selectors.visible_listing(request.user, pk)
    plan = coordination_selectors.active_plan(listing)
    return render(request, "listings/detail.html", {
        "listing": listing,
        "private": selectors.private_details_for(request.user, listing),
        "is_owner": listing.owner_id == request.user.pk,
        "active_plan": plan,
        "my_plan_role": plan.roles_of(request.user.pk) if plan else [],
        "my_offers": coordination_selectors.my_offers(request.user, listing),
        "can_offer": listing.state in coordination_services.OPEN_FOR_OFFERS and not listing.is_expired,
    })


def _edit_initial(listing, private):
    initial = {f: getattr(listing, f) for f in ("title", "description", "condition", "width_cm", "depth_cm",
                                                 "height_cm", "handling_notes", "needs_extra_helper", "deadline")}
    initial.update(zone=listing.zone_id, ownership_declared=True, action_token=ActionToken.new())
    if private:
        initial.update(pickup_details=private.pickup_details, latitude=private.latitude, longitude=private.longitude)
    for i, window in enumerate(listing.windows.all()[:3], start=1):
        initial[f"window_{i}_start"] = window.start
        initial[f"window_{i}_end"] = window.end
    return initial


@login_required
def edit(request, pk):
    listing = selectors.visible_listing(request.user, pk)
    if listing is None:
        raise Http404
    if listing.owner_id != request.user.pk:
        raise PermissionDenied
    if not listing.is_editable:
        messages.error(request, "This listing can no longer be edited.")
        return redirect(listing)
    status = 200
    if request.method == "POST":
        form = ListingForm(request.POST, request.FILES, require_photos=False)
        if form.is_valid():
            try:
                revision = int(request.POST.get("revision", ""))
            except ValueError:
                revision = -1
            try:
                services.update_listing(request.user, listing.pk, revision, form.cleaned_data)
            except services.StaleRevision:
                messages.error(request, "This listing changed since you opened it. Nothing was saved. "
                                        "Review the current version and try again.")
                return redirect("listings:edit", pk=listing.pk)
            except services.ListingClosed:
                messages.error(request, "This listing can no longer be edited. Nothing was saved.")
                return redirect(listing)
            messages.success(request, "Changes saved.")
            return redirect(listing)
        status = 400
    else:
        form = ListingForm(initial=_edit_initial(listing, selectors.private_details_for(request.user, listing)),
                           require_photos=False)
    return render(request, "listings/form.html", {
        "form": form, "zone_points": _zone_points(), "editing": True, "listing": listing,
    }, status=status)


@login_required
@require_POST
def close(request, pk):
    listing = selectors.visible_listing(request.user, pk)
    if listing is None:
        raise Http404
    try:
        services.close_listing(request.user, pk, int(request.POST.get("revision", "-1")))
    except services.NotAllowed:
        raise PermissionDenied
    except (services.StaleRevision, services.ListingClosed, ValueError):
        messages.error(request, "This listing changed since you opened it. Nothing was closed.")
        return redirect(listing)
    messages.success(request, "Listing closed.")
    return redirect("listings:activity")


@login_required
def activity(request):
    from apps.coordination import selectors as coordination_selectors, services as coordination_services
    from apps.coordination.models import Plan
    coordination_services.reconcile()
    plans = list(coordination_selectors.plans_for(request.user)[:30])
    me = request.user.pk
    invitations = [p for p in plans if
                   (p.state == Plan.State.AWAITING_CONFIRMATIONS and not p.confirmations.filter(user_id=me).exists())
                   or (p.state in (Plan.State.AWAITING_HANDOVER, Plan.State.NEEDS_REVIEW)
                       and me in (p.owner_id, p.recipient_id) and not p.handovers.filter(user_id=me).exists())]
    offers = coordination_selectors.my_offers(request.user)
    return render(request, "listings/activity.html", {
        "listings": selectors.my_listings(request.user),
        "plans": [p for p in plans if p not in invitations],
        "invitations": invitations,
        "offers": [(role, o) for role in ("recipient", "transport", "helper") for o in offers[role]],
    })


@login_required
def photo(request, photo_uuid):
    item = selectors.visible_photo(request.user, photo_uuid)
    if item is None:
        raise Http404
    response = FileResponse(item.image.open("rb"), content_type="image/jpeg")
    response["Cache-Control"] = "private, max-age=3600"
    return response
