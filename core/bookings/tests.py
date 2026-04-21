"""
Bookings test suite.

Test classes:
  AuthenticationTests        — page access for anonymous users
  DoctorViewTests            — doctor dashboard, availability, appointment views
  PatientViewTests           — patient browsing, booking, appointment management
  AppointmentFormTests       — form validation (availability, overlap, past, ordering)
  RescheduleFormTests        — reschedule validation including self-exclusion
  AppointmentLifecycleTests  — confirm, decline, cancel status transitions
  AccessControlTests         — role-based guards (doctor_required / patient_required)
  AvailabilityModelTests     — model-level validation
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile, Specialty
from bookings.forms import AppointmentForm, RescheduleForm
from bookings.models import Appointment, Availability


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def local_aware(year, month, day, hour, minute=0):
    """Return a timezone-aware datetime in the project's local timezone."""
    import datetime as _dt
    return timezone.make_aware(_dt.datetime(year, month, day, hour, minute))


def tomorrow_at(hour, minute=0):
    """Return a local-timezone-aware datetime for tomorrow at the given time."""
    local_now = timezone.localtime(timezone.now())
    tomorrow = local_now.date() + timedelta(days=1)
    return local_aware(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)


def fmt(d):
    """
    Format a timezone-aware datetime for a datetime-local HTML input.

    Converts to local time first so the form's DateTimeField parses it
    back to the same UTC value that was stored.
    """
    return timezone.localtime(d).strftime("%Y-%m-%dT%H:%M")


def make_doctor(username="doc", specialty=None):
    user = User.objects.create_user(
        username, password="testpass123",
        first_name="Sarah", last_name="Mitchell",
    )
    return DoctorProfile.objects.create(user=user, specialty=specialty)


def make_patient(username="pat"):
    user = User.objects.create_user(
        username, password="testpass123",
        first_name="John", last_name="Doe",
    )
    return PatientProfile.objects.create(user=user)


def make_availability(doctor, start_hour=9, end_hour=17, day_offset=1):
    """Create an availability block in the project's local timezone."""
    start = tomorrow_at(start_hour)
    end   = tomorrow_at(end_hour)
    if day_offset != 1:
        start = start + timedelta(days=day_offset - 1)
        end   = end   + timedelta(days=day_offset - 1)
    return Availability.objects.create(doctor=doctor, start=start, end=end)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

