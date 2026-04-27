from django.contrib import admin
from .models import (
    Department, Doctor, DoctorSchedule, Patient, MedicalRecord,
    TriageAssessment, Token, EmergencyEscalation, Notification
)


# ─── Department ───────────────────────────────────────────────────────────────

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'code')
    list_editable = ('is_active',)
    ordering = ('name',)


# ─── Doctor ───────────────────────────────────────────────────────────────────

class DoctorScheduleInline(admin.TabularInline):
    model = DoctorSchedule
    extra = 1
    fields = ('day_of_week', 'start_time', 'end_time', 'max_patients', 'is_active')


@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    list_display = ('name', 'specialization', 'department', 'phone', 'is_available', 'created_at')
    list_filter = ('specialization', 'department', 'is_available')
    search_fields = ('name', 'phone', 'registration_number')
    list_editable = ('is_available',)
    ordering = ('name',)
    inlines = [DoctorScheduleInline]


@admin.register(DoctorSchedule)
class DoctorScheduleAdmin(admin.ModelAdmin):
    list_display = ('doctor', 'day_of_week', 'start_time', 'end_time', 'max_patients', 'is_active')
    list_filter = ('day_of_week', 'is_active')
    search_fields = ('doctor__name',)


# ─── Patient ──────────────────────────────────────────────────────────────────

class MedicalRecordInline(admin.TabularInline):
    model = MedicalRecord
    extra = 0
    readonly_fields = ('visit_date',)
    fields = ('doctor', 'diagnosis', 'prescription', 'follow_up_date', 'visit_date')
    show_change_link = True


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'age', 'gender', 'phone', 'blood_group', 'created_at')
    list_filter = ('gender', 'blood_group', 'created_at')
    search_fields = ('name', 'phone', 'email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    list_per_page = 25
    inlines = [MedicalRecordInline]
    fieldsets = (
        ('Personal Info', {'fields': ('name', 'age', 'gender', 'blood_group')}),
        ('Contact',       {'fields': ('phone', 'email', 'address', 'emergency_contact')}),
        ('Medical',       {'fields': ('allergies',)}),
        ('Timestamps',    {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = ('patient', 'doctor', 'hospital', 'visit_date', 'follow_up_date')
    list_filter = ('hospital', 'visit_date')
    search_fields = ('patient__name', 'doctor__name', 'diagnosis')
    readonly_fields = ('visit_date',)
    ordering = ('-visit_date',)


# ─── Triage ───────────────────────────────────────────────────────────────────

@admin.register(TriageAssessment)
class TriageAssessmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'ai_score', 'pulse', 'oxygen_level', 'temperature', 'pain_scale', 'assessed_at')
    list_filter = ('ai_score', 'assessed_at')
    search_fields = ('patient__name', 'symptoms')
    readonly_fields = ('assessed_at', 'ai_score', 'ai_reasoning', 'ai_action')
    ordering = ('-assessed_at',)
    fieldsets = (
        ('Patient',   {'fields': ('patient', 'symptoms', 'assessed_by')}),
        ('Vitals',    {'fields': ('bp_systolic', 'bp_diastolic', 'pulse', 'temperature', 'oxygen_level', 'pain_scale')}),
        ('AI Result', {'fields': ('ai_score', 'ai_reasoning', 'ai_action')}),
        ('Meta',      {'fields': ('assessed_at',), 'classes': ('collapse',)}),
    )


# ─── Queue / Token ────────────────────────────────────────────────────────────

@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('token_number', 'patient', 'department', 'triage_score', 'status', 'created_at', 'called_at')
    list_filter = ('status', 'department', 'triage_score', 'created_at')
    search_fields = ('patient__name', 'patient__phone', 'department')
    readonly_fields = ('token_number', 'created_at', 'called_at', 'completed_at')
    ordering = ('triage_score', 'created_at')
    list_per_page = 30
    list_editable = ('status',)


# ─── Emergency ────────────────────────────────────────────────────────────────

@admin.register(EmergencyEscalation)
class EmergencyEscalationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'escalated_by', 'auto_escalated', 'status', 'escalated_at', 'resolved_at')
    list_filter = ('status', 'auto_escalated', 'escalated_at')
    search_fields = ('patient__name', 'escalated_by', 'reason')
    readonly_fields = ('escalated_at', 'resolved_at', 'auto_escalated')
    ordering = ('-escalated_at',)
    list_editable = ('status',)


# ─── Notifications ────────────────────────────────────────────────────────────

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('patient', 'notification_type', 'phone', 'status', 'created_at', 'sent_at')
    list_filter = ('status', 'notification_type', 'created_at')
    search_fields = ('patient__name', 'phone', 'message')
    readonly_fields = ('created_at', 'sent_at')
    ordering = ('-created_at',)
