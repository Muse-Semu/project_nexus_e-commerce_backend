from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

from .models import Order, OrderStatus, Return
from users.tasks import send_email_notification

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_order_confirmation_email(self, order_id):
    """
    Send order confirmation email to customer
    """
    try:
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Confirmed - {order.order_number}"
        message = f"""
        Dear {order.customer.first_name},
        
        Your order {order.order_number} has been confirmed and is being processed.
        
        Order Details:
        - Total Amount: ${order.total_amount}
        - Items: {order.total_items}
        - Status: {order.get_status_display()}
        
        We will notify you when your order ships.
        
        Thank you for your purchase!
        """
        
        send_email_notification.delay(
            order.customer.email,
            subject,
            message,
            template_name='emails/order_confirmation.html',
            context={
                'order': order,
                'customer': order.customer
            }
        )
        
        logger.info(f"Order confirmation email sent for order {order.order_number}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for confirmation email")
    except Exception as e:
        logger.error(f"Failed to send order confirmation email: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, max_retries=3)
def send_order_shipped_email(self, order_id):
    """
    Send order shipped email to customer
    """
    try:
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Shipped - {order.order_number}"
        message = f"""
        Dear {order.customer.first_name},
        
        Your order {order.order_number} has been shipped!
        
        Tracking Information:
        - Tracking Number: {order.tracking_number}
        - Carrier: {order.shipping_carrier}
        - Estimated Delivery: {order.estimated_delivery}
        
        You can track your package using the tracking number above.
        
        Thank you for your patience!
        """
        
        send_email_notification.delay(
            order.customer.email,
            subject,
            message,
            template_name='emails/order_shipped.html',
            context={
                'order': order,
                'customer': order.customer
            }
        )
        
        logger.info(f"Order shipped email sent for order {order.order_number}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for shipped email")
    except Exception as e:
        logger.error(f"Failed to send order shipped email: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, max_retries=3)
def send_order_delivered_email(self, order_id):
    """
    Send order delivered email to customer
    """
    try:
        order = Order.objects.get(id=order_id)
        
        subject = f"Order Delivered - {order.order_number}"
        message = f"""
        Dear {order.customer.first_name},
        
        Your order {order.order_number} has been delivered!
        
        We hope you enjoy your purchase. If you have any issues with your order, 
        please don't hesitate to contact our customer service team.
        
        Thank you for choosing us!
        """
        
        send_email_notification.delay(
            order.customer.email,
            subject,
            message,
            template_name='emails/order_delivered.html',
            context={
                'order': order,
                'customer': order.customer
            }
        )
        
        logger.info(f"Order delivered email sent for order {order.order_number}")
        
    except Order.DoesNotExist:
        logger.error(f"Order {order_id} not found for delivered email")
    except Exception as e:
        logger.error(f"Failed to send order delivered email: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, max_retries=3)
def send_return_approval_email(self, return_id):
    """
    Send return approval email to customer
    """
    try:
        return_request = Return.objects.get(id=return_id)
        
        subject = f"Return Approved - Order {return_request.order.order_number}"
        message = f"""
        Dear {return_request.customer.first_name},
        
        Your return request for order {return_request.order.order_number} has been approved.
        
        Return Details:
        - Reason: {return_request.get_reason_display()}
        - Refund Amount: ${return_request.refund_amount}
        - Status: {return_request.get_status_display()}
        
        Your refund will be processed within 5-7 business days.
        
        Thank you for your patience!
        """
        
        send_email_notification.delay(
            return_request.customer.email,
            subject,
            message,
            template_name='emails/return_approved.html',
            context={
                'return_request': return_request,
                'customer': return_request.customer
            }
        )
        
        logger.info(f"Return approval email sent for return {return_request.id}")
        
    except Return.DoesNotExist:
        logger.error(f"Return {return_id} not found for approval email")
    except Exception as e:
        logger.error(f"Failed to send return approval email: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task(bind=True, max_retries=3)
def send_return_rejection_email(self, return_id):
    """
    Send return rejection email to customer
    """
    try:
        return_request = Return.objects.get(id=return_id)
        
        subject = f"Return Request Update - Order {return_request.order.order_number}"
        message = f"""
        Dear {return_request.customer.first_name},
        
        Your return request for order {return_request.order.order_number} has been reviewed.
        
        Unfortunately, we cannot approve your return request at this time.
        
        Reason: {return_request.admin_notes}
        
        If you have any questions, please contact our customer service team.
        
        Thank you for understanding.
        """
        
        send_email_notification.delay(
            return_request.customer.email,
            subject,
            message,
            template_name='emails/return_rejected.html',
            context={
                'return_request': return_request,
                'customer': return_request.customer
            }
        )
        
        logger.info(f"Return rejection email sent for return {return_request.id}")
        
    except Return.DoesNotExist:
        logger.error(f"Return {return_id} not found for rejection email")
    except Exception as e:
        logger.error(f"Failed to send return rejection email: {str(e)}")
        raise self.retry(countdown=60, max_retries=3)


@shared_task
def check_delayed_orders():
    """
    Check for orders that are taking too long to process
    """
    try:
        # Find orders that have been pending for more than 24 hours
        delayed_orders = Order.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timedelta(hours=24)
        )
        
        for order in delayed_orders:
            logger.warning(f"Order {order.order_number} has been pending for more than 24 hours")
            
            # Send notification to admin
            subject = f"Delayed Order Alert - {order.order_number}"
            message = f"""
            Order {order.order_number} has been pending for more than 24 hours.
            
            Customer: {order.customer.email}
            Amount: ${order.total_amount}
            Created: {order.created_at}
            
            Please review and process this order.
            """
            
            # Send to admin email
            admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [admin_email],
                fail_silently=True
            )
        
        logger.info(f"Checked {delayed_orders.count()} delayed orders")
        
    except Exception as e:
        logger.error(f"Failed to check delayed orders: {str(e)}")


@shared_task
def generate_order_report():
    """
    Generate daily order report
    """
    try:
        from django.db.models import Sum, Count
        from datetime import datetime
        
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Get yesterday's orders
        orders = Order.objects.filter(
            created_at__date=yesterday
        )
        
        # Calculate metrics
        total_orders = orders.count()
        total_revenue = orders.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        orders_by_status = orders.values('status').annotate(
            count=Count('id')
        )
        
        # Generate report
        report = f"""
        Daily Order Report - {yesterday}
        
        Total Orders: {total_orders}
        Total Revenue: ${total_revenue:.2f}
        
        Orders by Status:
        """
        
        for status_data in orders_by_status:
            status = status_data['status']
            count = status_data['count']
            report += f"- {status}: {count}\n"
        
        # Send report to admin
        subject = f"Daily Order Report - {yesterday}"
        
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'admin@example.com')
        send_mail(
            subject,
            report,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=True
        )
        
        logger.info(f"Daily order report generated for {yesterday}")
        
    except Exception as e:
        logger.error(f"Failed to generate order report: {str(e)}")


@shared_task
def cleanup_expired_orders():
    """
    Clean up expired orders (cancelled orders older than 30 days)
    """
    try:
        from datetime import timedelta
        
        # Find cancelled orders older than 30 days
        expired_orders = Order.objects.filter(
            status='cancelled',
            cancelled_at__lt=timezone.now() - timedelta(days=30)
        )
        
        count = expired_orders.count()
        expired_orders.delete()
        
        logger.info(f"Cleaned up {count} expired orders")
        
    except Exception as e:
        logger.error(f"Failed to cleanup expired orders: {str(e)}") 