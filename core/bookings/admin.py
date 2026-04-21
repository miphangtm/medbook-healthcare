"""Admin registration for the bookings app."""

from django.contrib import admin

from .models import Appointment, Availability


@admin.register(Availability)
class AvailabilityAdmin(admin.ModelAdmin):
    list_display = ("doctor", "start", "end", "note")
    list_filter = ("doctor",)
    date_hierarchy = "start"
    search_fields = ("doctor__user__username", "doctor__user__last_name", "note")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "start", "end", "status", "reason")
    list_filter = ("status", "doctor")
    date_hierarchy = "start"
    search_fields = (
        "patient__user__username",
        "patient__user__last_name",
        "doctor__user__username",
        "doctor__user__last_name",
        "reason",
    )
    # Prevent accidental bulk-edits of status from the list view.
    readonly_fields = ("patient", "doctor")
