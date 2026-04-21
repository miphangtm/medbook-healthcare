"""
Custom context processors.

user_role — adds is_patient and is_doctor booleans to every template context
so that the base navbar can conditionally show role-specific links without
directly accessing reverse OneToOne relations (which raise AttributeError in
Django 5.x when the related object doesn't exist).
"""


def user_role(request):
    if not request.user.is_authenticated:
        return {"is_patient": False, "is_doctor": False}
    return {
        "is_patient": hasattr(request.user, "patientprofile"),
        "is_doctor": hasattr(request.user, "doctorprofile"),
    }
