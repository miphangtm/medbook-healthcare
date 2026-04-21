"""
Bookings models.

  Availability   — a time block a doctor is open for appointments
  Appointment    — a confirmed or pending booking between patient and doctor
"""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile

# Choices kept as a module-level constant so views/templates can reference
# them without importing the full model (e.g. for filter dropdowns).
APPT_STATUS = (
    ("PENDING", "Pending"),
    ("CONFIRMED", "Confirmed"),
    ("CANCELLED", "Cancelled"),
)


class Availability(models.Model):
    """
    A contiguous block of time during which a doctor can accept bookings.

    Doctors create these from their availability management page. Patients
    must choose appointment times that fall entirely within one of these blocks.
    """

    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    note = models.CharField(max_length=120, blank=True, help_text="Optional note shown to patients.")

    class Meta:
        ordering = ["start"]
        verbose_name_plural = "availabilities"

    def clean(self):
        if self.start and self.end and self.end <= self.start:
            raise ValidationError("Availability end time must be after the start time.")

    def __str__(self) -> str:
        return f"{self.doctor} | {self.start:%d %b %Y %H:%M} → {self.end:%H:%M}"


class Appointment(models.Model):
    """
    A booking between a patient and a doctor.

    Booking flow:
      1. Patient submits a booking → status defaults to PENDING.
      2. Doctor reviews and confirms → status becomes CONFIRMED.
      3. Either party can cancel → status becomes CANCELLED.

    The appointment start/end must fall within one of the doctor's
    Availability blocks and must not overlap any other active appointment
    for that doctor. This validation lives in AppointmentForm (and
    RescheduleForm) so that the API path can reuse model.full_clean().
    """

    patient = models.ForeignKey(
        PatientProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    doctor = models.ForeignKey(
        DoctorProfile,
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=10, choices=APPT_STATUS, default="PENDING")
    reason = models.CharField(max_length=200, blank=True, help_text="Optional reason for visit.")

    class Meta:
        ordering = ["-start"]

    @property
    def duration_minutes(self) -> int:
        """Convenience: appointment length in whole minutes."""
        return int((self.end - self.start).total_seconds() // 60)

    def clean(self):
        """Model-level field sanity checks (not overlap/availability — see forms)."""
        if not self.start or not self.end:
            raise ValidationError("Both start and end times must be provided.")
        if self.end <= self.start:
            raise ValidationError("Appointment end must be after the start.")
        if self.start < timezone.now():
            raise ValidationError("Cannot book an appointment in the past.")

    def __str__(self) -> str:
        return f"{self.patient} with {self.doctor} @ {self.start:%d %b %Y %H:%M}"
