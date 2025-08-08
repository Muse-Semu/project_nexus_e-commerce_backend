from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Order, OrderItem, OrderStatus, Return, ReturnItem, ShippingLabel
from products.serializers import ProductSerializer, ProductVariantSerializer

User = get_user_model()


class OrderItemSerializer(serializers.ModelSerializer):
    """
    Serializer for order items
    """
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    
    class Meta:
        model = OrderItem
        fields = (
            'id', 'product', 'variant', 'quantity', 'unit_price', 'total_price',
            'product_name', 'product_sku', 'variant_name'
        )
        read_only_fields = ('id', 'unit_price', 'total_price', 'product_name', 'product_sku', 'variant_name')


class OrderStatusSerializer(serializers.ModelSerializer):
    """
    Serializer for order status history
    """
    created_by = serializers.ReadOnlyField(source='created_by.email')
    
    class Meta:
        model = OrderStatus
        fields = ('id', 'status', 'comment', 'created_by', 'created_at')
        read_only_fields = ('id', 'created_by', 'created_at')


class OrderSerializer(serializers.ModelSerializer):
    """
    Serializer for orders
    """
    items = OrderItemSerializer(many=True, read_only=True)
    status_history = OrderStatusSerializer(many=True, read_only=True)
    customer = serializers.ReadOnlyField(source='customer.email')
    total_items = serializers.ReadOnlyField()
    is_paid = serializers.ReadOnlyField()
    can_cancel = serializers.ReadOnlyField()
    can_return = serializers.ReadOnlyField()
    
    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'status', 'payment_status',
            'shipping_address', 'billing_address', 'shipping_phone',
            'payment_method', 'transaction_id', 'subtotal', 'discount_amount',
            'shipping_cost', 'tax_amount', 'total_amount', 'tracking_number',
            'shipping_carrier', 'estimated_delivery', 'items', 'status_history',
            'total_items', 'is_paid', 'can_cancel', 'can_return',
            'customer_notes', 'admin_notes', 'created_at', 'updated_at',
            'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'
        )
        read_only_fields = (
            'id', 'order_number', 'customer', 'transaction_id', 'subtotal',
            'discount_amount', 'shipping_cost', 'tax_amount', 'total_amount',
            'tracking_number', 'shipping_carrier', 'estimated_delivery',
            'created_at', 'updated_at', 'confirmed_at', 'shipped_at',
            'delivered_at', 'cancelled_at'
        )


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating orders from checkout session
    """
    class Meta:
        model = Order
        fields = ('customer_notes',)
    
    def create(self, validated_data):
        """Create order from checkout session"""
        checkout_session = self.context.get('checkout_session')
        if not checkout_session:
            raise serializers.ValidationError("Checkout session is required")
        
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
            customer_notes=validated_data.get('customer_notes', '')
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
        
        return order


class OrderUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating orders (admin only)
    """
    class Meta:
        model = Order
        fields = (
            'status', 'payment_status', 'tracking_number', 'shipping_carrier',
            'estimated_delivery', 'admin_notes'
        )


class ReturnItemSerializer(serializers.ModelSerializer):
    """
    Serializer for return items
    """
    order_item = OrderItemSerializer(read_only=True)
    
    class Meta:
        model = ReturnItem
        fields = ('id', 'order_item', 'quantity', 'reason')
        read_only_fields = ('id',)


class ReturnSerializer(serializers.ModelSerializer):
    """
    Serializer for returns
    """
    items = ReturnItemSerializer(many=True, read_only=True)
    customer = serializers.ReadOnlyField(source='customer.email')
    processed_by = serializers.ReadOnlyField(source='processed_by.email')
    
    class Meta:
        model = Return
        fields = (
            'id', 'order', 'customer', 'reason', 'description', 'status',
            'refund_amount', 'refund_method', 'refund_transaction_id',
            'admin_notes', 'processed_by', 'items', 'created_at', 'updated_at',
            'processed_at'
        )
        read_only_fields = (
            'id', 'customer', 'refund_amount', 'refund_method', 
            'refund_transaction_id', 'admin_notes', 'processed_by',
            'created_at', 'updated_at', 'processed_at'
        )


class ReturnCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating returns
    """
    items = ReturnItemSerializer(many=True)
    
    class Meta:
        model = Return
        fields = ('order', 'reason', 'description', 'items')
    
    def validate(self, attrs):
        """Validate return request"""
        order = attrs['order']
        
        # Check if order can be returned
        if not order.can_return:
            raise serializers.ValidationError("This order cannot be returned")
        
        # Check if return already exists
        if Return.objects.filter(order=order, status__in=['pending', 'approved', 'processing']).exists():
            raise serializers.ValidationError("A return request already exists for this order")
        
        return attrs
    
    def create(self, validated_data):
        """Create return request"""
        items_data = validated_data.pop('items')
        return_request = Return.objects.create(**validated_data)
        
        # Create return items
        for item_data in items_data:
            ReturnItem.objects.create(return_request=return_request, **item_data)
        
        return return_request


class ReturnUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating returns (admin only)
    """
    class Meta:
        model = Return
        fields = ('status', 'refund_amount', 'refund_method', 'refund_transaction_id', 'admin_notes')


class ShippingLabelSerializer(serializers.ModelSerializer):
    """
    Serializer for shipping labels
    """
    order = OrderSerializer(read_only=True)
    
    class Meta:
        model = ShippingLabel
        fields = ('id', 'order', 'label_url', 'tracking_number', 'carrier', 'created_at')
        read_only_fields = ('id', 'created_at')


class OrderSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for order summary (used in lists)
    """
    total_items = serializers.ReadOnlyField()
    customer = serializers.ReadOnlyField(source='customer.email')
    
    class Meta:
        model = Order
        fields = (
            'id', 'order_number', 'customer', 'status', 'payment_status',
            'total_amount', 'total_items', 'created_at'
        )
        read_only_fields = ('id', 'order_number', 'customer', 'total_amount', 'total_items', 'created_at')


class OrderAnalyticsSerializer(serializers.Serializer):
    """
    Serializer for order analytics
    """
    total_orders = serializers.IntegerField()
    total_revenue = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_order_value = serializers.DecimalField(max_digits=10, decimal_places=2)
    orders_by_status = serializers.DictField()
    revenue_by_month = serializers.DictField()
    top_products = serializers.ListField() 