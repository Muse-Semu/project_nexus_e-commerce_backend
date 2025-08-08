from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from products.models import Product, ProductVariant
from carts.models import CheckoutSession
import uuid

User = get_user_model()


class Order(models.Model):
    """
    Main order model for managing customer orders
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('processing', 'Processing'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
        ('returned', 'Returned'),
    )
    
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('partially_refunded', 'Partially Refunded'),
    )
    
    # Order identification
    order_number = models.CharField(max_length=50, unique=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Customer information
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    
    # Order details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    
    # Addresses
    shipping_address = models.TextField()
    billing_address = models.TextField()
    shipping_phone = models.CharField(max_length=20)
    
    # Payment information
    payment_method = models.CharField(max_length=50, default='chapa')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Shipping information
    tracking_number = models.CharField(max_length=100, null=True, blank=True)
    shipping_carrier = models.CharField(max_length=50, null=True, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    
    # Notes
    customer_notes = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'orders_order'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['customer']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Order {self.order_number}"
    
    def save(self, *args, **kwargs):
        # Generate order number if not provided
        if not self.order_number:
            self.order_number = self._generate_order_number()
        super().save(*args, **kwargs)
    
    def _generate_order_number(self):
        """Generate unique order number"""
        import random
        import string
        
        # Format: ORD-YYYYMMDD-XXXXX
        from django.utils import timezone
        date_str = timezone.now().strftime('%Y%m%d')
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return f"ORD-{date_str}-{random_str}"
    
    @property
    def total_items(self):
        """Return total number of items in order"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def is_paid(self):
        """Check if order is paid"""
        return self.payment_status in ['paid', 'refunded', 'partially_refunded']
    
    @property
    def can_cancel(self):
        """Check if order can be cancelled"""
        return self.status in ['pending', 'confirmed', 'processing']
    
    @property
    def can_return(self):
        """Check if order can be returned"""
        if self.status == 'delivered' and self.delivered_at:
            from django.utils import timezone
            from datetime import timedelta
            return timezone.now() - self.delivered_at < timedelta(days=30)
        return False


class OrderItem(models.Model):
    """
    Individual items in an order
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Product snapshot (in case product is deleted/modified)
    product_name = models.CharField(max_length=200)
    product_sku = models.CharField(max_length=100)
    variant_name = models.CharField(max_length=100, blank=True)
    
    class Meta:
        db_table = 'orders_orderitem'
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['product']),
        ]
    
    def __str__(self):
        variant_text = f" - {self.variant_name}" if self.variant_name else ""
        return f"{self.quantity}x {self.product_name}{variant_text}"
    
    def save(self, *args, **kwargs):
        # Calculate total price
        self.total_price = self.unit_price * self.quantity
        
        # Snapshot product details
        if not self.product_name:
            self.product_name = self.product.name
        if not self.product_sku:
            self.product_sku = self.product.sku
        if self.variant and not self.variant_name:
            self.variant_name = self.variant.name
        
        super().save(*args, **kwargs)


class OrderStatus(models.Model):
    """
    Order status history for tracking order changes
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES)
    comment = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'orders_orderstatus'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.order.order_number} - {self.status}"


class Return(models.Model):
    """
    Return/refund management
    """
    REASON_CHOICES = (
        ('defective', 'Defective Product'),
        ('wrong_item', 'Wrong Item Received'),
        ('not_as_described', 'Not As Described'),
        ('size_issue', 'Size/Fit Issue'),
        ('quality_issue', 'Quality Issue'),
        ('other', 'Other'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    )
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns')
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='returns')
    reason = models.CharField(max_length=20, choices=REASON_CHOICES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Refund information
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    refund_method = models.CharField(max_length=50, null=True, blank=True)
    refund_transaction_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Admin information
    admin_notes = models.TextField(blank=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_returns')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'orders_return'
        indexes = [
            models.Index(fields=['order']),
            models.Index(fields=['customer']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Return for Order {self.order.order_number}"


class ReturnItem(models.Model):
    """
    Items being returned
    """
    return_request = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='items')
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reason = models.CharField(max_length=20, choices=Return.REASON_CHOICES)
    
    class Meta:
        db_table = 'orders_returnitem'
        indexes = [
            models.Index(fields=['return_request']),
            models.Index(fields=['order_item']),
        ]
    
    def __str__(self):
        return f"{self.quantity}x {self.order_item.product_name}"


class ShippingLabel(models.Model):
    """
    Shipping label information
    """
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='shipping_label')
    label_url = models.URLField()
    tracking_number = models.CharField(max_length=100)
    carrier = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'orders_shippinglabel'
    
    def __str__(self):
        return f"Shipping label for {self.order.order_number}"
