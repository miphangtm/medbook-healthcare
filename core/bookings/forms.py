"""
Bookings forms.

  AppointmentForm   — patient books a new appointment with a specific doctor
  RescheduleForm    — patient reschedules an existing appointment
  AvailabilityForm  — doctor creates or edits an availability block
"""

from django import forms
from django.utils import timezone

from .models import Appointment, Availability


class AppointmentForm(forms.ModelForm):
    """
    Form for a patient to book a new appointment.

    Accepts doctor as a constructor argument so availability and overlap
    checks can run during form validation (before the model is saved).
    """

    start = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )
    end = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )

    class Meta:
        model = Appointment
        fields = ["start", "end", "reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={"class": "form-control", "rows": 3, "placeholder": "Optional reason for visit"}
            ),
        }

    def __init__(self, doctor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.doctor = doctor

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")

        if start and start < timezone.now():
            self.add_error("start", "Start time must be in the future.")
        if start and end and end <= start:
            self.add_error("end", "End time must be after the start time.")

        if start and end and self.doctor:
            self._validate_availability(start, end)
            self._validate_no_overlap(start, end)

        return cleaned

    def _validate_availability(self, start, end):
        """Ensure the requested slot falls inside one of the doctor's availability blocks."""
        is_available = Availability.objects.filter(
            doctor=self.doctor,
            start__lte=start,
            end__gte=end,
        ).exists()
        if not is_available:
            self.add_error(None, "The selected time is outside this doctor's availability.")

    def _validate_no_overlap(self, start, end):
        """Ensure no active appointment already occupies this time slot."""
        current_pk = self.instance.pk if self.instance else None
        overlap = (
            Appointment.objects.filter(
                doctor=self.doctor,
                status__in=["PENDING", "CONFIRMED"],
                start__lt=end,
                end__gt=start,
            )
            .exclude(pk=current_pk)
            .exists()
        )
        if overlap:
            self.add_error(None, "This time slot overlaps with an existing appointment.")


class RescheduleForm(forms.ModelForm):
    """
    Form for a patient to move an existing appointment to a new time.

    Unlike AppointmentForm, the doctor is already known via self.instance,
    so we read it from there during clean().
    """

    start = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )
    end = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )

    class Meta:
        model = Appointment
        fields = ["start", "end", "reason"]
        widgets = {
            "reason": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")

        if start and start < timezone.now():
            self.add_error("start", "Start time must be in the future.")
        if start and end and end <= start:
            self.add_error("end", "End time must be after the start time.")

        # self.instance is populated because we always pass instance=appt.
        if start and end and self.instance and self.instance.pk:
            doctor = self.instance.doctor
            self._validate_availability(doctor, start, end)
            self._validate_no_overlap(doctor, start, end)

        return cleaned

    def _validate_availability(self, doctor, start, end):
        is_available = Availability.objects.filter(
            doctor=doctor,
            start__lte=start,
            end__gte=end,
        ).exists()
        if not is_available:
            self.add_error(None, "The new time is outside this doctor's availability.")

    def _validate_no_overlap(self, doctor, start, end):
        # Exclude the current appointment so it doesn't conflict with itself.
        overlap = (
            Appointment.objects.filter(
                doctor=doctor,
                status__in=["PENDING", "CONFIRMED"],
                start__lt=end,
                end__gt=start,
            )
            .exclude(pk=self.instance.pk)
            .exists()
        )
        if overlap:
            self.add_error(None, "The new time overlaps with another appointment.")


class AvailabilityForm(forms.ModelForm):
    """Form for a doctor to add or update an availability block."""

    start = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )
    end = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local", "class": "form-control"}
        )
    )

    class Meta:
        model = Availability
        fields = ["start", "end", "note"]
        widgets = {
            "note": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Optional note for patients"}
            ),
        }

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start")
        end = cleaned.get("end")
        if start and start < timezone.now():
            self.add_error("start", "Start time must be in the future.")
        if start and end and end <= start:
            self.add_error("end", "End time must be after the start time.")
        return cleaned
