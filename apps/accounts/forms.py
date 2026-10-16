from django.contrib.auth.forms import UserCreationForm

from .models import User


class SignupForm(UserCreationForm):
    class Meta:
        model = User
        fields = ("username", "display_name")
        labels = {"display_name": "Name shown to neighbours"}
        help_texts = {"display_name": "First name or nickname. Don't use your full name or address."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Plain sentences instead of Django's developer-style hints and bulleted validator list.
        self.fields["username"].help_text = "Letters, numbers and @ . + - _ only."
        self.fields["password1"].help_text = ("At least 8 characters, not only numbers, not a common password "
                                              "and not similar to your username.")
        self.fields["password2"].label = "Confirm password"
        self.fields["password2"].help_text = ""
