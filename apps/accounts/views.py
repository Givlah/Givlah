from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import SignupForm
from .models import User


class GivlahLoginView(LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if settings.DEMO_MODE:
            context["demo_users"] = User.objects.filter(is_synthetic=True, is_active=True).order_by("display_name")
        return context


def signup(request):
    if request.user.is_authenticated:
        return redirect("listings:nearby")
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"Welcome to Givlah, {user.display_name}.")
        return redirect("listings:nearby")
    return render(request, "accounts/signup.html", {"form": form})


@require_POST
def demo_switch(request):
    """Log in as a fictional demo account. Exists only in demo mode and only for synthetic users."""
    if not settings.DEMO_MODE:
        raise Http404
    user = get_object_or_404(User, pk=request.POST.get("user_id"), is_synthetic=True, is_active=True)
    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.info(request, f"Demo: now acting as {user.display_name} (synthetic account).")
    return redirect("listings:nearby")
