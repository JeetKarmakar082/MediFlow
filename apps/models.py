from django.db import models


# ─── Department ───────────────────────────────────────────────────────────────

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=30, unique=True, help_text='Short code used in queue e.g. general, cardiology')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


# ─── Doctor ───────────────────────────────────────────────────────────────────

class Doctor(models.Model):
    SPECIALIZATION_CHOICES = [
        ('general', 'General Medicine'), ('emergency', 'Emergency'),
        ('cardiology', 'Cardiology'), ('orthopedics', 'Orthopedics'),
        ('pediatrics', 'Pediatrics'), ('neurology', 'Neurology'),
        ('gynecology', 'Gynecology'), ('surgery', 'Surgery'), ('other', 'Other'),
    ]
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=50, choices=SPECIALIZATION_CHOICES)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='doctors'
    )
    phone = models.CharField(max_length=15)
    registration_number = models.CharField(max_length=50, unique=True)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Dr. {self.name} ({self.specialization})"


class DoctorSchedule(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='schedules')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    max_patients = models.IntegerField(default=20)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('doctor', 'day_of_week')

    def __str__(self):
        return f"{self.doctor.name} - {self.get_day_of_week_display()}"


# ─── Patient ──────────────────────────────────────────────────────────────────

class Patient(models.Model):
    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    BLOOD_GROUP_CHOICES = [
        ('A+', 'A+'), ('A-', 'A-'), ('B+', 'B+'), ('B-', 'B-'),
        ('AB+', 'AB+'), ('AB-', 'AB-'), ('O+', 'O+'), ('O-', 'O-'),
    ]
    name = models.CharField(max_length=100)
    age = models.IntegerField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    phone = models.CharField(max_length=15, unique=True)
    email = models.EmailField(blank=True)
    blood_group = models.CharField(max_length=5, choices=BLOOD_GROUP_CHOICES, blank=True)
    allergies = models.TextField(blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.phone})"


# ─── Medical Record ───────────────────────────────────────────────────────────

class MedicalRecord(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medical_records')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, related_name='medical_records')
    diagnosis = models.TextField()
    prescription = models.TextField()
    notes = models.TextField(blank=True)
    visit_date = models.DateTimeField(auto_now_add=True)
    hospital = models.CharField(max_length=100, default='General Hospital')
    follow_up_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-visit_date']

    def __str__(self):
        return f"{self.patient.name} - {self.visit_date.date()}"


# ─── Triage ───────────────────────────────────────────────────────────────────

class TriageAssessment(models.Model):
    SCORE_CHOICES = [
        (1, 'Immediate - Life Threatening'), (2, 'Emergency - Urgent'),
        (3, 'Urgent - Serious'), (4, 'Semi-Urgent'), (5, 'Non-Urgent - Minor'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='triage_assessments')
    symptoms = models.TextField()
    bp_systolic = models.IntegerField()
    bp_diastolic = models.IntegerField()
    pulse = models.IntegerField()
    temperature = models.FloatField()
    oxygen_level = models.FloatField()
    pain_scale = models.IntegerField()
    ai_score = models.IntegerField(choices=SCORE_CHOICES, null=True, blank=True)
    ai_reasoning = models.TextField(blank=True)
    ai_action = models.TextField(blank=True)
    ai_source = models.CharField(
        max_length=20, default='rule_based',
        choices=[('gemini', 'Google Gemini'), ('rule_based', 'Rule-Based Engine')],
        help_text='Which engine produced this score'
    )
    assessed_at = models.DateTimeField(auto_now_add=True)
    assessed_by = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-assessed_at']

    def __str__(self):
        return f"Triage: {self.patient.name} — Score {self.ai_score}"

    @property
    def bp(self):
        return f"{self.bp_systolic}/{self.bp_diastolic}"


# ─── Queue / Token ────────────────────────────────────────────────────────────

class Token(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting'), ('called', 'Called'),
        ('in_progress', 'In Progress'), ('done', 'Done'),
        ('skipped', 'Skipped'), ('cancelled', 'Cancelled'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='tokens')
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True, blank=True, related_name='tokens')
    token_number = models.IntegerField()
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='tokens'
    )
    triage_score = models.IntegerField(default=5)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['triage_score', 'created_at']

    def __str__(self):
        return f"Token #{self.token_number} — {self.patient.name} ({self.department})"

    @classmethod
    def generate_token_number(cls, department):
        from django.utils import timezone
        from django.db import transaction
        today = timezone.now().date()
        with transaction.atomic():
            last = cls.objects.select_for_update().filter(
                department=department, created_at__date=today
            ).order_by('-token_number').first()
            return (last.token_number + 1) if last else 1


# ─── Emergency ────────────────────────────────────────────────────────────────

class EmergencyEscalation(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'), ('resolved', 'Resolved'), ('transferred', 'Transferred'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='escalations')
    token = models.ForeignKey(Token, on_delete=models.SET_NULL, null=True, blank=True)
    triage_assessment = models.ForeignKey(
        'TriageAssessment', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='escalations', help_text='Auto-linked when created from triage'
    )
    reason = models.TextField()
    escalated_by = models.CharField(max_length=100)
    auto_escalated = models.BooleanField(default=False, help_text='True if created automatically from triage score')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    escalated_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-escalated_at']

    def __str__(self):
        return f"Emergency: {self.patient.name} [{self.status}]"


# ─── Notifications ────────────────────────────────────────────────────────────

class Notification(models.Model):
    TYPE_CHOICES = [
        ('token_assigned', 'Token Assigned'), ('token_called', 'Token Called'),
        ('emergency', 'Emergency Alert'), ('general', 'General'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'), ('sent', 'Sent'), ('failed', 'Failed'),
    ]
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    message = models.TextField()
    phone = models.CharField(max_length=15)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type} → {self.phone} [{self.status}]"



from django.db.models.signals import post_migrate
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.conf import settings

@receiver(post_migrate)
def create_admin_user(sender, **kwargs):
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin123@gmail.com', 'admin123')
        print("Superuser created successfully!")
