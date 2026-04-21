"""
Root URL configuration.

  /           → bookings app  (dashboard, doctors, appointments)
  /accounts/  → accounts app  (login, logout, register, profile)
  /api/       → bookings REST API
  /admin/     → Django admin
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/", include("bookings.api_urls")),
    path("", include("bookings.urls")),
]