class AuthenticationTests(TestCase):
    def test_login_page_loads(self):
        resp = self.client.get(reverse("accounts:login"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Login")

    def test_unauthenticated_redirected_from_dashboard(self):
        resp = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)

    def test_unauthenticated_redirected_from_my_appointments(self):
        resp = self.client.get(reverse("bookings:my_appointments"))
        self.assertRedirects(resp, "/accounts/login/?next=/my-appointments/")

    def test_unauthenticated_redirected_from_availability(self):
        resp = self.client.get(reverse("bookings:availability_list"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)


# ---------------------------------------------------------------------------
# Doctor views
# ---------------------------------------------------------------------------

class DoctorViewTests(TestCase):
    def setUp(self):
        specialty = Specialty.objects.create(name="Cardiology")
        self.doctor = make_doctor("drsmith", specialty=specialty)
        make_availability(self.doctor)
        self.client.login(username="drsmith", password="testpass123")

    def test_dashboard_loads(self):
        resp = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dashboard")

    def test_availability_list_loads(self):
        resp = self.client.get(reverse("bookings:availability_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Availability")

    def test_doctor_appointments_loads(self):
        patient = make_patient("pat_dv")
        Appointment.objects.create(
            patient=patient, doctor=self.doctor,
            start=tomorrow_at(10), end=tomorrow_at(11), status="PENDING",
        )
        resp = self.client.get(reverse("bookings:doctor_appointments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Appointments")

    def test_status_filter_tab(self):
        resp = self.client.get(
            reverse("bookings:doctor_appointments") + "?status=PENDING"
        )
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Patient views
# ---------------------------------------------------------------------------

class PatientViewTests(TestCase):
    def setUp(self):
        self.specialty = Specialty.objects.create(name="General Practice")
        self.doctor = make_doctor("docpv", specialty=self.specialty)
        make_availability(self.doctor)
        self.patient = make_patient("patpv")
        self.client.login(username="patpv", password="testpass123")

    def test_dashboard_loads(self):
        resp = self.client.get(reverse("bookings:dashboard"))
        self.assertEqual(resp.status_code, 200)

    def test_doctor_list_loads(self):
        resp = self.client.get(reverse("bookings:doctor_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Find a Doctor")

    def test_doctor_list_search(self):
        resp = self.client.get(reverse("bookings:doctor_list") + "?q=General")
        self.assertEqual(resp.status_code, 200)

    def test_doctor_detail_loads(self):
        resp = self.client.get(reverse("bookings:doctor_detail", args=[self.doctor.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.doctor.user.get_full_name())

    def test_my_appointments_loads(self):
        resp = self.client.get(reverse("bookings:my_appointments"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Appointments")

    def test_my_appointments_status_filter(self):
        Appointment.objects.create(
            patient=self.patient, doctor=self.doctor,
            start=tomorrow_at(10), end=tomorrow_at(11), status="CONFIRMED",
        )
        resp = self.client.get(
            reverse("bookings:my_appointments") + "?status=CONFIRMED"
        )
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# AppointmentForm validation
# ---------------------------------------------------------------------------

class AppointmentFormTests(TestCase):
    def setUp(self):
        specialty = Specialty.objects.create(name="Cardiology")
        self.doctor = make_doctor("docform", specialty=specialty)
        self.avail = make_availability(self.doctor, start_hour=9, end_hour=17)

    def _form(self, start, end, reason="Check-up"):
        return AppointmentForm(doctor=self.doctor, data={
            "start": fmt(start), "end": fmt(end), "reason": reason,
        })

    def test_valid_booking_within_availability(self):
        form = self._form(tomorrow_at(10), tomorrow_at(11))
        self.assertTrue(form.is_valid(), form.errors)

    def test_booking_outside_availability_fails(self):
        form = self._form(tomorrow_at(6), tomorrow_at(7))  # before 9am open
        self.assertFalse(form.is_valid())

    def test_booking_in_past_fails(self):
        past = timezone.now() - timedelta(hours=2)
        form = self._form(past, past + timedelta(hours=1))
        self.assertFalse(form.is_valid())

    def test_end_before_start_fails(self):
        form = self._form(tomorrow_at(11), tomorrow_at(10))
        self.assertFalse(form.is_valid())

    def test_overlapping_confirmed_appointment_fails(self):
        patient = make_patient("pat_ovlp")
        Appointment.objects.create(
            doctor=self.doctor, patient=patient,
            start=tomorrow_at(10), end=tomorrow_at(11), status="CONFIRMED",
        )
        # Overlaps 10-11 window
        form = self._form(tomorrow_at(10, 30), tomorrow_at(11, 30))
        self.assertFalse(form.is_valid())

    def test_cancelled_appointment_does_not_block_slot(self):
        patient = make_patient("pat_canc")
        Appointment.objects.create(
            doctor=self.doctor, patient=patient,
            start=tomorrow_at(10), end=tomorrow_at(11), status="CANCELLED",
        )
        # Same slot should now be bookable
        form = self._form(tomorrow_at(10), tomorrow_at(11))
        self.assertTrue(form.is_valid(), form.errors)

    def test_adjacent_appointment_does_not_overlap(self):
        patient = make_patient("pat_adj")
        Appointment.objects.create(
            doctor=self.doctor, patient=patient,
            start=tomorrow_at(10), end=tomorrow_at(11), status="CONFIRMED",
        )
        # Book immediately after — should not overlap
        form = self._form(tomorrow_at(11), tomorrow_at(12))
        self.assertTrue(form.is_valid(), form.errors)


# ---------------------------------------------------------------------------
# RescheduleForm validation
# ---------------------------------------------------------------------------

class RescheduleFormTests(TestCase):
    def setUp(self):
        self.doctor  = make_doctor("doc_rs")
        self.patient = make_patient("pat_rs")
        self.avail   = make_availability(self.doctor, start_hour=9, end_hour=17)
        self.appt = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient,
            start=tomorrow_at(10), end=tomorrow_at(11), status="CONFIRMED",
        )

    def _form(self, start, end):
        return RescheduleForm(
            data={"start": fmt(start), "end": fmt(end), "reason": ""},
            instance=self.appt,
        )

    def test_reschedule_to_valid_slot(self):
        form = self._form(tomorrow_at(14), tomorrow_at(15))
        self.assertTrue(form.is_valid(), form.errors)

    def test_reschedule_to_same_time_does_not_self_conflict(self):
        # Rescheduling to the exact same slot must not flag its own overlap.
        form = self._form(self.appt.start, self.appt.end)
        self.assertTrue(form.is_valid(), form.errors)

    def test_reschedule_outside_availability_fails(self):
        form = self._form(tomorrow_at(6), tomorrow_at(7))
        self.assertFalse(form.is_valid())

    def test_reschedule_in_past_fails(self):
        past = timezone.now() - timedelta(hours=2)
        form = self._form(past, past + timedelta(hours=1))
        self.assertFalse(form.is_valid())


# ---------------------------------------------------------------------------
# Appointment lifecycle
# ---------------------------------------------------------------------------

class AppointmentLifecycleTests(TestCase):
    def setUp(self):
        self.doctor  = make_doctor("doc_life")
        self.patient = make_patient("pat_life")
        self.appt = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient,
            start=tomorrow_at(10), end=tomorrow_at(11), status="PENDING",
        )

    def test_doctor_confirms_pending(self):
        self.client.login(username="doc_life", password="testpass123")
        self.client.post(reverse("bookings:confirm_appointment", args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "CONFIRMED")

    def test_doctor_declines_pending(self):
        self.client.login(username="doc_life", password="testpass123")
        self.client.post(reverse("bookings:decline_appointment", args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "CANCELLED")

    def test_confirming_non_pending_is_idempotent(self):
        self.appt.status = "CONFIRMED"
        self.appt.save()
        self.client.login(username="doc_life", password="testpass123")
        self.client.post(reverse("bookings:confirm_appointment", args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "CONFIRMED")

    def test_patient_cancels_own_appointment(self):
        self.client.login(username="pat_life", password="testpass123")
        resp = self.client.post(reverse("bookings:appointment_cancel", args=[self.appt.pk]))
        self.appt.refresh_from_db()
        self.assertEqual(self.appt.status, "CANCELLED")
        self.assertEqual(resp.status_code, 302)

    def test_patient_cannot_cancel_another_patients_appointment(self):
        other = make_patient("other_life")
        other_appt = Appointment.objects.create(
            doctor=self.doctor, patient=other,
            start=tomorrow_at(13), end=tomorrow_at(14), status="PENDING",
        )
        self.client.login(username="pat_life", password="testpass123")
        resp = self.client.post(reverse("bookings:appointment_cancel", args=[other_appt.pk]))
        self.assertEqual(resp.status_code, 404)
        other_appt.refresh_from_db()
        self.assertEqual(other_appt.status, "PENDING")

    def test_new_appointment_defaults_to_pending(self):
        appt = Appointment.objects.create(
            doctor=self.doctor, patient=self.patient,
            start=tomorrow_at(15), end=tomorrow_at(16),
        )
        self.assertEqual(appt.status, "PENDING")


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------

class AccessControlTests(TestCase):
    def setUp(self):
        self.doctor  = make_doctor("doc_ac")
        self.patient = make_patient("pat_ac")

    def test_patient_blocked_from_doctor_appointments(self):
        self.client.login(username="pat_ac", password="testpass123")
        resp = self.client.get(reverse("bookings:doctor_appointments"))
        self.assertRedirects(resp, reverse("bookings:dashboard"))

    def test_patient_blocked_from_availability_create(self):
        self.client.login(username="pat_ac", password="testpass123")
        resp = self.client.get(reverse("bookings:availability_create"))
        self.assertRedirects(resp, reverse("bookings:dashboard"))

    def test_doctor_blocked_from_cancel_endpoint(self):
        patient2 = make_patient("pat_for_ac")
        appt = Appointment.objects.create(
            doctor=self.doctor, patient=patient2,
            start=tomorrow_at(10), end=tomorrow_at(11),
        )
        self.client.login(username="doc_ac", password="testpass123")
        resp = self.client.get(reverse("bookings:appointment_cancel", args=[appt.pk]))
        self.assertRedirects(resp, reverse("bookings:dashboard"))

    def test_doctor_can_access_availability(self):
        self.client.login(username="doc_ac", password="testpass123")
        resp = self.client.get(reverse("bookings:availability_list"))
        self.assertEqual(resp.status_code, 200)

    def test_patient_can_access_my_appointments(self):
        self.client.login(username="pat_ac", password="testpass123")
        resp = self.client.get(reverse("bookings:my_appointments"))
        self.assertEqual(resp.status_code, 200)


# ---------------------------------------------------------------------------
# Availability model
# ---------------------------------------------------------------------------

class AvailabilityModelTests(TestCase):
    def setUp(self):
        self.doctor = make_doctor("doc_avmodel")
        self.client.login(username="doc_avmodel", password="testpass123")

    def test_end_before_start_raises_validation_error(self):
        avail = Availability(
            doctor=self.doctor,
            start=tomorrow_at(10),
            end=tomorrow_at(9),
        )
        with self.assertRaises(Exception):
            avail.full_clean()

    def test_availability_str_contains_doctor_name(self):
        avail = make_availability(self.doctor)
        self.assertIn("sarah mitchell", str(avail).lower())

    def test_doctor_can_create_availability_via_view(self):
        resp = self.client.post(reverse("bookings:availability_create"), {
            "start": fmt(tomorrow_at(9,  0)),
            "end":   fmt(tomorrow_at(17, 0)),
            "note":  "Clinic hours",
        })
        self.assertRedirects(resp, reverse("bookings:availability_list"))
        self.assertTrue(Availability.objects.filter(doctor=self.doctor).exists())

    def test_availability_end_before_start_form_invalid(self):
        resp = self.client.post(reverse("bookings:availability_create"), {
            "start": fmt(tomorrow_at(12, 0)),
            "end":   fmt(tomorrow_at(9,  0)),
            "note":  "",
        })
        self.assertEqual(resp.status_code, 200)  # stays on form
        self.assertFalse(Availability.objects.filter(doctor=self.doctor).exists())
