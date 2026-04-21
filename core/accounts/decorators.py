"""
Role-based access decorators.

Usage (always stack on top of @login_required so anonymous users are
redirected to login before the role check runs):

    @login_required
    @doctor_required
    def my_doctor_view(request): ...

    @login_required
    @patient_required
    def my_patient_view(request): ...
"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect


def patient_required(view_func):
    """Allow only users who have a PatientProfile."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if hasattr(request.user, "patientprofile"):
            return view_func(request, *args, **kwargs)
        messages.error(request, "You need a patient account to access that page.")
        return redirect("bookings:dashboard")

    return _wrapped


def doctor_required(view_func):
    """Allow only users who have a DoctorProfile."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if hasattr(request.user, "doctorprofile"):
            return view_func(request, *args, **kwargs)
        messages.error(request, "You need a doctor account to access that page.")
        return redirect("bookings:dashboard")

    return _wrapped
