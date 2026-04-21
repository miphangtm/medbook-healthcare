"""
Accounts views.

  register  — public sign-up; creates User + role profile, auto-logs in
  profile   — authenticated user views and edits their own details
"""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import DoctorProfileUpdateForm, ProfileUpdateForm, RegisterForm
from .models import DoctorProfile, PatientProfile


def register(request):
    """
    Create a new user account.

    After a valid POST:
      1. Save the User with a hashed password.
      2. Create the role-specific profile (PatientProfile or DoctorProfile).
      3. Log the user in and redirect to the dashboard.
    """
    if request.user.is_authenticated:
        return redirect("bookings:dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password"])
            user.save()

            role = form.cleaned_data["role"]
            if role == "patient":
                PatientProfile.objects.create(user=user)
            else:
                # Doctors start with no specialty; they set it from their profile.
                DoctorProfile.objects.create(user=user, specialty=None)

            login(request, user)
            messages.success(request, "Welcome! Your account has been created.")
            return redirect("bookings:dashboard")
    else:
        form = RegisterForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile(request):
    """
    View and edit the current user's profile.

    Doctors get DoctorProfileUpdateForm (includes bio + specialty).
    Patients get ProfileUpdateForm (name, email, phone).

    The view saves User fields via form.save(), then saves profile-specific
    fields (phone, bio, specialty) directly on the role model.
    """
    user = request.user
    is_doctor = hasattr(user, "doctorprofile")
    is_patient = hasattr(user, "patientprofile")
    role_profile = getattr(user, "doctorprofile", None) or getattr(user, "patientprofile", None)

    FormClass = DoctorProfileUpdateForm if is_doctor else ProfileUpdateForm

    # Pre-fill role-specific fields so the form shows current values.
    initial = {"phone": role_profile.phone if role_profile else ""}
    if is_doctor:
        initial["bio"] = user.doctorprofile.bio
        initial["specialty"] = user.doctorprofile.specialty

    if request.method == "POST":
        form = FormClass(request.POST, instance=user, initial=initial)
        if form.is_valid():
            form.save()

            # Save profile-specific fields to the role model.
            if is_doctor:
                dp = user.doctorprofile
                dp.phone = form.cleaned_data.get("phone", "")
                dp.bio = form.cleaned_data.get("bio", "")
                dp.specialty = form.cleaned_data.get("specialty")
                dp.save(update_fields=["phone", "bio", "specialty"])
            elif is_patient:
                pp = user.patientprofile
                pp.phone = form.cleaned_data.get("phone", "")
                pp.save(update_fields=["phone"])

            messages.success(request, "Profile updated successfully.")
            return redirect("accounts:profile")
    else:
        form = FormClass(instance=user, initial=initial)

    return render(request, "accounts/profile.html", {
        "form": form,
        "role_profile": role_profile,
        "is_doctor": is_doctor,
        "is_patient": is_patient,
    })
