"""
Bookings DRF serializers.

  SpecialtySerializer     — read-only specialty info
  DoctorSerializer        — read-only doctor info with nested specialty
  AvailabilitySerializer  — doctor's availability blocks (CRUD)
  AppointmentSerializer   — patient appointments (CRUD)
"""

from rest_framework import serializers

from accounts.models import DoctorProfile, Specialty

from .models import Appointment, Availability


class SpecialtySerializer(serializers.ModelSerializer):
    class Meta:
        model = Specialty
        fields = ["id", "name"]


class DoctorSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    specialty = SpecialtySerializer(read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ["id", "full_name", "specialty", "bio"]

    def get_full_name(self, obj) -> str:
        return obj.full_name


class AvailabilitySerializer(serializers.ModelSerializer):
    # doctor is set by the view; read-only here so clients can't spoof it.
    doctor = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Availability
        fields = ["id", "doctor", "start", "end", "note"]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=DoctorProfile.objects.all())
    # patient is always the requesting user; never accepted from the client.
    patient = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Appointment
        fields = ["id", "patient", "doctor", "start", "end", "status", "reason"]
        # Clients cannot change status directly; that happens via dedicated endpoints.
        read_only_fields = ["status"]

    def validate(self, attrs):
        """
        Cross-field validation: availability and overlap checks.

        These mirror the rules in AppointmentForm so the API path is
        equally strict.
        """
        start = attrs.get("start")
        end = attrs.get("end")
        doctor = attrs.get("doctor")

        if start and end and doctor:
            # Must fall inside one of the doctor's availability blocks.
            available = Availability.objects.filter(
                doctor=doctor,
                start__lte=start,
                end__gte=end,
            ).exists()
            if not available:
                raise serializers.ValidationError(
                    "The selected time is outside this doctor's availability."
                )

            # Must not overlap an existing active appointment.
            current_pk = self.instance.pk if self.instance else None
            overlap = (
                Appointment.objects.filter(
                    doctor=doctor,
                    status__in=["PENDING", "CONFIRMED"],
                    start__lt=end,
                    end__gt=start,
                )
                .exclude(pk=current_pk)
                .exists()
            )
            if overlap:
                raise serializers.ValidationError(
                    "This time slot overlaps with an existing appointment."
                )

        return super().validate(attrs)

    def create(self, validated_data):
        user = self.context["request"].user
        patient = getattr(user, "patientprofile", None)
        if not patient:
            raise serializers.ValidationError("Only patients can create appointments.")
        appt = Appointment(patient=patient, **validated_data)
        appt.full_clean()
        appt.save()
        return appt

    def update(self, instance, validated_data):
        user = self.context["request"].user
        patient = getattr(user, "patientprofile", None)
        if instance.patient != patient:
            raise serializers.ValidationError("You can only update your own appointments.")
        for key, value in validated_data.items():
            setattr(instance, key, value)
        instance.full_clean()
        instance.save()
        return instance
