from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count
from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import (
    Department, Doctor, DoctorSchedule, Patient, MedicalRecord,
    TriageAssessment, Token, EmergencyEscalation, Notification
)
from .serializers import (
    DepartmentSerializer, DoctorSerializer, DoctorScheduleSerializer,
    PatientSerializer, MedicalRecordSerializer, TriageAssessmentSerializer,
    TriageInputSerializer, TokenSerializer, EmergencyEscalationSerializer,
    NotificationSerializer
)
from .triage_engine import calculate_triage_score


# ─── Auth Views ───────────────────────────────────────────────────────────────

def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect(request.GET.get('next', '/'))
        error = 'Invalid username or password.'

    return render(request, 'login.html', {'error': error})


def logout_view(request):
    logout(request)
    return redirect('login')


# ─── Protected Page Views ─────────────────────────────────────────────────────

@login_required
def dashboard_view(request):
    return render(request, 'dashboard.html')

@login_required
def patients_view(request):
    return render(request, 'patients.html')

@login_required
def triage_view(request):
    return render(request, 'triage.html')

@login_required
def queue_view(request):
    return render(request, 'queue.html')

@login_required
def doctors_view(request):
    return render(request, 'doctors.html')

@login_required
def emergency_view(request):
    return render(request, 'emergency.html')

@login_required
def assessments_view(request):
    return render(request, 'assessments.html')

@login_required
def schedules_view(request):
    return render(request, 'schedules.html')

@login_required
def records_view(request):
    return render(request, 'records.html')

def queue_display_view(request, department):
    # Public — TV display board doesn't need login
    return render(request, 'queue_display.html', {'department': department})


# ─── Dashboard Stats API ──────────────────────────────────────────────────────

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.now().date()
        stats = {
            'today': {
                'total_patients': Token.objects.filter(created_at__date=today).count(),
                'waiting': Token.objects.filter(status__in=['waiting', 'called']).count(),
                'in_progress': Token.objects.filter(status='in_progress').count(),
                'completed': Token.objects.filter(status='done', completed_at__date=today).count(),
                'emergencies': EmergencyEscalation.objects.filter(escalated_at__date=today, status='active').count(),
            },
            'doctors': {
                'total': Doctor.objects.count(),
                'available': Doctor.objects.filter(is_available=True).count(),
            },
            'queue_by_department': list(
                Token.objects.filter(status__in=['waiting', 'called'])
                .values('department__name')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
            'triage_breakdown': {
                'critical':    TriageAssessment.objects.filter(ai_score=1).count(),
                'emergency':   TriageAssessment.objects.filter(ai_score=2).count(),
                'urgent':      TriageAssessment.objects.filter(ai_score=3).count(),
                'semi_urgent': TriageAssessment.objects.filter(ai_score=4).count(),
                'minor':       TriageAssessment.objects.filter(ai_score=5).count(),
            },
        }
        return Response(stats)


# ─── Department ViewSet ───────────────────────────────────────────────────────

class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.filter(is_active=True)
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]


# ─── Doctor Schedule ViewSet ──────────────────────────────────────────────────

class DoctorScheduleViewSet(viewsets.ModelViewSet):
    queryset = DoctorSchedule.objects.select_related('doctor').all()
    serializer_class = DoctorScheduleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if doctor_id := self.request.query_params.get('doctor'):
            qs = qs.filter(doctor_id=doctor_id)
        return qs


# ─── Doctor ViewSet ────────────────────────────────────────────────────────────

class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.all()
    serializer_class = DoctorSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['get'], url_path='availability')
    def availability(self, request):
        today = timezone.now().weekday()
        current_time = timezone.now().time()
        schedules = DoctorSchedule.objects.filter(
            day_of_week=today, start_time__lte=current_time,
            end_time__gte=current_time, is_active=True, doctor__is_available=True,
        ).select_related('doctor')
        dept = request.query_params.get('department')
        if dept:
            schedules = schedules.filter(doctor__department=dept)
        return Response(DoctorSerializer([s.doctor for s in schedules], many=True).data)

    @action(detail=True, methods=['patch'], url_path='toggle-availability')
    def toggle_availability(self, request, pk=None):
        doctor = self.get_object()
        doctor.is_available = not doctor.is_available
        doctor.save()
        return Response({'is_available': doctor.is_available})


