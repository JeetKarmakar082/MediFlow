from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User, Group
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import models
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
    PatientSerializer, StaffPatientSerializer, MedicalRecordSerializer,
    TriageAssessmentSerializer, TriageInputSerializer, TokenSerializer,
    EmergencyEscalationSerializer, NotificationSerializer
)
from .permissions import (
    is_admin, is_doctor, is_staff_role, get_role,
    IsAdminRole, IsAdminOrDoctor, IsAnyRole
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


def doctor_login_view(request):
    """Dedicated login page for doctors — only accepts users in the 'doctor' group."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    error = None
    username_val = ''
    if request.method == 'POST':
        username_val = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=username_val, password=password)
        if user is not None:
            # Only allow users who are in the doctor group (or superusers)
            if user.is_superuser or user.groups.filter(name='doctor').exists():
                login(request, user)
                return redirect(request.GET.get('next', '/'))
            else:
                error = 'This portal is for doctors only. Please use the staff login.'
        else:
            error = 'Invalid username or password.'

    return render(request, 'doctor_login.html', {'error': error, 'username': username_val})


def doctor_logout_view(request):
    """Logout and redirect back to the doctor login page."""
    logout(request)
    return redirect('doctor-login')


def doctor_signup_view(request):
    """Public signup page — creates a Doctor profile + linked User account in one step."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    departments = Department.objects.filter(is_active=True).order_by('name')
    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = {
            'username':            request.POST.get('username', '').strip(),
            'email':               request.POST.get('email', '').strip(),
            'name':                request.POST.get('name', '').strip(),
            'specialization':      request.POST.get('specialization', '').strip(),
            'department':          request.POST.get('department', '').strip(),
            'phone':               request.POST.get('phone', '').strip(),
            'registration_number': request.POST.get('registration_number', '').strip(),
        }
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        # ── Validate credentials ──────────────────────────────────────────────
        if not form_data['username']:
            errors['username'] = 'Username is required.'
        elif User.objects.filter(username=form_data['username']).exists():
            errors['username'] = 'This username is already taken.'

        if form_data['email'] and User.objects.filter(email=form_data['email']).exists():
            errors['email'] = 'An account with this email already exists.'

        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'

        if password != password2:
            errors['password2'] = 'Passwords do not match.'

        # ── Validate doctor profile ───────────────────────────────────────────
        if not form_data['name']:
            errors['name'] = 'Full name is required.'

        if not form_data['specialization']:
            errors['specialization'] = 'Please select a specialization.'

        if not form_data['department']:
            errors['department'] = 'Please select a department.'

        if not form_data['phone']:
            errors['phone'] = 'Phone number is required.'

        if not form_data['registration_number']:
            errors['registration_number'] = 'Registration number is required.'
        elif Doctor.objects.filter(registration_number=form_data['registration_number']).exists():
            errors['registration_number'] = 'A doctor with this registration number already exists.'

        if not errors:
            try:
                dept = Department.objects.get(pk=form_data['department'])
            except Department.DoesNotExist:
                errors['department'] = 'Selected department does not exist.'

        if not errors:
            # Create the User account
            new_user = User.objects.create_user(
                username=form_data['username'],
                email=form_data['email'],
                password=password,
            )
            # Add to doctor group
            doctor_group, _ = Group.objects.get_or_create(name='doctor')
            new_user.groups.add(doctor_group)

            # Create the Doctor profile linked to the user
            Doctor.objects.create(
                user=new_user,
                name=form_data['name'],
                specialization=form_data['specialization'],
                department=dept,
                phone=form_data['phone'],
                registration_number=form_data['registration_number'],
                is_available=True,
            )

            # Log them in immediately
            login(request, new_user)
            return redirect('dashboard')

    return render(request, 'doctor_signup.html', {
        'errors': errors,
        'form_data': form_data,
        'departments': departments,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


def landing_view(request):
    return render(request, 'landing.html')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    errors = {}
    form_data = {}

    if request.method == 'POST':
        form_data = {
            'username':   request.POST.get('username', '').strip(),
            'email':      request.POST.get('email', '').strip(),
            'first_name': request.POST.get('first_name', '').strip(),
            'last_name':  request.POST.get('last_name', '').strip(),
        }
        password  = request.POST.get('password', '')
        password2 = request.POST.get('password2', '')

        if not form_data['username']:
            errors['username'] = 'Username is required.'
        elif User.objects.filter(username=form_data['username']).exists():
            errors['username'] = 'This username is already taken.'

        if form_data['email'] and User.objects.filter(email=form_data['email']).exists():
            errors['email'] = 'An account with this email already exists.'

        if not password:
            errors['password'] = 'Password is required.'
        elif len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'

        if password != password2:
            errors['password2'] = 'Passwords do not match.'

        if not errors:
            # First user ever → superuser/admin; subsequent users → staff by default
            is_first_user = not User.objects.exists()
            if is_first_user:
                user = User.objects.create_superuser(
                    username=form_data['username'],
                    email=form_data['email'],
                    password=password,
                    first_name=form_data['first_name'],
                    last_name=form_data['last_name'],
                )
            else:
                user = User.objects.create_user(
                    username=form_data['username'],
                    email=form_data['email'],
                    password=password,
                    first_name=form_data['first_name'],
                    last_name=form_data['last_name'],
                )
                staff_group, _ = Group.objects.get_or_create(name='staff')
                user.groups.add(staff_group)
            login(request, user)
            return redirect('dashboard')

    return render(request, 'signup.html', {'errors': errors, 'form_data': form_data})


# ─── Protected Page Views ─────────────────────────────────────────────────────

def _role_context(request):
    """Return role context dict to inject into every template."""
    role = get_role(request.user)
    return {
        'user_role': role,
        'is_admin': role == 'admin',
        'is_doctor': role == 'doctor',
        'is_staff': role == 'staff',
    }

@login_required
def dashboard_view(request):
    ctx = _role_context(request)
    if is_doctor(request.user) and not is_admin(request.user):
        try:
            doctor = request.user.doctor_profile
            ctx['doctor_department_name'] = doctor.department.name if doctor.department else ''
            ctx['doctor_department_code'] = doctor.department.code if doctor.department else ''
        except Exception:
            ctx['doctor_department_name'] = ''
            ctx['doctor_department_code'] = ''
    return render(request, 'dashboard.html', ctx)

@login_required
def patients_view(request):
    return render(request, 'patients.html', _role_context(request))

@login_required
def triage_view(request):
    if is_staff_role(request.user) and not is_admin(request.user):
        return redirect('queue')
    # Doctors CAN perform triage for patients in their department
    ctx = _role_context(request)
    if is_doctor(request.user) and not is_admin(request.user):
        try:
            doctor = request.user.doctor_profile
            ctx['doctor_department_code'] = doctor.department.code if doctor.department else ''
            ctx['doctor_department_name'] = doctor.department.name if doctor.department else ''
            ctx['doctor_profile_id'] = doctor.id
        except Exception:
            ctx['doctor_department_code'] = ''
            ctx['doctor_department_name'] = ''
            ctx['doctor_profile_id'] = None
    return render(request, 'triage.html', ctx)

@login_required
def queue_view(request):
    ctx = _role_context(request)
    # Pass the doctor's department code so the template can pre-filter
    if is_doctor(request.user) and not is_admin(request.user):
        try:
            doctor = request.user.doctor_profile
            ctx['doctor_department_code'] = doctor.department.code if doctor.department else ''
            ctx['doctor_department_name'] = doctor.department.name if doctor.department else ''
        except Exception:
            ctx['doctor_department_code'] = ''
            ctx['doctor_department_name'] = ''
    return render(request, 'queue.html', ctx)

@login_required
def doctors_view(request):
    if is_staff_role(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    # Doctors cannot manage other doctors
    if is_doctor(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    return render(request, 'doctors.html', _role_context(request))

@login_required
def emergency_view(request):
    return render(request, 'emergency.html', _role_context(request))

@login_required
def assessments_view(request):
    if is_staff_role(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    # Doctors can view triage history for their department patients
    ctx = _role_context(request)
    if is_doctor(request.user) and not is_admin(request.user):
        try:
            doctor = request.user.doctor_profile
            ctx['doctor_department_code'] = doctor.department.code if doctor.department else ''
        except Exception:
            ctx['doctor_department_code'] = ''
    return render(request, 'assessments.html', ctx)

@login_required
def schedules_view(request):
    if is_staff_role(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    if is_doctor(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    return render(request, 'schedules.html', _role_context(request))

@login_required
def records_view(request):
    if is_staff_role(request.user) and not is_admin(request.user):
        return redirect('dashboard')
    ctx = _role_context(request)
    # Pass the doctor's own profile id so the template can pre-select it
    if is_doctor(request.user) and not is_admin(request.user):
        try:
            doctor = request.user.doctor_profile
            ctx['doctor_profile_id'] = doctor.id
            ctx['doctor_profile_name'] = doctor.name
        except Exception:
            ctx['doctor_profile_id'] = None
            ctx['doctor_profile_name'] = ''
    return render(request, 'records.html', ctx)

def queue_display_view(request, department):
    return render(request, 'queue_display.html', {'department': department})

@login_required
def user_management_view(request):
    """Admin-only: assign roles, create doctor accounts, and link doctors to user accounts."""
    if not is_admin(request.user):
        return redirect('dashboard')

    success_msg = None
    error_msg = None

    if request.method == 'POST':
        action_type = request.POST.get('action')

        # ── Create a brand-new doctor user account ────────────────────────────
        if action_type == 'create_doctor_user':
            username  = request.POST.get('new_username', '').strip()
            password  = request.POST.get('new_password', '').strip()
            doctor_id = request.POST.get('doctor_id_new', '').strip()

            if not username or not password:
                error_msg = 'Username and password are required.'
            elif User.objects.filter(username=username).exists():
                error_msg = f'Username "{username}" is already taken.'
            else:
                try:
                    new_user = User.objects.create_user(username=username, password=password)
                    doctor_group, _ = Group.objects.get_or_create(name='doctor')
                    new_user.groups.add(doctor_group)
                    # Optionally link to a Doctor profile immediately
                    if doctor_id:
                        try:
                            doctor = Doctor.objects.get(pk=doctor_id)
                            # Unlink any previous user from this doctor profile
                            Doctor.objects.filter(user=new_user).update(user=None)
                            if doctor.user and doctor.user != new_user:
                                doctor.user.groups.remove(doctor_group)
                            doctor.user = new_user
                            doctor.save()
                            success_msg = (
                                f'Doctor account "{username}" created and linked to '
                                f'Dr. {doctor.name}. They can now log in at /doctor/login/'
                            )
                        except Doctor.DoesNotExist:
                            success_msg = (
                                f'Doctor account "{username}" created. '
                                f'Link a Doctor profile to complete setup.'
                            )
                    else:
                        success_msg = (
                            f'Doctor account "{username}" created. '
                            f'Link a Doctor profile to complete setup.'
                        )
                except Exception as e:
                    error_msg = f'Error creating account: {e}'

        else:
            # ── Existing user actions ─────────────────────────────────────────
            user_id = request.POST.get('user_id')
            try:
                target_user = User.objects.get(pk=user_id)
            except User.DoesNotExist:
                return redirect('user-management')

            if action_type == 'set_role':
                role = request.POST.get('role')
                target_user.groups.clear()
                if role == 'doctor':
                    target_user.groups.add(Group.objects.get_or_create(name='doctor')[0])
                elif role == 'staff':
                    target_user.groups.add(Group.objects.get_or_create(name='staff')[0])
                elif role == 'admin':
                    target_user.is_superuser = True
                    target_user.is_staff = True
                    target_user.save()
                success_msg = f'Role updated for {target_user.username}.'

            elif action_type == 'link_doctor':
                doctor_id = request.POST.get('doctor_id')
                if doctor_id:
                    try:
                        doctor = Doctor.objects.get(pk=doctor_id)
                        # Unlink any previous doctor linked to this user
                        Doctor.objects.filter(user=target_user).update(user=None)
                        doctor.user = target_user
                        doctor.save()
                        # Ensure user is in doctor group
                        target_user.groups.clear()
                        target_user.groups.add(Group.objects.get_or_create(name='doctor')[0])
                        success_msg = (
                            f'{target_user.username} linked to Dr. {doctor.name}. '
                            f'They can log in at /doctor/login/'
                        )
                    except Doctor.DoesNotExist:
                        error_msg = 'Doctor profile not found.'

        if not success_msg and not error_msg:
            return redirect('user-management')

    users = User.objects.prefetch_related('groups').select_related('doctor_profile').order_by('username')
    doctors = Doctor.objects.select_related('user', 'department').all()

    users_with_roles = []
    for u in users:
        group_names = [g.name for g in u.groups.all()]
        linked_doctor = getattr(u, 'doctor_profile', None)
        users_with_roles.append({
            'user': u,
            'role': 'admin' if u.is_superuser else (group_names[0] if group_names else 'none'),
            'group_names': group_names,
            'linked_doctor': linked_doctor,
            'is_current': u.id == request.user.id,
        })

    ctx = {
        **_role_context(request),
        'users_with_roles': users_with_roles,
        'doctors': doctors,
        'success_msg': success_msg,
        'error_msg': error_msg,
    }
    return render(request, 'user_management.html', ctx)


# ─── Dashboard Stats API ──────────────────────────────────────────────────────

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.db.models import Q
        today = timezone.now().date()

        # For doctors: scope to their department. For admin/staff: all departments.
        doctor_dept = None
        if is_doctor(request.user) and not is_admin(request.user):
            try:
                doctor = request.user.doctor_profile
                if doctor.department:
                    doctor_dept = doctor.department
            except Exception:
                pass

        # Base token queryset — scoped to department for doctors
        if doctor_dept:
            token_qs = Token.objects.filter(department=doctor_dept)
        else:
            token_qs = Token.objects.all()

        # Base triage queryset — scoped to department patients for doctors
        if doctor_dept:
            dept_patient_ids = token_qs.values_list('patient_id', flat=True)
            triage_qs = TriageAssessment.objects.filter(patient_id__in=dept_patient_ids)
        else:
            triage_qs = TriageAssessment.objects.all()

        stats = {
            'today': {
                # Unique patients who got a token today
                'total_patients': token_qs.filter(
                    created_at__date=today
                ).values('patient_id').distinct().count(),

                # Currently in queue waiting to be called
                'waiting': token_qs.filter(status='waiting').count(),

                # Called or currently being seen
                'in_progress': token_qs.filter(
                    status__in=['called', 'in_progress']
                ).count(),

                # Completed today — token marked done with completed_at today
                'completed': token_qs.filter(
                    status='done', completed_at__date=today
                ).count(),

                # Active emergency escalations raised today
                'emergencies': EmergencyEscalation.objects.filter(
                    escalated_at__date=today, status='active'
                ).count(),
            },
            'doctors': {
                'total': Doctor.objects.count(),
                'available': Doctor.objects.filter(is_available=True).count(),
            },
            'queue_by_department': list(
                token_qs.filter(status__in=['waiting', 'called', 'in_progress'])
                .values('department__name')
                .annotate(count=Count('id'))
                .order_by('-count')
            ),
            'triage_breakdown': {
                'critical':    triage_qs.filter(ai_score=1).count(),
                'emergency':   triage_qs.filter(ai_score=2).count(),
                'urgent':      triage_qs.filter(ai_score=3).count(),
                'semi_urgent': triage_qs.filter(ai_score=4).count(),
                'minor':       triage_qs.filter(ai_score=5).count(),
            },
            'scoped_to_department': doctor_dept.name if doctor_dept else None,
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
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        # Staff get limited fields; doctors and admins get full details
        if is_staff_role(self.request.user) and not is_admin(self.request.user) and not is_doctor(self.request.user):
            return StaffPatientSerializer
        return PatientSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        # Doctors see all patients — they are filtered at the data level
        # (triage, records, tokens) but the patient list itself is unrestricted
        # so doctors can search and select any patient for triage/records
        if phone := self.request.query_params.get('phone'):
            qs = qs.filter(phone__icontains=phone)
        if name := self.request.query_params.get('name'):
            qs = qs.filter(name__icontains=name)
        # Generic search across both name and phone
        if q := self.request.query_params.get('q'):
            from django.db.models import Q
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q))
        return qs

    def create(self, request, *args, **kwargs):
        # Staff can register patients; doctors cannot
        if is_doctor(request.user) and not is_admin(request.user):
            return Response({'error': 'Doctors cannot register patients.'}, status=status.HTTP_403_FORBIDDEN)
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=['get'], url_path='history')
    def history(self, request, pk=None):
        patient = self.get_object()
        records = MedicalRecord.objects.filter(patient=patient)
        return Response(MedicalRecordSerializer(records, many=True).data)


class MedicalRecordViewSet(viewsets.ModelViewSet):
    queryset = MedicalRecord.objects.all()
    serializer_class = MedicalRecordSerializer
    permission_classes = [IsAdminOrDoctor]

    def get_queryset(self):
        qs = super().get_queryset()
        # Doctors see records they created OR records for patients in their department
        if is_doctor(self.request.user) and not is_admin(self.request.user):
            try:
                doctor = self.request.user.doctor_profile
                own_record_ids = MedicalRecord.objects.filter(doctor=doctor).values_list('id', flat=True)
                dept_patient_ids = []
                if doctor.department:
                    dept_patient_ids = Token.objects.filter(
                        department=doctor.department
                    ).values_list('patient_id', flat=True)
                dept_record_ids = MedicalRecord.objects.filter(
                    patient_id__in=dept_patient_ids
                ).values_list('id', flat=True)
                qs = qs.filter(id__in=set(list(own_record_ids) + list(dept_record_ids)))
            except Exception:
                qs = qs.none()
        if pid := self.request.query_params.get('patient'):
            qs = qs.filter(patient_id=pid)
        return qs

    def perform_create(self, serializer):
        # Auto-assign the logged-in doctor's profile when a doctor creates a record
        if is_doctor(self.request.user) and not is_admin(self.request.user):
            try:
                doctor = self.request.user.doctor_profile
                serializer.save(doctor=doctor)
                return
            except Exception:
                pass
        serializer.save()

    def update(self, request, *args, **kwargs):
        # Doctors can only update records they own
        if is_doctor(request.user) and not is_admin(request.user):
            record = self.get_object()
            try:
                doctor = request.user.doctor_profile
                if record.doctor != doctor:
                    return Response(
                        {'error': 'You can only edit your own medical records.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return Response({'error': 'No doctor profile linked.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # Doctors can only delete records they own
        if is_doctor(request.user) and not is_admin(request.user):
            record = self.get_object()
            try:
                doctor = request.user.doctor_profile
                if record.doctor != doctor:
                    return Response(
                        {'error': 'You can only delete your own medical records.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return Response({'error': 'No doctor profile linked.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)


# ─── Triage ViewSet ───────────────────────────────────────────────────────────

class TriageViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TriageAssessment.objects.all()
    serializer_class = TriageAssessmentSerializer
    permission_classes = [IsAdminOrDoctor]

    def get_queryset(self):
        qs = super().get_queryset()
        # Doctors only see triage for patients with tokens in their department
        if is_doctor(self.request.user) and not is_admin(self.request.user):
            try:
                doctor = self.request.user.doctor_profile
                if doctor.department:
                    patient_ids = Token.objects.filter(
                        department=doctor.department
                    ).values_list('patient_id', flat=True)
                    qs = qs.filter(patient_id__in=patient_ids)
                else:
                    qs = qs.none()
            except Exception:
                qs = qs.none()
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

        # Doctors can triage any patient — token is assigned to their department
        if is_doctor(request.user) and not is_admin(request.user):
            try:
                doctor = request.user.doctor_profile
                if not doctor.department:
                    return Response(
                        {'error': 'Your doctor profile has no assigned department.'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            except Exception:
                return Response(
                    {'error': 'No doctor profile linked to your account.'},
                    status=status.HTTP_403_FORBIDDEN
                )

        return self._run_triage(request, data, patient)

    def _run_triage(self, request, data, patient):
        vitals = {
            'bp_systolic': data['bp_systolic'], 'bp_diastolic': data['bp_diastolic'],
            'pulse': data['pulse'], 'temperature': data['temperature'],
            'oxygen': data['oxygen_level'], 'pain': data['pain_scale'],
        }
        result = calculate_triage_score(vitals, data['symptoms'])

        score = result['score']

        assessment = TriageAssessment.objects.create(
            patient=patient, symptoms=data['symptoms'],
            bp_systolic=data['bp_systolic'], bp_diastolic=data['bp_diastolic'],
            pulse=data['pulse'], temperature=data['temperature'],
            oxygen_level=data['oxygen_level'], pain_scale=data['pain_scale'],
            ai_score=score, ai_reasoning=result['reason'],
            ai_action=result['action'], ai_source=result.get('source', 'rule_based'),
            assessed_by=data.get('assessed_by', ''),
        )

        # Determine the department for the token:
        # - Doctor portal: always the doctor's own department regardless of score
        # - Admin/staff: AI-suggested dept, with emergency dept override for score 1 & 2
        assigned_dept = None

        if is_doctor(request.user) and not is_admin(request.user):
            # Token always goes to the doctor's department
            try:
                assigned_dept = request.user.doctor_profile.department
            except Exception:
                pass
        else:
            # Admin/staff path — use AI-suggested department
            ai_department_code = result.get('department', 'general')
            if score <= 2:
                ai_department_code = 'emergency'
            assigned_dept = Department.objects.filter(code=ai_department_code).first()
            if not assigned_dept:
                assigned_dept = (
                    Department.objects.filter(code='general').first() or
                    Department.objects.filter(is_active=True).first()
                )

        # Create the queue token — for emergency/critical scores, triage_score stays 1
        # so the patient floats to the top of the queue regardless of department
        token = None
        if assigned_dept:
            token = Token.objects.create(
                patient=patient,
                department=assigned_dept,
                token_number=Token.generate_token_number(assigned_dept),
                triage_score=score,  # score 1 = highest priority in queue ordering
                status='waiting',
                notes=(
                    f"Auto-assigned by {'Gemini AI' if result.get('source') == 'gemini' else 'Rule-Based Engine'}. "
                    f"Score {score} — dept: {assigned_dept.name}."
                ),
            )

        # Score 1 & 2: create an emergency escalation record for tracking
        if score <= 2:
            score_label = 'CRITICAL' if score == 1 else 'EMERGENCY'
            EmergencyEscalation.objects.create(
                patient=patient,
                triage_assessment=assessment,
                token=token,
                reason=(
                    f"[AUTO] Triage score {score} — {score_label}. "
                    f"{result['reason']}. Action: {result['action']}"
                ),
                escalated_by=data.get('assessed_by') or 'Triage System',
                auto_escalated=True,
                status='active',
            )

        response_data = TriageAssessmentSerializer(assessment).data
        response_data['assigned_department'] = assigned_dept.name if assigned_dept else None
        response_data['assigned_department_code'] = assigned_dept.code if assigned_dept else None
        response_data['token_number'] = token.token_number if token else None
        return Response(response_data, status=status.HTTP_201_CREATED)


# ─── Token / Queue ViewSet ────────────────────────────────────────────────────

class TokenViewSet(viewsets.ModelViewSet):
    queryset = Token.objects.all()
    serializer_class = TokenSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = super().get_queryset()
        # Doctors only see tokens for their assigned department
        if is_doctor(self.request.user) and not is_admin(self.request.user):
            try:
                doctor = self.request.user.doctor_profile
                if doctor.department:
                    qs = qs.filter(department=doctor.department)
                else:
                    return qs.none()
            except Exception:
                return qs.none()
        # Allow filtering by department code (ignored for doctors — their dept is enforced above)
        if not (is_doctor(self.request.user) and not is_admin(self.request.user)):
            if dept := self.request.query_params.get('department'):
                qs = qs.filter(department__code=dept)
        # Support multiple status values: ?status=waiting&status=called
        statuses = self.request.query_params.getlist('status')
        if statuses:
            qs = qs.filter(status__in=statuses)
        return qs

    def perform_create(self, serializer):
        # Doctors can only create tokens for their own department
        if is_doctor(self.request.user) and not is_admin(self.request.user):
            try:
                doctor = self.request.user.doctor_profile
                if doctor.department:
                    dept = serializer.validated_data.get('department')
                    if dept and dept != doctor.department:
                        from rest_framework.exceptions import PermissionDenied
                        raise PermissionDenied('You can only issue tokens for your own department.')
            except Exception as e:
                if 'PermissionDenied' in type(e).__name__:
                    raise
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

    def perform_update(self, serializer):
        """Auto-set completed_at when status is set to done via PATCH."""
        instance = serializer.instance
        new_status = serializer.validated_data.get('status', instance.status)
        if new_status == 'done' and not instance.completed_at:
            serializer.save(completed_at=timezone.now())
        else:
            serializer.save()


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
