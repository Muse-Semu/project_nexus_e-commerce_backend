from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from products.models import Product, ProductVariant
import uuid

User = get_user_model()


class Cart(models.Model):
    """
    Shopping cart model that can be associated with users or sessions
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='carts')
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts_cart'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        if self.user:
            return f"Cart for {self.user.email}"
        return f"Session cart: {self.session_key}"
    
    @property
    def total_items(self):
        """Return total number of items in cart"""
        return sum(item.quantity for item in self.items.all())
    
    @property
    def total_amount(self):
        """Calculate total amount of cart"""
        return sum(item.total_price for item in self.items.all())
    
    @property
    def is_empty(self):
        """Check if cart is empty"""
        return self.items.count() == 0


class CartItem(models.Model):
    """
    Individual items in a shopping cart
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'carts_cartitem'
        unique_together = ['cart', 'product', 'variant']
        indexes = [
            models.Index(fields=['cart']),
            models.Index(fields=['product']),
            models.Index(fields=['variant']),
        ]
    
    def __str__(self):
        variant_text = f" - {self.variant.name}" if self.variant else ""
        return f"{self.quantity}x {self.product.name}{variant_text}"
    
    @property
    def unit_price(self):
        """Get the unit price (product price + variant adjustment)"""
        if self.variant:
            return self.variant.current_price
        return self.product.current_price
    
    @property
    def total_price(self):
        """Calculate total price for this item"""
        return self.unit_price * self.quantity
    
    def clean(self):
        """Validate cart item"""
        from django.core.exceptions import ValidationError
        
        # Check if product is active
        if not self.product.is_active:
            raise ValidationError("Cannot add inactive product to cart")
        
        # Check stock availability
        if self.variant:
            available_stock = self.variant.stock_quantity
        else:
            available_stock = self.product.stock_quantity
        
        if self.quantity > available_stock:
            raise ValidationError(f"Only {available_stock} items available in stock")
        
        # Check if product is out of stock
        if available_stock == 0:
            raise ValidationError("Product is out of stock")


class Coupon(models.Model):
    """
    Coupon model for discounts
    """
    DISCOUNT_TYPE_CHOICES = (
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed Amount'),
    )
    
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percentage')
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    maximum_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'carts_coupon'
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['is_active']),
            models.Index(fields=['valid_from', 'valid_until']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.get_discount_type_display()}"
    
    def is_valid(self):
        """Check if coupon is valid"""
        from django.utils import timezone
        now = timezone.now()
        
        return (
            self.is_active and
            now >= self.valid_from and
            now <= self.valid_until and
            (self.usage_limit is None or self.used_count < self.usage_limit)
        )
    
    def calculate_discount(self, cart_total):
        """Calculate discount amount"""
        if not self.is_valid() or cart_total < self.minimum_amount:
            return 0
        
        if self.discount_type == 'percentage':
            discount = (cart_total * self.discount_value) / 100
        else:
            discount = self.discount_value
        
        # Apply maximum discount limit
        if self.maximum_discount:
            discount = min(discount, self.maximum_discount)
        
        return min(discount, cart_total)  # Cannot discount more than cart total


class CartCoupon(models.Model):
    """
    Junction table for cart-coupon relationships
    """
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE, related_name='applied_coupon')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'carts_cartcoupon'
    
    def __str__(self):
        return f"{self.cart} - {self.coupon.code}"


class CheckoutSession(models.Model):
    """
    Checkout session model for managing checkout process
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    cart = models.OneToOneField(Cart, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Shipping information
    shipping_address = models.TextField()
    billing_address = models.TextField()
    shipping_phone = models.CharField(max_length=20)
    
    # Payment information
    payment_method = models.CharField(max_length=50, default='chapa')
    payment_status = models.CharField(max_length=20, default='pending')
    transaction_id = models.CharField(max_length=100, null=True, blank=True)
    
    # Amounts
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()
    
    class Meta:
        db_table = 'carts_checkoutsession'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['session_key']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Checkout Session {self.id}"
    
    def is_expired(self):
        """Check if checkout session is expired"""
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def calculate_totals(self):
        """Calculate all totals for checkout"""
        # Subtotal from cart
        self.subtotal = self.cart.total_amount
        
        # Discount from applied coupon
        if hasattr(self.cart, 'applied_coupon'):
            self.discount_amount = self.cart.applied_coupon.coupon.calculate_discount(self.subtotal)
        else:
            self.discount_amount = 0
        
        # Calculate final total
        self.total_amount = self.subtotal - self.discount_amount + self.shipping_cost + self.tax_amount
        self.save()
        
        return {
            'subtotal': self.subtotal,
            'discount_amount': self.discount_amount,
            'shipping_cost': self.shipping_cost,
            'tax_amount': self.tax_amount,
            'total_amount': self.total_amount
        }
