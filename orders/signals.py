from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Order, OrderStatus, Return
from .tasks import (
    send_order_confirmation_email, send_order_shipped_email, 
    send_order_delivered_email, send_return_approval_email,
    send_return_rejection_email
)


@receiver(post_save, sender=Order)
def handle_order_status_changes(sender, instance, created, **kwargs):
    """
    Handle order status changes and trigger appropriate actions
    """
    if created:
        # New order created
        return
    
    # Check if status changed
    if instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        
        # Send appropriate notifications based on status change
        if new_status == 'confirmed' and old_status == 'pending':
            # Order confirmed - send confirmation email
            send_order_confirmation_email.delay(str(instance.id))
            
        elif new_status == 'shipped' and old_status == 'confirmed':
            # Order shipped - send shipping notification
            send_order_shipped_email.delay(str(instance.id))
            
        elif new_status == 'delivered' and old_status == 'shipped':
            # Order delivered - send delivery notification
            send_order_delivered_email.delay(str(instance.id))


@receiver(post_save, sender=Return)
def handle_return_status_changes(sender, instance, created, **kwargs):
    """
    Handle return status changes and trigger appropriate actions
    """
    if created:
        # New return request created
        return
    
    # Check if status changed
    if instance.tracker.has_changed('status'):
        old_status = instance.tracker.previous('status')
        new_status = instance.status
        
        # Send appropriate notifications based on status change
        if new_status == 'approved' and old_status == 'pending':
            # Return approved - send approval email
            send_return_approval_email.delay(str(instance.id))
            
        elif new_status == 'rejected' and old_status == 'pending':
            # Return rejected - send rejection email
            send_return_rejection_email.delay(str(instance.id))


@receiver(post_save, sender=OrderStatus)
def log_order_status_changes(sender, instance, created, **kwargs):
    """
    Log order status changes for audit purposes
    """
    if created:
        # Log the status change
        from django.contrib.admin.models import LogEntry, CHANGE
        from django.contrib.contenttypes.models import ContentType
        
        LogEntry.objects.log_action(
            user_id=instance.created_by.id if instance.created_by else None,
            content_type_id=ContentType.objects.get_for_model(Order).pk,
            object_id=instance.order.id,
            object_repr=f"Order {instance.order.order_number}",
            action_flag=CHANGE,
            change_message=f"Status changed to {instance.status}: {instance.comment}"
        ) 