"""
Bookings views.

Patient views:
  dashboard               — role-aware landing page
  doctor_list             — browse/search all doctors (paginated)
  doctor_detail           — doctor bio + upcoming availability
  book_appointment        — submit a new booking (PENDING)
  my_appointments         — patient's history with status filter + pagination
  appointment_cancel      — soft-cancel via status
  appointment_reschedule  — move to a new time slot

Doctor views:
  doctor_appointments     — incoming appointments with filter + pagination
  confirm_appointment     — confirm a PENDING appointment
  decline_appointment     — decline (cancel) a PENDING appointment
  availability_list       — manage availability blocks (paginated)
  availability_create     — add a new block
  availability_edit       — update an existing block
  availability_delete     — remove a block (with confirmation page)
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import doctor_required, patient_required
from accounts.models import DoctorProfile, PatientProfile

from .forms import AppointmentForm, AvailabilityForm, RescheduleForm
from .models import Appointment, Availability


# ---------------------------------------------------------------------------
# Shared
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    """
    Role-aware landing page.

    Doctors see today's schedule and a pending-count alert.
    Patients see their next five upcoming appointments.
    """
    ctx = {}

    if hasattr(request.user, "doctorprofile"):
        doctor = request.user.doctorprofile
        ctx["is_doctor"] = True
        ctx["doctor_schedule"] = (
            Appointment.objects
            .filter(doctor=doctor, start__date=timezone.now().date())
            .select_related("patient__user")
            .order_by("start")
        )
        ctx["pending_count"] = Appointment.objects.filter(
            doctor=doctor, status="PENDING"
        ).count()

    if hasattr(request.user, "patientprofile"):
        patient = request.user.patientprofile
        ctx["is_patient"] = True
        ctx["upcoming"] = (
            Appointment.objects
            .filter(patient=patient, start__gte=timezone.now())
            .exclude(status="CANCELLED")
            .select_related("doctor__user", "doctor__specialty")
            .order_by("start")[:5]
        )

    return render(request, "bookings/dashboard.html", ctx)


# ---------------------------------------------------------------------------
# Doctor discovery (patient-facing)
# ---------------------------------------------------------------------------

@login_required
def doctor_list(request):
    """List all doctors with name/specialty search and pagination."""
    query = request.GET.get("q", "").strip()
    doctors = DoctorProfile.objects.select_related("user", "specialty").order_by(
        "user__last_name", "user__first_name"
    )
    if query:
        doctors = doctors.filter(
            user__first_name__icontains=query
        ) | doctors.filter(
            user__last_name__icontains=query
        ) | doctors.filter(
            specialty__name__icontains=query
        )

    paginator = Paginator(doctors, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    # Preserve search query across pagination links
    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "bookings/doctor_list.html", {
        "page_obj": page_obj,
        "query": query,
        "query_params": query_params.urlencode(),
    })


@login_required
def doctor_detail(request, doctor_id):
    """Show a doctor's profile and upcoming availability blocks."""
    doctor = get_object_or_404(
        DoctorProfile.objects.select_related("user", "specialty"),
        pk=doctor_id,
    )
    upcoming_availability = (
        doctor.availabilities
        .filter(end__gte=timezone.now())
        .order_by("start")[:10]
    )
    return render(request, "bookings/doctor_detail.html", {
        "doctor": doctor,
        "availability": upcoming_availability,
        "is_patient": hasattr(request.user, "patientprofile"),
    })


# ---------------------------------------------------------------------------
# Appointment booking (patient)
# ---------------------------------------------------------------------------