# ─── Patient ViewSet ──────────────────────────────────────────────────────────

class PatientViewSet(viewsets.ModelViewSet):
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if phone := self.request.query_params.get('phone'):
            qs = qs.filter(phone__icontains=phone)
        if name := self.request.query_params.get('name'):
            qs = qs.filter(name__icontains=name)
        return qs

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        patient = self.get_object()
        records = MedicalRecord.objects.filter(patient=patient)
        return Response(MedicalRecordSerializer(records, many=True).data)


class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.all()
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if pid := self.request.query_params.get('patient'):
            qs = qs.filter(patient_id=pid)
        return qs


# ─── Triage ViewSet ───────────────────────────────────────────────────────────

class TriageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TriageAssessment.objects.all()
    serializer_class = TriageAssessmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if pid := self.request.query_params.get('patient'):
            qs = qs.filter(patient_id=pid)
        return qs

    @action(detail=False, methods=['post'], url_path='assess')
    def assess(self, request):
        serializer = TriageInputSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        try:
            patient = Patient.objects.get(pk=data['patient_id'])
        except Patient.DoesNotExist:
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        vitals = {
            'bp_systolic': data['bp_systolic'], 'bp_diastolic': data['bp_diastolic'],
            'pulse': data['pulse'], 'temperature': data['temperature'],
            'oxygen': data['oxygen_level'], 'pain': data['pain_scale'],
        }
        result = calculate_triage_score(vitals, data['symptoms'])
        assessment = TriageAssessment.objects.create(
            patient=patient, symptoms=data['symptoms'],
            bp_systolic=data['bp_systolic'], bp_diastolic=data['bp_diastolic'],
            pulse=data['pulse'], temperature=data['temperature'],
            oxygen_level=data['oxygen_level'], pain_scale=data['pain_scale'],
            ai_score=result['score'], ai_reasoning=result['reason'],
            ai_action=result['action'], ai_source=result.get('source', 'rule_based'),
            assessed_by=data.get('assessed_by', ''),
        )

        # Auto-escalate to emergency if score is 1 (Critical) or 2 (Emergency)
        if result['score'] <= 2:
            score_label = 'CRITICAL' if result['score'] == 1 else 'EMERGENCY'

            # Get or fallback to emergency department
            emergency_dept = Department.objects.filter(code='emergency').first()

            # Auto-create a queue token in the Emergency department
            token = None
            if emergency_dept:
                token = Token.objects.create(
                    patient=patient,
                    department=emergency_dept,
                    token_number=Token.generate_token_number(emergency_dept),
                    triage_score=result['score'],
                    status='waiting',
                    notes=f"Auto-created from triage. Score {result['score']} — {score_label}.",
                )

            # Create the emergency escalation linked to both triage and token
            EmergencyEscalation.objects.create(
                patient=patient,
                triage_assessment=assessment,
                token=token,
                reason=(
                    f"[AUTO] Triage score {result['score']} — {score_label}. "
                    f"{result['reason']}. Action: {result['action']}"
                ),
                escalated_by=data.get('assessed_by') or 'Triage System',
                auto_escalated=True,
                status='active',
            )

        return Response(TriageAssessmentSerializer(assessment).data, status=status.HTTP_201_CREATED)


# ─── Token / Queue ViewSet ────────────────────────────────────────────────────

