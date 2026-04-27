from rest_framework import serializers
from .models import (
    Department, Doctor, DoctorSchedule, Patient, MedicalRecord,
    TriageAssessment, Token, EmergencyEscalation, Notification
)


# ─── Department ───────────────────────────────────────────────────────────────

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = '__all__'
        read_only_fields = ('created_at',)


# ─── Doctor ───────────────────────────────────────────────────────────────────

class DoctorScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorSchedule
        fields = '__all__'


class DoctorSerializer(serializers.ModelSerializer):
    schedules = DoctorScheduleSerializer(many=True, read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = Doctor
        fields = '__all__'
        read_only_fields = ('created_at',)


# ─── Patient ──────────────────────────────────────────────────────────────────

class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')


class MedicalRecordSerializer(serializers.ModelSerializer):
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    patient_phone = serializers.CharField(source='patient.phone', read_only=True)

    class Meta:
        model = MedicalRecord
        fields = '__all__'
        read_only_fields = ('visit_date',)


# ─── Triage ───────────────────────────────────────────────────────────────────

class TriageAssessmentSerializer(serializers.ModelSerializer):
    bp = serializers.CharField(read_only=True)
    score_label = serializers.CharField(source='get_ai_score_display', read_only=True)
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    patient_phone = serializers.CharField(source='patient.phone', read_only=True)

    class Meta:
        model = TriageAssessment
        fields = '__all__'
        read_only_fields = ('ai_score', 'ai_reasoning', 'ai_action', 'assessed_at')


class TriageInputSerializer(serializers.Serializer):
    patient_id = serializers.IntegerField()
    symptoms = serializers.CharField()
    bp_systolic = serializers.IntegerField(min_value=40, max_value=300)
    bp_diastolic = serializers.IntegerField(min_value=20, max_value=200)
    pulse = serializers.IntegerField(min_value=20, max_value=300)
    temperature = serializers.FloatField(min_value=30.0, max_value=45.0)
    oxygen_level = serializers.FloatField(min_value=50.0, max_value=100.0)
    pain_scale = serializers.IntegerField(min_value=0, max_value=10)
    assessed_by = serializers.CharField(required=False, default='')


# ─── Queue ────────────────────────────────────────────────────────────────────

class TokenSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    patient_phone = serializers.CharField(source='patient.phone', read_only=True)
    doctor_name = serializers.CharField(source='doctor.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    department_code = serializers.CharField(source='department.code', read_only=True)
    triage_label = serializers.SerializerMethodField()

    class Meta:
        model = Token
        fields = '__all__'
        read_only_fields = ('token_number', 'created_at', 'called_at', 'completed_at')

    def get_triage_label(self, obj):
        return {1: 'Critical', 2: 'Emergency', 3: 'Urgent', 4: 'Semi-Urgent', 5: 'Minor'}.get(obj.triage_score, 'Unknown')


# ─── Emergency ────────────────────────────────────────────────────────────────

class EmergencyEscalationSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.name', read_only=True)
    triage_score = serializers.IntegerField(source='triage_assessment.ai_score', read_only=True)
    triage_action = serializers.CharField(source='triage_assessment.ai_action', read_only=True)

    class Meta:
        model = EmergencyEscalation
        fields = '__all__'
        read_only_fields = ('escalated_at', 'resolved_at', 'auto_escalated')


# ─── Notifications ────────────────────────────────────────────────────────────

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'
        read_only_fields = ('sent_at', 'created_at', 'status', 'error_message')