@login_required
def book_appointment(request, doctor_id):
    """
    Patient books a new appointment with the specified doctor.

    The doctor's upcoming availability is passed to the template so the
    patient can see valid time windows without navigating away.

    New appointments are PENDING; the doctor confirms them separately.
    """
    doctor = get_object_or_404(
        DoctorProfile.objects.select_related("user", "specialty"),
        pk=doctor_id,
    )

    patient = getattr(request.user, "patientprofile", None)
    if not patient:
        messages.error(request, "You must have a patient account to book an appointment.")
        return redirect("bookings:doctor_detail", doctor_id=doctor.id)

    if request.method == "POST":
        form = AppointmentForm(doctor=doctor, data=request.POST)
        if form.is_valid():
            try:
                appt = form.save(commit=False)
                appt.patient = patient
                appt.doctor = doctor
                appt.status = "PENDING"
                appt.full_clean()
                appt.save()
                messages.success(request, "Appointment request sent! The doctor will confirm it shortly.")
                return redirect("bookings:my_appointments")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = AppointmentForm(doctor=doctor)

    # Show the doctor's upcoming availability on the booking page so the
    # patient doesn't have to navigate away to find valid time slots.
    upcoming_availability = (
        doctor.availabilities
        .filter(end__gte=timezone.now())
        .order_by("start")[:8]
    )

    return render(request, "bookings/book_appointment.html", {
        "doctor": doctor,
        "form": form,
        "availability": upcoming_availability,
    })


@login_required
def my_appointments(request):
    """
    Patient's full appointment history.

    Supports filtering by status (PENDING / CONFIRMED / CANCELLED) and
    is paginated.
    """
    patient = getattr(request.user, "patientprofile", None)
    if not patient:
        messages.error(request, "You must have a patient account to view appointments.")
        return redirect("bookings:dashboard")

    status_filter = request.GET.get("status", "")
    appointments = (
        Appointment.objects
        .filter(patient=patient)
        .select_related("doctor__user", "doctor__specialty")
        .order_by("-start")
    )
    if status_filter in ("PENDING", "CONFIRMED", "CANCELLED"):
        appointments = appointments.filter(status=status_filter)

    paginator = Paginator(appointments, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "bookings/my_appointments.html", {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "query_params": query_params.urlencode(),
    })


@login_required
@patient_required
def appointment_cancel(request, pk):
    """Patient cancels one of their own appointments (soft-delete via status)."""
    patient = request.user.patientprofile
    appt = get_object_or_404(Appointment, pk=pk, patient=patient)

    if appt.status == "CANCELLED":
        messages.info(request, "That appointment is already cancelled.")
        return redirect("bookings:my_appointments")

    if request.method == "POST":
        appt.status = "CANCELLED"
        appt.save(update_fields=["status"])
        messages.success(request, "Appointment cancelled.")
        return redirect("bookings:my_appointments")

    return render(request, "bookings/confirm_delete.html", {
        "object": appt,
        "type": "appointment",
        "action_label": "Cancel Appointment",
        "cancel_url": reverse("bookings:my_appointments"),
    })


@login_required
@patient_required
def appointment_reschedule(request, pk):
    """Patient moves an existing appointment to a new time slot."""
    patient = request.user.patientprofile
    appt = get_object_or_404(Appointment, pk=pk, patient=patient)

    if appt.status == "CANCELLED":
        messages.error(request, "You cannot reschedule a cancelled appointment.")
        return redirect("bookings:my_appointments")

    if request.method == "POST":
        form = RescheduleForm(request.POST, instance=appt)
        if form.is_valid():
            try:
                updated = form.save(commit=False)
                # Rescheduling resets status to PENDING for doctor re-confirmation.
                updated.status = "PENDING"
                updated.full_clean()
                updated.save()
                messages.success(request, "Appointment rescheduled. The doctor will re-confirm it.")
                return redirect("bookings:my_appointments")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = RescheduleForm(instance=appt)

    return render(request, "bookings/reschedule.html", {"form": form, "appt": appt})


# ---------------------------------------------------------------------------
# Doctor appointment management
# ---------------------------------------------------------------------------

