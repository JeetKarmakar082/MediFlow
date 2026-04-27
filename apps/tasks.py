import logging
from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_sms_notification(self, patient_id: int, message: str, notification_type: str = 'general'):
    from apps.models import Patient, Notification

    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return

    notif = Notification.objects.create(
        patient=patient, notification_type=notification_type,
        message=message, phone=patient.phone,
    )

    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')
    from_num = getattr(settings, 'TWILIO_PHONE_NUMBER', '')

    if not all([sid, token, from_num]):
        logger.info(f"[SMS MOCK] To {patient.phone}: {message}")
        notif.status = 'sent'
        notif.sent_at = timezone.now()
        notif.save()
        return

    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(body=message, from_=from_num, to=f"+91{patient.phone}")
        notif.status = 'sent'
        notif.sent_at = timezone.now()
        notif.save()
    except Exception as exc:
        notif.status = 'failed'
        notif.error_message = str(exc)
        notif.save()
        raise self.retry(exc=exc, countdown=60)
