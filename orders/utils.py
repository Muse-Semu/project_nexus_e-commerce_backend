from django.db import transaction
from django.utils import timezone
from .models import Order, OrderItem, OrderStatus
from carts.models import CheckoutSession
import logging

logger = logging.getLogger(__name__)


def create_order_from_checkout(checkout_session, customer_notes=''):
    """
    Create an order from a checkout session
    """
    try:
        with transaction.atomic():
            # Create order
            order = Order.objects.create(
                customer=checkout_session.user,
                shipping_address=checkout_session.shipping_address,
                billing_address=checkout_session.billing_address,
                shipping_phone=checkout_session.shipping_phone,
                payment_method=checkout_session.payment_method,
                transaction_id=checkout_session.transaction_id,
                subtotal=checkout_session.subtotal,
                discount_amount=checkout_session.discount_amount,
                shipping_cost=checkout_session.shipping_cost,
                tax_amount=checkout_session.tax_amount,
                total_amount=checkout_session.total_amount,
                customer_notes=customer_notes
            )
            
            # Create order items from cart
            for cart_item in checkout_session.cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product=cart_item.product,
                    variant=cart_item.variant,
                    quantity=cart_item.quantity,
                    unit_price=cart_item.unit_price,
                    product_name=cart_item.product.name,
                    product_sku=cart_item.product.sku,
                    variant_name=cart_item.variant.name if cart_item.variant else ''
                )
            
            # Create initial status
            OrderStatus.objects.create(
                order=order,
                status='pending',
                comment='Order created from checkout session'
            )
            
            # Update checkout session status
            checkout_session.status = 'completed'
            checkout_session.save()
            
            logger.info(f"Order {order.order_number} created from checkout session {checkout_session.id}")
            
            return order
            
    except Exception as e:
        logger.error(f"Failed to create order from checkout session: {str(e)}")
        raise


def update_order_status(order, new_status, comment='', created_by=None):
    """
    Update order status and create status history
    """
    try:
        with transaction.atomic():
            old_status = order.status
            order.status = new_status
            
            # Update timestamp based on status
            if new_status == 'confirmed':
                order.confirmed_at = timezone.now()
            elif new_status == 'shipped':
                order.shipped_at = timezone.now()
            elif new_status == 'delivered':
                order.delivered_at = timezone.now()
            elif new_status == 'cancelled':
                order.cancelled_at = timezone.now()
            
            order.save()
            
            # Create status history
            OrderStatus.objects.create(
                order=order,
                status=new_status,
                comment=comment,
                created_by=created_by
            )
            
            logger.info(f"Order {order.order_number} status changed from {old_status} to {new_status}")
            
            return order
            
    except Exception as e:
        logger.error(f"Failed to update order status: {str(e)}")
        raise


def calculate_order_totals(order):
    """
    Recalculate order totals based on items
    """
    try:
        subtotal = sum(item.total_price for item in order.items.all())
        
        # Apply discount if any
        discount_amount = order.discount_amount
        
        # Calculate final total
        total_amount = subtotal - discount_amount + order.shipping_cost + order.tax_amount
        
        # Update order
        order.subtotal = subtotal
        order.total_amount = total_amount
        order.save()
        
        logger.info(f"Order {order.order_number} totals recalculated: ${total_amount:.2f}")
        
        return {
            'subtotal': subtotal,
            'discount_amount': discount_amount,
            'shipping_cost': order.shipping_cost,
            'tax_amount': order.tax_amount,
            'total_amount': total_amount
        }
        
    except Exception as e:
        logger.error(f"Failed to calculate order totals: {str(e)}")
        raise


def validate_order_can_be_cancelled(order):
    """
    Validate if an order can be cancelled
    """
    return order.status in ['pending', 'confirmed', 'processing']


def validate_order_can_be_returned(order):
    """
    Validate if an order can be returned
    """
    if order.status != 'delivered':
        return False
    
    if not order.delivered_at:
        return False
    
    # Check if within return window (30 days)
    from datetime import timedelta
    return timezone.now() - order.delivered_at < timedelta(days=30)


def get_order_analytics(start_date=None, end_date=None):
    """
    Get order analytics for a date range
    """
    from django.db.models import Sum, Count, Avg
    
    if not start_date:
        start_date = timezone.now() - timedelta(days=30)
    if not end_date:
        end_date = timezone.now()
    
    orders = Order.objects.filter(
        created_at__range=[start_date, end_date]
    )
    
    # Basic metrics
    total_orders = orders.count()
    total_revenue = orders.filter(payment_status='paid').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    average_order_value = orders.filter(payment_status='paid').aggregate(
        avg=Avg('total_amount')
    )['avg'] or 0
    
    # Orders by status
    orders_by_status = orders.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Revenue by day
    revenue_by_day = orders.filter(payment_status='paid').extra(
        select={'day': "DATE(created_at)"}
    ).values('day').annotate(
        revenue=Sum('total_amount')
    ).order_by('day')
    
    return {
        'total_orders': total_orders,
        'total_revenue': total_revenue,
        'average_order_value': average_order_value,
        'orders_by_status': {item['status']: item['count'] for item in orders_by_status},
        'revenue_by_day': {item['day']: item['revenue'] for item in revenue_by_day}
    } 