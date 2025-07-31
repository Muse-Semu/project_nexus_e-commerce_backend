from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from .models import User, VendorProfile, CustomerProfile, AuditLog
from .tasks import send_welcome_email, send_vendor_approval_notification

User = get_user_model()


@receiver(post_save, sender=User)
def create_user_profiles(sender, instance, created, **kwargs):
    """
    Create vendor or customer profile when user is created
    """
    if created:
        if instance.role == 'vendor':
            VendorProfile.objects.create(user=instance)
        elif instance.role == 'customer':
            CustomerProfile.objects.create(user=instance)
        
        # Send welcome email
        try:
            send_welcome_email.delay(instance.id)
        except Exception as e:
            # Log the error but don't fail the user creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send welcome email for user {instance.id}: {e}")


@receiver(post_save, sender=VendorProfile)
def handle_vendor_approval(sender, instance, created, **kwargs):
    """
    Send notification when vendor is approved
    """
    if not created and instance.is_approved and instance.approved_by:
        try:
            send_vendor_approval_notification.delay(instance.id)
        except Exception as e:
            # Log the error but don't fail the approval
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send vendor approval notification for vendor {instance.id}: {e}")


@receiver(post_save, sender=User)
def log_user_changes(sender, instance, **kwargs):
    """
    Log user changes for audit purposes
    """
    if hasattr(instance, '_audit_action'):
        AuditLog.objects.create(
            user=instance,
            action=instance._audit_action,
            details={'user_id': instance.id}
        ) 