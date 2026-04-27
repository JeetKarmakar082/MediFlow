# MediFlow — Smart Patient Flow Management System

A Django-based hospital management system with AI-powered triage, real-time queue management, and emergency escalation — built for government hospitals in India.

---

## Features

- **AI Triage Engine** — Scores patient urgency (1–5) using Google Gemini AI, with a rule-based fallback when no API key is set
- **Smart Queue Management** — Priority queue that puts critical patients first, not just first-come-first-serve
- **Emergency Escalation** — Manual and auto-escalation for triage scores 1 & 2, reflected instantly in the queue
- **Live Queue Display Board** — WebSocket-powered TV display for waiting areas, auto-reconnects on disconnect
- **Patient Registration** — Full patient profiles with medical history, allergies, blood group
- **Medical Records** — Diagnosis, prescription, and follow-up tracking per visit
- **Doctor Management** — Doctor profiles, specializations, weekly schedules, availability toggle
- **Department Management** — Dedicated department model with queue scoped per department
- **SMS Notifications** — Twilio integration for token assignment and call alerts (mocks to console if not configured)
- **Admin Panel** — Full Django admin with search, filters, and inline editing for all models

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 4.2 + Django REST Framework |
| Real-time | Django Channels + Redis |
| AI Triage | Google Gemini 2.5 Flash (`google-genai`) |
| Database | SQLite (dev) / PostgreSQL (production) |
| Auth | Django session authentication |
| SMS | Twilio |
| Task Queue | Celery + Redis |
| Frontend | HTML + Tailwind CSS (CDN) + Vanilla JS |
| Server | Daphne (ASGI) |

---

## Project Structure

```
hospital_system/
├── apps/
│   ├── models.py          # All models — Patient, Doctor, Token, Triage, Emergency, etc.
│   ├── views.py           # All views — page views + API ViewSets
│   ├── serializers.py     # DRF serializers
│   ├── urls.py            # Single router for all API endpoints
│   ├── admin.py           # Admin registrations
│   ├── triage_engine.py   # Gemini AI + rule-based triage scorer
│   ├── tasks.py           # Celery SMS task
│   ├── consumers.py       # WebSocket consumer
│   └── routing.py         # WebSocket URL routing
├── hospital_system/
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py            # Channels ASGI config
│   └── celery.py
├── templates/
│   ├── base.html          # Shared layout with sidebar
│   ├── login.html
│   ├── dashboard.html
│   ├── patients.html
│   ├── triage.html
│   ├── assessments.html   # Triage history
│   ├── queue.html
│   ├── doctors.html
│   ├── schedules.html     # Doctor schedules
│   ├── records.html       # Medical records
│   ├── emergency.html
│   └── queue_display.html # Live TV board
├── static/
│   └── js/api.js          # CSRF-aware fetch helper
├── .env.example
├── manage.py
└── requirements.txt
```

---

## Setup

### 1. Clone and install dependencies

```bash
git clone <repo-url>
cd hospital_system
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in:

```env
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Redis
REDIS_HOST=127.0.0.1
REDIS_URL=redis://127.0.0.1:6379/0

# Google Gemini AI (free tier — get key at https://aistudio.google.com)
GEMINI_API_KEY=your-gemini-key-here

# Twilio SMS (optional)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=
```

### 3. Run migrations and seed departments

```bash
python manage.py migrate

python manage.py shell -c "
from apps.models import Department
depts = [
    ('General Medicine', 'general'),
    ('Emergency', 'emergency'),
    ('Cardiology', 'cardiology'),
    ('Orthopedics', 'orthopedics'),
    ('Pediatrics', 'pediatrics'),
    ('Neurology', 'neurology'),
    ('Gynecology', 'gynecology'),
    ('Surgery', 'surgery'),
]
for name, code in depts:
    Department.objects.get_or_create(code=code, defaults={'name': name})
print('Done')
"
```

### 4. Create superuser

```bash
python manage.py createsuperuser
```

### 5. Start Redis

```bash
# Windows (after installing Redis)
redis-server

# WSL / Linux
sudo service redis-server start
```

### 6. Start the server

```bash
# Main server (HTTP + WebSocket)
daphne hospital_system.asgi:application

# Or for development
python manage.py runserver
```

### 7. Start Celery worker (for SMS notifications)

```bash
celery -A hospital_system worker -l info
```

---

## Pages

| URL | Page |
|---|---|
| `/` | Dashboard — live stats, triage breakdown, quick actions |
| `/patients/` | Patient list, search, register |
| `/triage/` | AI triage assessment form |
| `/assessments/` | Triage history with filters |
| `/queue/` | Queue management — call next, issue token |
| `/doctors/` | Doctor profiles and availability |
| `/schedules/` | Doctor weekly schedules |
| `/records/` | Medical records |
| `/emergency/` | Emergency escalations |
| `/display/<dept>/` | Live TV queue board (public) |
| `/admin/` | Django admin panel |

---

## API Endpoints

All endpoints are under `/api/` and require session authentication.

```
GET/POST   /api/patients/
GET        /api/patients/{id}/history/
GET/POST   /api/doctors/
PATCH      /api/doctors/{id}/toggle-availability/
GET        /api/doctors/availability/
GET/POST   /api/departments/
POST       /api/triage/assess/
GET        /api/triage/
GET/POST   /api/queue/
POST       /api/queue/call-next/
GET        /api/queue/status/
PATCH      /api/queue/{id}/complete/
GET/POST   /api/records/
POST       /api/emergency/escalate/
PATCH      /api/emergency/{id}/resolve/
GET        /api/dashboard/stats/

WS         /ws/queue/{department}/
```

---

## Triage Scoring

| Score | Level | Action |
|---|---|---|
| 1 | Critical — Immediate | Resuscitation bay, alert doctor NOW |
| 2 | Emergency | Seen within 15 minutes |
| 3 | Urgent | Seen within 30 minutes |
| 4 | Semi-Urgent | Seen within 1 hour |
| 5 | Non-Urgent | Routine queue, within 2 hours |

Scores 1 and 2 automatically:
- Create a queue token in the Emergency department
- Create an emergency escalation record
- Appear in queue management with a CRITICAL/EMERGENCY badge

---

## AI Triage Engine

The engine in `apps/triage_engine.py` works in two modes:

**Gemini AI mode** (when `GEMINI_API_KEY` is set)
- Uses `gemini-2.5-flash` model
- Considers both vitals and symptom description
- Returns score, clinical reasoning, and recommended action
- Falls back to rule-based if Gemini fails or quota is exceeded

**Rule-based mode** (fallback)
- Scores based on vitals thresholds (SpO2, pulse, BP, temperature, pain)
- No API key required
- Deterministic and always available

---

## Default Credentials

After running `createsuperuser`:

```
URL:      http://127.0.0.1:8000/login/
Admin:    http://127.0.0.1:8000/admin/
```

---

## Production Notes

- Switch `DATABASES` in `settings.py` to PostgreSQL
- Set `DEBUG=False` and configure `ALLOWED_HOSTS`
- Run `python manage.py collectstatic`
- Use Nginx as a reverse proxy in front of Daphne
- Store `SECRET_KEY` and all API keys securely — never commit `.env`
