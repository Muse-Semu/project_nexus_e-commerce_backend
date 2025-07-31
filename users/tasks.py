from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_sms_verification(self, phone_number, code):
    """
    Send SMS verification code using Twilio Simulator
    """
    try:
        # Initialize Twilio client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        # Send SMS using Twilio Simulator
        message = client.messages.create(
            body=f'Your verification code is: {code}',
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"SMS sent successfully to {phone_number}: {message.sid}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send SMS to {phone_number}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_email_notification(self, email, subject, message, template_name=None, context=None):
    """
    Send email notification
    """
    try:
        if template_name and context:
            # Render email template
            html_message = render_to_string(template_name, context)
            plain_message = message
        else:
            html_message = None
            plain_message = message
        
        # Send email
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.EMAIL_HOST_USER,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Email sent successfully to {email}")
        return True
        
    except Exception as exc:
        logger.error(f"Failed to send email to {email}: {str(exc)}")
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, user_id):
    """
    Send welcome email to new users
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Welcome to Our E-commerce Platform!'
        message = f"""
        Hello {user.first_name},
        
        Welcome to our e-commerce platform! Your account has been created successfully.
        
        Please verify your phone number to complete your registration.
        
        Best regards,
        The E-commerce Team
        """
        
        send_email_notification.delay(user.email, subject, message)
        logger.info(f"Welcome email sent to {user.email}")
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
    except Exception as exc:
        logger.error(f"Failed to send welcome email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_reset_email(self, user_id, reset_url):
    """
    Send password reset email
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Password Reset Request'
        message = f"""
        Hello {user.first_name},
        
        You have requested to reset your password. Click the link below to reset it:
        
        {reset_url}
        
        If you didn't request this, please ignore this email.
        
        Best regards,
        The E-commerce Team
        """
        
        send_email_notification.delay(user.email, subject, message)
        logger.info(f"Password reset email sent to {user.email}")
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
    except Exception as exc:
        logger.error(f"Failed to send password reset email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_account_activation_email(self, user_id, activation_url):
    """
    Send account activation email
    """
    try:
        from .models import User
        user = User.objects.get(id=user_id)
        
        subject = 'Activate Your Account'
        message = f"""
        Hello {user.first_name},
        
        Thank you for registering! Please click the link below to activate your account:
        
        {activation_url}
        
        Best regards,
        The E-commerce Team
        """
        
        send_email_notification.delay(user.email, subject, message)
        logger.info(f"Account activation email sent to {user.email}")
        
    except User.DoesNotExist:
        logger.error(f"User with id {user_id} not found")
    except Exception as exc:
        logger.error(f"Failed to send account activation email: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_vendor_approval_notification(self, vendor_id):
    """
    Send notification when vendor is approved
    """
    try:
        from .models import VendorProfile
        vendor_profile = VendorProfile.objects.get(id=vendor_id)
        
        subject = 'Vendor Account Approved!'
        message = f"""
        Hello {vendor_profile.user.first_name},
        
        Congratulations! Your vendor account has been approved. You can now start adding products to our platform.
        
        Best regards,
        The E-commerce Team
        """
        
        send_email_notification.delay(vendor_profile.user.email, subject, message)
        logger.info(f"Vendor approval notification sent to {vendor_profile.user.email}")
        
    except VendorProfile.DoesNotExist:
        logger.error(f"Vendor profile with id {vendor_id} not found")
    except Exception as exc:
        logger.error(f"Failed to send vendor approval notification: {str(exc)}")
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries)) 