@login_required
@doctor_required
def doctor_appointments(request):
    """Doctor views all their appointments with status filter and pagination."""
    doctor = request.user.doctorprofile
    status_filter = request.GET.get("status", "")

    appointments = (
        Appointment.objects
        .filter(doctor=doctor)
        .select_related("patient__user")
        .order_by("-start")
    )
    if status_filter in ("PENDING", "CONFIRMED", "CANCELLED"):
        appointments = appointments.filter(status=status_filter)

    paginator = Paginator(appointments, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    query_params.pop("page", None)

    return render(request, "bookings/doctor_appointments.html", {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "query_params": query_params.urlencode(),
        "pending_count": Appointment.objects.filter(doctor=doctor, status="PENDING").count(),
    })


@login_required
@doctor_required
def confirm_appointment(request, pk):
    """Doctor confirms a PENDING appointment (POST only)."""
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user.doctorprofile)

    if request.method == "POST":
        if appointment.status == "PENDING":
            appointment.status = "CONFIRMED"
            appointment.save(update_fields=["status"])
            messages.success(request, f"Appointment with {appointment.patient.full_name} confirmed.")
        else:
            messages.info(request, "Only pending appointments can be confirmed.")

    return redirect("bookings:doctor_appointments")


@login_required
@doctor_required
def decline_appointment(request, pk):
    """
    Doctor declines (cancels) a PENDING appointment (POST only).

    Uses a confirmation page on GET so the doctor doesn't accidentally
    decline with a misclick.
    """
    appointment = get_object_or_404(Appointment, pk=pk, doctor=request.user.doctorprofile)

    if appointment.status != "PENDING":
        messages.info(request, "Only pending appointments can be declined.")
        return redirect("bookings:doctor_appointments")

    if request.method == "POST":
        appointment.status = "CANCELLED"
        appointment.save(update_fields=["status"])
        messages.warning(request, f"Appointment with {appointment.patient.full_name} declined.")
        return redirect("bookings:doctor_appointments")

    return render(request, "bookings/confirm_delete.html", {
        "object": appointment,
        "type": "appointment",
        "action_label": "Decline Appointment",
        "cancel_url": reverse("bookings:doctor_appointments"),
    })


# ---------------------------------------------------------------------------
# Availability management (doctor)
# ---------------------------------------------------------------------------

@login_required
@doctor_required
def availability_list(request):
    """Doctor sees all their availability blocks, paginated."""
    doctor = request.user.doctorprofile
    items = Availability.objects.filter(doctor=doctor).order_by("start")

    paginator = Paginator(items, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(request, "bookings/availability_list.html", {"page_obj": page_obj})


@login_required
@doctor_required
def availability_create(request):
    """Doctor adds a new availability block."""
    doctor = request.user.doctorprofile

    if request.method == "POST":
        form = AvailabilityForm(request.POST)
        if form.is_valid():
            try:
                avail = form.save(commit=False)
                avail.doctor = doctor
                avail.full_clean()
                avail.save()
                messages.success(request, "Availability block added.")
                return redirect("bookings:availability_list")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = AvailabilityForm()

    return render(request, "bookings/availability_form.html", {
        "form": form,
        "title": "Add Availability",
    })


@login_required
@doctor_required
def availability_edit(request, pk):
    """Doctor updates an existing availability block."""
    doctor = request.user.doctorprofile
    avail = get_object_or_404(Availability, pk=pk, doctor=doctor)

    if request.method == "POST":
        form = AvailabilityForm(request.POST, instance=avail)
        if form.is_valid():
            try:
                updated = form.save(commit=False)
                updated.full_clean()
                updated.save()
                messages.success(request, "Availability updated.")
                return redirect("bookings:availability_list")
            except ValidationError as exc:
                form.add_error(None, exc)
    else:
        form = AvailabilityForm(instance=avail)

    return render(request, "bookings/availability_form.html", {
        "form": form,
        "title": "Edit Availability",
    })


@login_required
@doctor_required
def availability_delete(request, pk):
    """Doctor removes an availability block (GET shows confirmation, POST deletes)."""
    doctor = request.user.doctorprofile
    avail = get_object_or_404(Availability, pk=pk, doctor=doctor)

    if request.method == "POST":
        avail.delete()
        messages.success(request, "Availability block deleted.")
        return redirect("bookings:availability_list")

    return render(request, "bookings/confirm_delete.html", {
        "object": avail,
        "type": "availability slot",
        "action_label": "Delete Slot",
        "cancel_url": reverse("bookings:availability_list"),
    })
