from django.contrib import admin
from .models import Cart, CartItem, Coupon, CartCoupon, CheckoutSession


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    readonly_fields = ('unit_price', 'total_price')
    fields = ('product', 'variant', 'quantity', 'unit_price', 'total_price')


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'total_items', 'total_amount', 'is_empty', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'session_key')
    readonly_fields = ('id', 'total_items', 'total_amount', 'is_empty', 'created_at', 'updated_at')
    inlines = [CartItemInline]
    
    def total_items(self, obj):
        return obj.total_items
    
    def total_amount(self, obj):
        return f"${obj.total_amount:.2f}"
    
    def is_empty(self, obj):
        return obj.is_empty
    
    total_items.short_description = 'Items'
    total_amount.short_description = 'Total Amount'
    is_empty.short_description = 'Empty'


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'variant', 'quantity', 'unit_price', 'total_price', 'created_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('cart__user__email', 'product__name', 'variant__name')
    readonly_fields = ('unit_price', 'total_price', 'created_at', 'updated_at')
    
    def unit_price(self, obj):
        return f"${obj.unit_price:.2f}"
    
    def total_price(self, obj):
        return f"${obj.total_price:.2f}"
    
    unit_price.short_description = 'Unit Price'
    total_price.short_description = 'Total Price'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'discount_value', 'minimum_amount', 'usage_limit', 'used_count', 'is_active', 'is_valid', 'valid_from', 'valid_until')
    list_filter = ('discount_type', 'is_active', 'valid_from', 'valid_until')
    search_fields = ('code', 'description')
    readonly_fields = ('used_count', 'created_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('code', 'description', 'discount_type', 'discount_value')
        }),
        ('Usage Limits', {
            'fields': ('minimum_amount', 'maximum_discount', 'usage_limit', 'used_count')
        }),
        ('Validity', {
            'fields': ('is_active', 'valid_from', 'valid_until')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def is_valid(self, obj):
        return obj.is_valid()
    
    is_valid.boolean = True
    is_valid.short_description = 'Valid'


@admin.register(CartCoupon)
class CartCouponAdmin(admin.ModelAdmin):
    list_display = ('cart', 'coupon', 'applied_at')
    list_filter = ('applied_at',)
    search_fields = ('cart__user__email', 'coupon__code')
    readonly_fields = ('applied_at',)


@admin.register(CheckoutSession)
class CheckoutSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'status', 'payment_status', 'total_amount', 'created_at', 'expires_at', 'is_expired')
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('user__email', 'transaction_id', 'shipping_phone')
    readonly_fields = ('id', 'subtotal', 'discount_amount', 'shipping_cost', 'tax_amount', 'total_amount', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'user', 'session_key', 'cart', 'status')
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'billing_address', 'shipping_phone')
        }),
        ('Payment Information', {
            'fields': ('payment_method', 'payment_status', 'transaction_id')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'discount_amount', 'shipping_cost', 'tax_amount', 'total_amount')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'expires_at'),
            'classes': ('collapse',)
        }),
    )
    
    def is_expired(self, obj):
        return obj.is_expired()
    
    is_expired.boolean = True
    is_expired.short_description = 'Expired'
