from django.contrib import admin
from django.utils.html import format_html
from .models import Order, OrderItem, OrderStatus, Return, ReturnItem, ShippingLabel


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('unit_price', 'total_price', 'product_name', 'product_sku', 'variant_name')
    fields = ('product', 'variant', 'quantity', 'unit_price', 'total_price', 'product_name', 'product_sku', 'variant_name')


class OrderStatusInline(admin.TabularInline):
    model = OrderStatus
    extra = 0
    readonly_fields = ('created_at',)
    fields = ('status', 'comment', 'created_by', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'customer', 'status', 'payment_status', 'total_amount', 
        'total_items', 'created_at', 'is_paid', 'can_cancel', 'can_return'
    )
    list_filter = ('status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'customer__email', 'customer__first_name', 'customer__last_name')
    readonly_fields = (
        'order_number', 'total_items', 'is_paid', 'can_cancel', 'can_return',
        'created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'
    )
    inlines = [OrderItemInline, OrderStatusInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order_number', 'customer', 'status', 'payment_status')
        }),
        ('Addresses', {
            'fields': ('shipping_address', 'billing_address', 'shipping_phone')
        }),
        ('Payment', {
            'fields': ('payment_method', 'transaction_id')
        }),
        ('Amounts', {
            'fields': ('subtotal', 'discount_amount', 'shipping_cost', 'tax_amount', 'total_amount')
        }),
        ('Shipping', {
            'fields': ('tracking_number', 'shipping_carrier', 'estimated_delivery')
        }),
        ('Notes', {
            'fields': ('customer_notes', 'admin_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'confirmed_at', 'shipped_at', 'delivered_at', 'cancelled_at'),
            'classes': ('collapse',)
        }),
    )
    
    def total_items(self, obj):
        return obj.total_items
    
    def is_paid(self, obj):
        return obj.is_paid
    
    def can_cancel(self, obj):
        return obj.can_cancel
    
    def can_return(self, obj):
        return obj.can_return
    
    total_items.short_description = 'Items'
    is_paid.boolean = True
    is_paid.short_description = 'Paid'
    can_cancel.boolean = True
    can_cancel.short_description = 'Can Cancel'
    can_return.boolean = True
    can_return.short_description = 'Can Return'
    
    actions = ['confirm_orders', 'ship_orders', 'mark_delivered']
    
    def confirm_orders(self, request, queryset):
        """Confirm selected orders"""
        from django.utils import timezone
        
        for order in queryset.filter(status='pending'):
            order.status = 'confirmed'
            order.confirmed_at = timezone.now()
            order.save()
            
            OrderStatus.objects.create(
                order=order,
                status='confirmed',
                comment='Order confirmed via admin action',
                created_by=request.user
            )
        
        self.message_user(request, f"{queryset.count()} orders confirmed successfully")
    
    def ship_orders(self, request, queryset):
        """Ship selected orders"""
        from django.utils import timezone
        
        for order in queryset.filter(status='confirmed'):
            order.status = 'shipped'
            order.shipped_at = timezone.now()
            order.save()
            
            OrderStatus.objects.create(
                order=order,
                status='shipped',
                comment='Order shipped via admin action',
                created_by=request.user
            )
        
        self.message_user(request, f"{queryset.count()} orders shipped successfully")
    
    def mark_delivered(self, request, queryset):
        """Mark selected orders as delivered"""
        from django.utils import timezone
        
        for order in queryset.filter(status='shipped'):
            order.status = 'delivered'
            order.delivered_at = timezone.now()
            order.save()
            
            OrderStatus.objects.create(
                order=order,
                status='delivered',
                comment='Order delivered via admin action',
                created_by=request.user
            )
        
        self.message_user(request, f"{queryset.count()} orders marked as delivered")
    
    confirm_orders.short_description = "Confirm selected orders"
    ship_orders.short_description = "Ship selected orders"
    mark_delivered.short_description = "Mark selected orders as delivered"


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'variant', 'quantity', 'unit_price', 'total_price')
    list_filter = ('order__status',)
    search_fields = ('order__order_number', 'product__name', 'product_name')
    readonly_fields = ('unit_price', 'total_price', 'product_name', 'product_sku', 'variant_name')
    
    def unit_price(self, obj):
        return f"${obj.unit_price:.2f}"
    
    def total_price(self, obj):
        return f"${obj.total_price:.2f}"
    
    unit_price.short_description = 'Unit Price'
    total_price.short_description = 'Total Price'


@admin.register(OrderStatus)
class OrderStatusAdmin(admin.ModelAdmin):
    list_display = ('order', 'status', 'created_by', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('order__order_number', 'comment', 'created_by__email')
    readonly_fields = ('created_at',)


class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 0
    readonly_fields = ('order_item',)


@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ('order', 'customer', 'reason', 'status', 'refund_amount', 'created_at')
    list_filter = ('status', 'reason', 'created_at')
    search_fields = ('order__order_number', 'customer__email', 'description')
    readonly_fields = ('created_at', 'updated_at', 'processed_at')
    inlines = [ReturnItemInline]
    
    fieldsets = (
        ('Return Information', {
            'fields': ('order', 'customer', 'reason', 'description', 'status')
        }),
        ('Refund Information', {
            'fields': ('refund_amount', 'refund_method', 'refund_transaction_id')
        }),
        ('Admin Information', {
            'fields': ('admin_notes', 'processed_by')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['approve_returns', 'reject_returns']
    
    def approve_returns(self, request, queryset):
        """Approve selected returns"""
        for return_request in queryset.filter(status='pending'):
            return_request.status = 'approved'
            return_request.processed_by = request.user
            return_request.save()
        
        self.message_user(request, f"{queryset.count()} returns approved successfully")
    
    def reject_returns(self, request, queryset):
        """Reject selected returns"""
        for return_request in queryset.filter(status='pending'):
            return_request.status = 'rejected'
            return_request.processed_by = request.user
            return_request.save()
        
        self.message_user(request, f"{queryset.count()} returns rejected successfully")
    
    approve_returns.short_description = "Approve selected returns"
    reject_returns.short_description = "Reject selected returns"


@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ('return_request', 'order_item', 'quantity', 'reason')
    list_filter = ('reason', 'return_request__status')
    search_fields = ('return_request__order__order_number', 'order_item__product_name')


@admin.register(ShippingLabel)
class ShippingLabelAdmin(admin.ModelAdmin):
    list_display = ('order', 'tracking_number', 'carrier', 'created_at')
    list_filter = ('carrier', 'created_at')
    search_fields = ('order__order_number', 'tracking_number')
    readonly_fields = ('created_at',)
