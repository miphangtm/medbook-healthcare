# MedBook — Healthcare Appointment Booking System

A full-stack Django web application that connects patients with doctors for appointment scheduling. Patients can browse doctors, book appointments, and manage their schedule. Doctors can set their availability, review incoming requests, and confirm or decline bookings.

---

## Features

### Patient
- Register and log in as a patient
- Browse and search the doctor directory by name or specialty
- Book appointments within a doctor's available windows
- View, filter, and cancel upcoming appointments

### Doctor
- Register and log in as a doctor
- Set weekly availability blocks
- Review incoming appointment requests (Pending → Confirmed / Cancelled)
- View full appointment history with status filter tabs

### General
- Role-based access control — patients and doctors each see only their own views
- Appointment lifecycle: **Pending → Confirmed** (doctor accepts) or **Cancelled** (doctor declines / patient cancels)
- Overlap and past-date validation on all booking and rescheduling forms
- Paginated list views throughout
- REST API for appointments and availability (session-authenticated)
- Custom 404 and 500 error pages
- Responsive Bootstrap 5 UI

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12+ |
| Framework | Django 5.2 |
| REST API | Django REST Framework 3.16 |
| Database | SQLite3 (dev) |
| Frontend | Bootstrap 5.3, Bootstrap Icons |
| Timezone | Australia/Melbourne |

---

## Project Structure

```
medbook-healthcare/
├── core/                        # Django project root
│   ├── core/                    # Settings, URLs, WSGI
│   ├── accounts/                # Auth, registration, profiles
│   │   ├── models.py            # PatientProfile, DoctorProfile, Specialty
│   │   ├── views.py             # register, login, profile, password change
│   │   ├── forms.py             # RegisterForm, ProfileUpdateForm
│   │   ├── decorators.py        # @patient_required, @doctor_required
│   │   ├── context_processors.py# is_patient / is_doctor for every template
│   │   └── templates/accounts/
│   ├── bookings/                # Core booking logic
│   │   ├── models.py            # Appointment, Availability
│   │   ├── views.py             # All booking views (paginated)
│   │   ├── forms.py             # AppointmentForm, RescheduleForm
│   │   ├── api_views.py         # DRF ViewSets
│   │   ├── serializers.py       # With availability + overlap validation
│   │   └── templates/bookings/
│   └── templates/               # Project-level 404.html, 500.html
└── requirements.txt
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/miphangtm/medbook-healthcare.git
cd medbook-healthcare
```

### 2. Create and activate a virtual environment

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Apply migrations

```bash
cd core
python manage.py migrate
```

### 5. Create a superuser (optional — for Django Admin access)

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser.

---

## Environment Variables

For production deployments, set the following environment variables instead of relying on the insecure defaults:

| Variable | Description | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Django secret key | Insecure dev key |
| `DJANGO_DEBUG` | Enable debug mode (`true`/`false`) | `true` |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated allowed hosts | `*` (when DEBUG=true) |

---

## Running Tests

```bash
cd core
python manage.py test
```

The test suite covers:
- Authentication and redirects
- Doctor and patient views
- Appointment form validation (availability, overlap, past dates)
- Reschedule form validation (including self-exclusion)
- Appointment lifecycle (confirm, decline, cancel)
- Role-based access control
- Availability model validation

---

## REST API

The API is session-authenticated and available at `/api/`.

| Endpoint | Methods | Description |
|---|---|---|
| `/api/appointments/` | GET, POST | List or create appointments |
| `/api/appointments/{id}/` | GET, PUT, PATCH, DELETE | Retrieve or update an appointment |
| `/api/availability/` | GET, POST | List or create availability blocks |
| `/api/availability/{id}/` | GET, PUT, PATCH, DELETE | Retrieve or update availability |

---

## Key URLs

| URL | Description |
|---|---|
| `/` | Dashboard (redirects to login if unauthenticated) |
| `/accounts/register/` | Register as patient or doctor |
| `/accounts/login/` | Login |
| `/accounts/profile/` | View and edit profile |
| `/doctors/` | Browse doctor directory |
| `/doctors/{id}/` | Doctor detail and booking form |
| `/my-appointments/` | Patient appointment list |
| `/doctor/appointments/` | Doctor appointment list |
| `/availability/` | Doctor availability management |
| `/admin/` | Django admin |

---

## Screenshots

> Register → browse doctors → book an appointment → doctor confirms.

![Dashboard](https://via.placeholder.com/800x400?text=Dashboard+Screenshot)

---

## License

MIT
