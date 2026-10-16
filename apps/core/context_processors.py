from django.conf import settings


def givlah(request):
    context = {"demo_mode": settings.DEMO_MODE}
    if settings.DEMO_MODE and request.user.is_authenticated:
        from apps.accounts.models import User

        context["demo_switch_users"] = User.objects.filter(
            is_synthetic=True, is_active=True,
        ).order_by("display_name")
    return context
