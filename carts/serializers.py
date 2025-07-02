from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Cart, CartItem, Coupon, CartCoupon, CheckoutSession
from products.serializers import ProductSerializer, ProductVariantSerializer

User = get_user_model()


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer for cart items
    """
    product = ProductSerializer(read_only=True)
    variant = ProductVariantSerializer(read_only=True)
    unit_price = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()
    
    class Meta:
        model = CartItem
        fields = (
            'id', 'product', 'variant', 'quantity', 
            'unit_price', 'total_price', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'unit_price', 'total_price', 'created_at', 'updated_at')


class CartItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating cart items
    """
    class Meta:
        model = CartItem
        fields = ('product', 'variant', 'quantity')
    
    def validate(self, attrs):
        product = attrs['product']
        variant = attrs.get('variant')
        quantity = attrs['quantity']
        
        # Check if product is active
        if not product.is_active:
            raise serializers.ValidationError("Cannot add inactive product to cart")
        
        # Check stock availability
        if variant:
            available_stock = variant.stock_quantity
        else:
            available_stock = product.stock_quantity
        
        if quantity > available_stock:
            raise serializers.ValidationError(f"Only {available_stock} items available in stock")
        
        if available_stock == 0:
            raise serializers.ValidationError("Product is out of stock")
        
        return attrs


class CouponSerializer(serializers.ModelSerializer):
    """
    Serializer for coupons
    """
    is_valid = serializers.ReadOnlyField()
    
    class Meta:
        model = Coupon
        fields = (
            'id', 'code', 'description', 'discount_type', 'discount_value',
            'minimum_amount', 'maximum_discount', 'usage_limit', 'used_count',
            'is_active', 'valid_from', 'valid_until', 'is_valid', 'created_at'
        )
        read_only_fields = ('id', 'used_count', 'created_at')


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer for shopping cart
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    total_amount = serializers.ReadOnlyField()
    is_empty = serializers.ReadOnlyField()
    applied_coupon = CouponSerializer(read_only=True)
    discount_amount = serializers.SerializerMethodField()
    final_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = Cart
        fields = (
            'id', 'user', 'session_key', 'items', 'total_items', 
            'total_amount', 'is_empty', 'applied_coupon', 'discount_amount',
            'final_amount', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'session_key', 'created_at', 'updated_at')
    
    def get_discount_amount(self, obj):
        """Calculate discount amount from applied coupon"""
        if hasattr(obj, 'applied_coupon') and obj.applied_coupon:
            return obj.applied_coupon.coupon.calculate_discount(obj.total_amount)
        return 0
    
    def get_final_amount(self, obj):
        """Calculate final amount after discount"""
        discount = self.get_discount_amount(obj)
        return max(0, obj.total_amount - discount)


class CartCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating carts
    """
    class Meta:
        model = Cart
        fields = ('user', 'session_key')


class ApplyCouponSerializer(serializers.Serializer):
    """
    Serializer for applying coupons to cart
    """
    code = serializers.CharField(max_length=20)
    
    def validate_code(self, value):
        """Validate coupon code"""
        try:
            coupon = Coupon.objects.get(code=value)
            if not coupon.is_valid():
                raise serializers.ValidationError("Coupon is not valid or has expired")
            return value
        except Coupon.DoesNotExist:
            raise serializers.ValidationError("Invalid coupon code")


class CartSummarySerializer(serializers.ModelSerializer):
    """
    Serializer for cart summary (used in checkout)
    """
    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    subtotal = serializers.ReadOnlyField(source='total_amount')
    discount_amount = serializers.SerializerMethodField()
    final_amount = serializers.SerializerMethodField()
    applied_coupon = CouponSerializer(read_only=True)
    
    class Meta:
        model = Cart
        fields = (
            'id', 'items', 'total_items', 'subtotal', 'discount_amount',
            'final_amount', 'applied_coupon'
        )
    
    def get_discount_amount(self, obj):
        """Calculate discount amount"""
        if hasattr(obj, 'applied_coupon') and obj.applied_coupon:
            return obj.applied_coupon.coupon.calculate_discount(obj.total_amount)
        return 0
    
    def get_final_amount(self, obj):
        """Calculate final amount after discount"""
        discount = self.get_discount_amount(obj)
        return max(0, obj.total_amount - discount)


class CheckoutSessionSerializer(serializers.ModelSerializer):
    """
    Serializer for checkout sessions
    """
    cart = CartSummarySerializer(read_only=True)
    
    class Meta:
        model = CheckoutSession
        fields = (
            'id', 'user', 'session_key', 'cart', 'status', 'shipping_address',
            'billing_address', 'shipping_phone', 'payment_method', 'payment_status',
            'transaction_id', 'subtotal', 'discount_amount', 'shipping_cost',
            'tax_amount', 'total_amount', 'created_at', 'updated_at', 'expires_at'
        )
        read_only_fields = ('id', 'user', 'session_key', 'status', 'payment_status',
                           'transaction_id', 'subtotal', 'discount_amount', 'shipping_cost',
                           'tax_amount', 'total_amount', 'created_at', 'updated_at', 'expires_at')


class CheckoutCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating checkout sessions
    """
    class Meta:
        model = CheckoutSession
        fields = ('shipping_address', 'billing_address', 'shipping_phone', 'payment_method')
    
    def validate(self, attrs):
        """Validate checkout data"""
        # Validate phone number format
        phone = attrs.get('shipping_phone', '')
        if not phone or len(phone) < 10:
            raise serializers.ValidationError("Valid phone number is required")
        
        # Validate addresses
        shipping_address = attrs.get('shipping_address', '')
        billing_address = attrs.get('billing_address', '')
        
        if not shipping_address or len(shipping_address.strip()) < 10:
            raise serializers.ValidationError("Valid shipping address is required")
        
        if not billing_address or len(billing_address.strip()) < 10:
            raise serializers.ValidationError("Valid billing address is required")
        
        return attrs


class PaymentInitiateSerializer(serializers.Serializer):
    """
    Serializer for initiating payment
    """
    checkout_session_id = serializers.UUIDField()
    
    def validate_checkout_session_id(self, value):
        """Validate checkout session"""
        try:
            checkout_session = CheckoutSession.objects.get(id=value)
            if checkout_session.is_expired():
                raise serializers.ValidationError("Checkout session has expired")
            if checkout_session.status != 'pending':
                raise serializers.ValidationError("Checkout session is not in pending status")
            return value
        except CheckoutSession.DoesNotExist:
            raise serializers.ValidationError("Invalid checkout session") 