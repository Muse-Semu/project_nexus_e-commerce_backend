from django.shortcuts import render
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.db.models import Q, Sum, Count
from datetime import datetime, timedelta
import logging

from .models import Order, OrderItem, OrderStatus, Return, ReturnItem, ShippingLabel
from .serializers import (
    OrderSerializer, OrderCreateSerializer, OrderUpdateSerializer, OrderSummarySerializer,
    ReturnSerializer, ReturnCreateSerializer, ReturnUpdateSerializer,
    ShippingLabelSerializer, OrderAnalyticsSerializer
)
from users.permissions import IsOwnerOrAdmin

User = get_user_model()
logger = logging.getLogger(__name__)


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet for order management
    """
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get orders based on user role"""
        user = self.request.user
        
        if user.is_admin():
            return Order.objects.all()
        elif user.is_vendor():
            # Vendors see orders for their products
            return Order.objects.filter(items__product__vendor=user).distinct()
        else:
            # Customers see their own orders
            return Order.objects.filter(customer=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderUpdateSerializer
        elif self.action == 'list':
            return OrderSummarySerializer
        return OrderSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        elif self.action in ['analytics', 'bulk_update']:
            return [IsAdminUser()]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def my_orders(self, request):
        """Get current user's orders"""
        orders = Order.objects.filter(customer=request.user)
        serializer = OrderSummarySerializer(orders, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel an order"""
        order = self.get_object()
        
        if not order.can_cancel:
            return Response(
                {'error': 'Order cannot be cancelled'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            order.status = 'cancelled'
            order.cancelled_at = timezone.now()
            order.save()
            
            # Create status history
            OrderStatus.objects.create(
                order=order,
                status='cancelled',
                comment=request.data.get('comment', 'Order cancelled by customer'),
                created_by=request.user
            )
            
            # Restore stock if order was confirmed/processing
            if order.status in ['confirmed', 'processing']:
                for item in order.items.all():
                    if item.variant:
                        item.variant.stock_quantity += item.quantity
                        item.variant.save()
                    else:
                        item.product.stock_quantity += item.quantity
                        item.product.save()
        
        return Response({'message': 'Order cancelled successfully'})
    
    @action(detail=True, methods=['post'])
    def confirm(self, request, pk=None):
        """Confirm an order (admin only)"""
        order = self.get_object()
        
        if order.status != 'pending':
            return Response(
                {'error': 'Order is not in pending status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            # Create status history
            OrderStatus.objects.create(
                order=order,
                status='confirmed',
                comment=request.data.get('comment', 'Order confirmed'),
                created_by=request.user
            )
            
            # Deduct stock
            for item in order.items.all():
                if item.variant:
                    if item.variant.stock_quantity < item.quantity:
                        return Response(
                            {'error': f'Insufficient stock for {item.product.name}'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    item.variant.stock_quantity -= item.quantity
                    item.variant.save()
                else:
                    if item.product.stock_quantity < item.quantity:
                        return Response(
                            {'error': f'Insufficient stock for {item.product.name}'}, 
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    item.product.stock_quantity -= item.quantity
                    item.product.save()
        
        return Response({'message': 'Order confirmed successfully'})
    
    @action(detail=True, methods=['post'])
    def ship(self, request, pk=None):
        """Ship an order (admin only)"""
        order = self.get_object()
        
        if order.status != 'confirmed':
            return Response(
                {'error': 'Order must be confirmed before shipping'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tracking_number = request.data.get('tracking_number')
        shipping_carrier = request.data.get('shipping_carrier')
        
        if not tracking_number or not shipping_carrier:
            return Response(
                {'error': 'Tracking number and shipping carrier are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            order.status = 'shipped'
            order.shipped_at = timezone.now()
            order.tracking_number = tracking_number
            order.shipping_carrier = shipping_carrier
            order.save()
            
            # Create status history
            OrderStatus.objects.create(
                order=order,
                status='shipped',
                comment=f'Order shipped via {shipping_carrier}. Tracking: {tracking_number}',
                created_by=request.user
            )
        
        return Response({'message': 'Order shipped successfully'})
    
    @action(detail=True, methods=['post'])
    def deliver(self, request, pk=None):
        """Mark order as delivered (admin only)"""
        order = self.get_object()
        
        if order.status != 'shipped':
            return Response(
                {'error': 'Order must be shipped before marking as delivered'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            order.status = 'delivered'
            order.delivered_at = timezone.now()
            order.save()
            
            # Create status history
            OrderStatus.objects.create(
                order=order,
                status='delivered',
                comment='Order delivered successfully',
                created_by=request.user
            )
        
        return Response({'message': 'Order marked as delivered'})
    
    @action(detail=False, methods=['get'])
    def analytics(self, request):
        """Get order analytics (admin only)"""
        # Get date range
        end_date = timezone.now()
        start_date = end_date - timedelta(days=30)
        
        # Calculate metrics
        orders = Order.objects.filter(created_at__range=[start_date, end_date])
        
        total_orders = orders.count()
        total_revenue = orders.filter(payment_status='paid').aggregate(
            total=Sum('total_amount')
        )['total'] or 0
        
        average_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # Orders by status
        orders_by_status = orders.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Revenue by month
        revenue_by_month = orders.filter(payment_status='paid').extra(
            select={'month': "EXTRACT(month FROM created_at)"}
        ).values('month').annotate(
            revenue=Sum('total_amount')
        ).order_by('month')
        
        # Top products
        top_products = OrderItem.objects.filter(
            order__created_at__range=[start_date, end_date]
        ).values('product__name').annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('total_price')
        ).order_by('-total_quantity')[:10]
        
        data = {
            'total_orders': total_orders,
            'total_revenue': total_revenue,
            'average_order_value': average_order_value,
            'orders_by_status': {item['status']: item['count'] for item in orders_by_status},
            'revenue_by_month': {item['month']: item['revenue'] for item in revenue_by_month},
            'top_products': list(top_products)
        }
        
        serializer = OrderAnalyticsSerializer(data)
        return Response(serializer.data)


class ReturnViewSet(viewsets.ModelViewSet):
    """
    ViewSet for return management
    """
    serializer_class = ReturnSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get returns based on user role"""
        user = self.request.user
        
        if user.is_admin():
            return Return.objects.all()
        else:
            return Return.objects.filter(customer=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReturnCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return ReturnUpdateSerializer
        return ReturnSerializer
    
    def get_permissions(self):
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsOwnerOrAdmin()]
        return super().get_permissions()
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve return request (admin only)"""
        return_request = self.get_object()
        
        if return_request.status != 'pending':
            return Response(
                {'error': 'Return request is not in pending status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund_amount = request.data.get('refund_amount')
        if not refund_amount:
            return Response(
                {'error': 'Refund amount is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            return_request.status = 'approved'
            return_request.refund_amount = refund_amount
            return_request.processed_by = request.user
            return_request.processed_at = timezone.now()
            return_request.save()
            
            # Update order status
            order = return_request.order
            order.status = 'returned'
            order.save()
            
            # Create order status history
            OrderStatus.objects.create(
                order=order,
                status='returned',
                comment=f'Return approved. Refund amount: ${refund_amount}',
                created_by=request.user
            )
        
        return Response({'message': 'Return request approved'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject return request (admin only)"""
        return_request = self.get_object()
        
        if return_request.status != 'pending':
            return Response(
                {'error': 'Return request is not in pending status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reason = request.data.get('reason', 'Return request rejected')
        
        with transaction.atomic():
            return_request.status = 'rejected'
            return_request.processed_by = request.user
            return_request.processed_at = timezone.now()
            return_request.admin_notes = reason
            return_request.save()
        
        return Response({'message': 'Return request rejected'})
    
    @action(detail=True, methods=['post'])
    def process_refund(self, request, pk=None):
        """Process refund for approved return (admin only)"""
        return_request = self.get_object()
        
        if return_request.status != 'approved':
            return Response(
                {'error': 'Return request must be approved before processing refund'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        refund_method = request.data.get('refund_method')
        if not refund_method:
            return Response(
                {'error': 'Refund method is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        with transaction.atomic():
            return_request.status = 'processing'
            return_request.refund_method = refund_method
            return_request.save()
            
            # TODO: Integrate with payment gateway for actual refund
            # For now, just mark as completed
            return_request.status = 'completed'
            return_request.save()
        
        return Response({'message': 'Refund processed successfully'})


class ShippingLabelViewSet(viewsets.ModelViewSet):
    """
    ViewSet for shipping label management
    """
    queryset = ShippingLabel.objects.all()
    serializer_class = ShippingLabelSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Get shipping labels for orders"""
        order_id = self.request.query_params.get('order')
        if order_id:
            return ShippingLabel.objects.filter(order_id=order_id)
        return ShippingLabel.objects.all()
