"""
Accounts models.

Three model types:
  - TimeStampedModel  abstract base that adds created_at / updated_at
  - PatientProfile    extends the built-in User for patients
  - Specialty         lookup table for medical specialties
  - DoctorProfile     extends the built-in User for doctors
"""

from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract base class that adds audit timestamps to any model."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Specialty(models.Model):
    """Medical specialty lookup table (e.g. General Practice, Cardiology)."""

    name = models.CharField(max_length=80, unique=True)

    class Meta:
        verbose_name_plural = "specialties"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class PatientProfile(TimeStampedModel):
    """
    One-to-one extension of Django's User model for patients.

    Every user who registers as a patient gets exactly one PatientProfile.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="patientprofile",
    )
    phone = models.CharField(max_length=30, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)

    @property
    def full_name(self) -> str:
        return self.user.get_full_name() or self.user.username

    def __str__(self) -> str:
        return f"Patient: {self.full_name}"


class DoctorProfile(TimeStampedModel):
    """
    One-to-one extension of Django's User model for doctors.

    specialty may be blank initially; doctors can update it from their profile.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="doctorprofile",
    )
    specialty = models.ForeignKey(
        Specialty,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="doctors",
    )
    bio = models.TextField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    @property
    def full_name(self) -> str:
        return self.user.get_full_name() or self.user.username

    def __str__(self) -> str:
        return f"Dr. {self.full_name}"
