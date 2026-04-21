"""URL patterns for the bookings app."""

from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    # General
    path("", views.dashboard, name="dashboard"),

    # Doctor discovery
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctor/<int:doctor_id>/", views.doctor_detail, name="doctor_detail"),

    # Patient appointment flow
    path("book/<int:doctor_id>/", views.book_appointment, name="book_appointment"),
    path("my-appointments/", views.my_appointments, name="my_appointments"),
    path("appointment/<int:pk>/cancel/", views.appointment_cancel, name="appointment_cancel"),
    path("appointment/<int:pk>/reschedule/", views.appointment_reschedule, name="appointment_reschedule"),

    # Doctor appointment management
    path("doctor/appointments/", views.doctor_appointments, name="doctor_appointments"),
    path("appointment/<int:pk>/confirm/", views.confirm_appointment, name="confirm_appointment"),
    path("appointment/<int:pk>/decline/", views.decline_appointment, name="decline_appointment"),

    # Doctor availability management
    path("availability/", views.availability_list, name="availability_list"),
    path("availability/new/", views.availability_create, name="availability_create"),
    path("availability/<int:pk>/edit/", views.availability_edit, name="availability_edit"),
    path("availability/<int:pk>/delete/", views.availability_delete, name="availability_delete"),
]
