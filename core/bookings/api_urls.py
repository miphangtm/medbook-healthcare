from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import SpecialtyViewSet, DoctorViewSet, AvailabilityViewSet, AppointmentViewSet

router = DefaultRouter()
router.register(r'specialties', SpecialtyViewSet, basename='specialty')
router.register(r'doctors', DoctorViewSet, basename='doctor')
router.register(r'availability', AvailabilityViewSet, basename='availability')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
]
