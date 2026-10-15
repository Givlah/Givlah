from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "display_name")
        labels = {"display_name": "Name shown to neighbours"}
        help_texts = {"display_name": "First name or nickname. Don't use your full name or address."}
