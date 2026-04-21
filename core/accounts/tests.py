"""
Accounts test suite.

Covers:
  - Registration (patient + doctor, password mismatch, email uniqueness)
  - Authenticated-user redirect away from register/login
  - Profile update (name, phone)
  - Password change page access
"""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import DoctorProfile, PatientProfile


class RegistrationTests(TestCase):
    def _post(self, **kwargs):
        defaults = {
            "username": "newuser",
            "first_name": "New",
            "last_name": "User",
            "email": "new@example.com",
            "password": "testpass123",
            "confirm_password": "testpass123",
            "role": "patient",
        }
        defaults.update(kwargs)
        return self.client.post(reverse("accounts:register"), defaults)

    def test_patient_registration_creates_profile(self):
        resp = self._post(username="pat1", role="patient")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(PatientProfile.objects.filter(user__username="pat1").exists())

    def test_doctor_registration_creates_profile(self):
        resp = self._post(username="doc1", email="doc@example.com", role="doctor")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(DoctorProfile.objects.filter(user__username="doc1").exists())

    def test_password_mismatch_fails(self):
        resp = self._post(username="mismatch", confirm_password="wrongpass")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="mismatch").exists())

    def test_duplicate_email_fails(self):
        User.objects.create_user("existing", email="taken@example.com", password="pass")
        resp = self._post(username="new2", email="taken@example.com")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username="new2").exists())

    def test_duplicate_username_fails(self):
        User.objects.create_user("taken", password="pass")
        resp = self._post(username="taken", email="unique@example.com")
        self.assertEqual(resp.status_code, 200)

    def test_authenticated_user_redirected_from_register(self):
        User.objects.create_user("loggedin", password="testpass123")
        PatientProfile.objects.create(
            user=User.objects.get(username="loggedin")
        )
        self.client.login(username="loggedin", password="testpass123")
        resp = self.client.get(reverse("accounts:register"))
        self.assertRedirects(resp, reverse("bookings:dashboard"))


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "profileuser", password="testpass123",
            first_name="Old", last_name="Name",
        )
        self.patient = PatientProfile.objects.create(user=self.user)
        self.client.login(username="profileuser", password="testpass123")

    def test_profile_page_loads(self):
        resp = self.client.get(reverse("accounts:profile"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "My Profile")

    def test_profile_update_saves_name(self):
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Updated",
            "last_name": "Name",
            "email": "updated@example.com",
            "phone": "0400000000",
        })
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_profile_update_saves_phone(self):
        self.client.post(reverse("accounts:profile"), {
            "first_name": "Old",
            "last_name": "Name",
            "email": "u@example.com",
            "phone": "0411111111",
        })
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.phone, "0411111111")

    def test_password_change_page_loads(self):
        resp = self.client.get(reverse("accounts:password_change"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Change Password")

    def test_unauthenticated_cannot_access_profile(self):
        self.client.logout()
        resp = self.client.get(reverse("accounts:profile"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.url)
