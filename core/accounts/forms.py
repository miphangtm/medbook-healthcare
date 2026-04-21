"""
Accounts forms.

  RegisterForm            — new user sign-up (username, name, email, password, role)
  ProfileUpdateForm       — edit name, email, and phone (patients)
  DoctorProfileUpdateForm — edit name, email, phone, bio, and specialty (doctors)
"""

from django import forms
from django.contrib.auth.models import User

from .models import Specialty


class RegisterForm(forms.ModelForm):
    """
    Registration form that creates a Django User and assigns a role.

    The role field is used in the view to create either a PatientProfile
    or a DoctorProfile after the User is saved.
    """

    ROLE_CHOICES = (
        ("patient", "Patient"),
        ("doctor", "Doctor"),
    )

    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
        min_length=8,
    )
    confirm_password = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"class": "form-control"}),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email"]
        widgets = {
            "username":   forms.TextInput(attrs={"class": "form-control"}),
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name":  forms.TextInput(attrs={"class": "form-control"}),
            "email":      forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("confirm_password"):
            self.add_error("confirm_password", "Passwords do not match.")
        return cleaned


class ProfileUpdateForm(forms.ModelForm):
    """
    Patient profile editor: display name, email, and phone.

    Phone is stored on PatientProfile; the view saves it there after
    calling form.save() on the User instance.
    """

    phone = forms.CharField(
        max_length=30,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. +61 4xx xxx xxx",
        }),
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control"}),
            "last_name":  forms.TextInput(attrs={"class": "form-control"}),
            "email":      forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if email and User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("That email is already in use by another account.")
        return email


class DoctorProfileUpdateForm(ProfileUpdateForm):
    """
    Doctor profile editor: extends ProfileUpdateForm with bio and specialty.

    bio and specialty are stored on DoctorProfile; the view saves them
    there after calling form.save() on the User instance.
    """

    bio = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control",
            "rows": 4,
            "placeholder": "A short bio visible to patients…",
        }),
    )
    specialty = forms.ModelChoiceField(
        queryset=Specialty.objects.all().order_by("name"),
        required=False,
        empty_label="— Select specialty —",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
