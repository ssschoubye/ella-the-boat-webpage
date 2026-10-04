"""Creating an account from an invitation, and logging in afterwards.

The email address is the username (ADR 0014). It is never verified: the
invitation link is the proof that this person is allowed in, and the address
is only a label and a way to reach them.
"""
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

User = get_user_model()

# django.contrib.auth's username field. An address longer than this cannot be
# stored as one, which is vanishingly rare but produces a baffling error if
# left to the database.
USERNAME_MAX_LENGTH = User._meta.get_field("username").max_length


class SignupForm(forms.Form):
    """Shown on the invitation page. Creates the one account that link allows."""

    first_name = forms.CharField(
        label="Fornavn",
        max_length=30,
        help_text="Det, de andre ser på dine bookinger og kommentarer.",
    )
    email = forms.EmailField(
        label="E-mailadresse",
        help_text="Den bruger du til at logge ind med. Enhver adresse kan bruges.",
    )
    password1 = forms.CharField(label="Adgangskode", widget=forms.PasswordInput, strip=False)
    password2 = forms.CharField(
        label="Gentag adgangskode", widget=forms.PasswordInput, strip=False
    )

    def clean_email(self):
        # Lower-cased everywhere, so that Anton@ and anton@ are one account
        # and not two. EmailLoginForm does the same on the way in.
        email = self.cleaned_data["email"].strip().lower()
        if len(email) > USERNAME_MAX_LENGTH:
            raise ValidationError(
                f"Adressen er for lang (maks. {USERNAME_MAX_LENGTH} tegn)."
            )
        if User.objects.filter(username=email).exists():
            raise ValidationError(
                "Der findes allerede en konto med den adresse. Prøv at logge ind i stedet."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")

        if password1 and password2 and password1 != password2:
            self.add_error("password2", "De to adgangskoder er ikke ens.")
            return cleaned

        if password1:
            # Django's own validators (length, too common, all numeric, too
            # similar to the name or address). Run against a throwaway user so
            # the similarity check has something to compare with.
            candidate = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
            )
            try:
                validate_password(password1, candidate)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    def save(self):
        return User.objects.create_user(
            username=self.cleaned_data["email"],
            email=self.cleaned_data["email"],
            first_name=self.cleaned_data["first_name"],
            password=self.cleaned_data["password1"],
        )


class EmailLoginForm(AuthenticationForm):
    """Django's login form, relabelled and case-insensitive.

    Accounts are created with the email as the username, so this only has to
    normalise the same way SignupForm does -- no custom backend needed.
    """

    username = forms.EmailField(
        label="E-mailadresse",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Forkert e-mailadresse eller adgangskode.",
        "inactive": "Den konto er lukket.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()
