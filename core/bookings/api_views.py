"""
Bookings REST API ViewSets.

All endpoints require authentication (configured globally in settings).

  GET  /api/specialties/          — list all specialties
  GET  /api/doctors/              — list/search doctors
  CRUD /api/availability/         — doctor manages their own availability
  CRUD /api/appointments/         — patient/doctor sees their appointments
"""

from rest_framework import filters, permissions, viewsets
from rest_framework.exceptions import PermissionDenied

from accounts.models import DoctorProfile, Specialty

from .models import Appointment, Availability
from .serializers import (
    AppointmentSerializer,
    AvailabilitySerializer,
    DoctorSerializer,
    SpecialtySerializer,
)


class SpecialtyViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of medical specialties."""

    queryset = Specialty.objects.all().order_by("name")
    serializer_class = SpecialtySerializer
    permission_classes = [permissions.IsAuthenticated]


class DoctorViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Read-only list of doctors.

    Supports ?search= across name and specialty fields.
    """

    queryset = DoctorProfile.objects.select_related("user", "specialty").all()
    serializer_class = DoctorSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter]
    search_fields = [
        "user__first_name",
        "user__last_name",
        "user__username",
        "specialty__name",
    ]


class AvailabilityViewSet(viewsets.ModelViewSet):
    """
    Availability CRUD — doctors only.

    A doctor can only read and modify their own availability blocks.
    Patients and staff receive an empty queryset (not a 403) so they
    can discover the endpoint without leaking other doctors' data.
    """

    serializer_class = AvailabilitySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "doctorprofile"):
            return Availability.objects.filter(doctor=user.doctorprofile).order_by("start")
        return Availability.objects.none()

    def perform_create(self, serializer):
        user = self.request.user
        if not hasattr(user, "doctorprofile"):
            raise PermissionDenied("Only doctors can create availability blocks.")
        serializer.save(doctor=user.doctorprofile)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    Appointment CRUD.

    - Patients see their own appointments.
    - Doctors see appointments where they are the doctor.
    - No cross-role leakage.
    """

    serializer_class = AppointmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "patientprofile"):
            return (
                Appointment.objects
                .filter(patient=user.patientprofile)
                .select_related("doctor__user", "doctor__specialty")
                .order_by("-start")
            )
        if hasattr(user, "doctorprofile"):
            return (
                Appointment.objects
                .filter(doctor=user.doctorprofile)
                .select_related("patient__user")
                .order_by("-start")
            )
        return Appointment.objects.none()