class TokenViewSet(viewsets.ModelViewSet):
    queryset = Token.objects.all()
    serializer_class = TokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if dept := self.request.query_params.get('department'):
            qs = qs.filter(department__code=dept)
        # Support multiple status values: ?status=waiting&status=called
        statuses = self.request.query_params.getlist('status')
        if statuses:
            qs = qs.filter(status__in=statuses)
        return qs

    def perform_create(self, serializer):
        department = serializer.validated_data['department']
        token = serializer.save(token_number=Token.generate_token_number(department))
        try:
            from .tasks import send_sms_notification
            send_sms_notification.delay(
                patient_id=token.patient.id,
                message=f"Token #{token.token_number} for {department} assigned. Est. wait: {self._wait(token)} mins.",
                notification_type='token_assigned',
            )
        except Exception:
            pass
        self._broadcast(department)

    def _wait(self, token):
        return Token.objects.filter(
            department=token.department, status='waiting',
            triage_score__lte=token.triage_score, created_at__lt=token.created_at,
        ).count() * 10

    def _broadcast(self, department):
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            layer = get_channel_layer()
            if layer:
                waiting = Token.objects.filter(department=department, status='waiting').count()
                current = Token.objects.filter(department=department, status='in_progress').first()
                async_to_sync(layer.group_send)(f"queue_{department}", {
                    'type': 'queue_update',
                    'current_token': current.token_number if current else None,
                    'waiting_count': waiting,
                    'department': department,
                })
        except Exception:
            pass

    @action(detail=False, methods=['get'], url_path='status')
    def queue_status(self, request):
        dept_code = request.query_params.get('department', '')
        qs = Token.objects.filter(status='waiting')
        if dept_code:
            qs = qs.filter(department__code=dept_code)
        current = Token.objects.filter(department__code=dept_code, status='in_progress').first() if dept_code else None
        return Response({
            'department': dept_code,
            'current_token': TokenSerializer(current).data if current else None,
            'waiting_count': qs.count(),
            'waiting_queue': TokenSerializer(qs[:10], many=True).data,
        })

    @action(detail=False, methods=['post'], url_path='call-next')
    def call_next(self, request):
        dept_code = request.data.get('department', '')
        next_token = Token.objects.filter(
            department__code=dept_code, status='waiting'
        ).order_by('triage_score', 'created_at').first()
        if not next_token:
            return Response({'message': 'No patients waiting'})
        next_token.status = 'called'
        next_token.called_at = timezone.now()
        next_token.save()
        try:
            from .tasks import send_sms_notification
            send_sms_notification.delay(
                patient_id=next_token.patient.id,
                message=f"Token #{next_token.token_number}: Please proceed to {next_token.department.name if next_token.department else dept_code} now.",
                notification_type='token_called',
            )
        except Exception:
            pass
        self._broadcast(dept_code)
        return Response(TokenSerializer(next_token).data)

    @action(detail=True, methods=['patch'], url_path='complete')
    def complete(self, request, pk=None):
        token = self.get_object()
        token.status = 'done'
        token.completed_at = timezone.now()
        token.save()
        self._broadcast(token.department)
        return Response(TokenSerializer(token).data)


# ─── Emergency ViewSet ────────────────────────────────────────────────────────

class EmergencyViewSet(viewsets.ModelViewSet):
    queryset = EmergencyEscalation.objects.all()
    serializer_class = EmergencyEscalationSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'], url_path='escalate')
    def escalate(self, request):
        serializer = EmergencyEscalationSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        escalation = serializer.save()

        if escalation.token:
            # If a token was provided, bump its priority to critical
            escalation.token.triage_score = 1
            escalation.token.status = 'waiting'
            escalation.token.save()
        else:
            # No token linked — auto-create one in Emergency department
            emergency_dept = Department.objects.filter(code='emergency').first()
            if emergency_dept:
                token = Token.objects.create(
                    patient=escalation.patient,
                    department=emergency_dept,
                    token_number=Token.generate_token_number(emergency_dept),
                    triage_score=1,
                    status='waiting',
                    notes=f"Auto-created from manual emergency escalation. Reason: {escalation.reason[:100]}",
                )
                # Link the token back to the escalation
                escalation.token = token
                escalation.save()

        return Response(EmergencyEscalationSerializer(escalation).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['patch'], url_path='resolve')
    def resolve(self, request, pk=None):
        escalation = self.get_object()
        escalation.status = 'resolved'
        escalation.resolved_at = timezone.now()
        escalation.resolution_notes = request.data.get('resolution_notes', '')
        escalation.save()
        return Response(EmergencyEscalationSerializer(escalation).data)


# ─── Notification ViewSet ─────────────────────────────────────────────────────

class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        if pid := self.request.query_params.get('patient'):
            qs = qs.filter(patient_id=pid)
        return qs
