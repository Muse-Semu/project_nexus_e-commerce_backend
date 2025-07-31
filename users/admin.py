from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, PhoneVerification, VendorProfile, CustomerProfile, AuditLog


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'full_name', 'role', 'is_active', 'is_verified', 'created_at')
    list_filter = ('role', 'is_active', 'is_verified', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-created_at',)
    readonly_fields = ('created_at', 'updated_at')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'phone_number')}),
        ('Permissions', {'fields': ('role', 'is_active', 'is_verified', 'two_factor_enabled')}),
        ('Important dates', {'fields': ('created_at', 'updated_at')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'phone_number', 'first_name', 'last_name', 'password1', 'password2', 'role'),
        }),
    )
    
    def full_name(self, obj):
        return obj.full_name
    full_name.short_description = 'Full Name'


@admin.register(PhoneVerification)
class PhoneVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'code', 'is_used', 'created_at', 'expires_at', 'is_expired')
    list_filter = ('is_used', 'created_at')
    search_fields = ('user__email', 'user__phone_number', 'code')
    readonly_fields = ('created_at', 'expires_at')
    
    def is_expired(self, obj):
        return obj.is_expired()
    is_expired.boolean = True
    is_expired.short_description = 'Expired'


@admin.register(VendorProfile)
class VendorProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company_name', 'is_approved', 'approved_at', 'approved_by')
    list_filter = ('is_approved', 'approved_at')
    search_fields = ('user__email', 'company_name', 'business_address')
    readonly_fields = ('approved_at', 'approved_by')
    
    fieldsets = (
        ('User Information', {'fields': ('user',)}),
        ('Company Information', {'fields': ('company_name', 'business_address', 'tax_id', 'business_license')}),
        ('Approval Status', {'fields': ('is_approved', 'approved_at', 'approved_by')}),
    )
    
    def save_model(self, request, obj, form, change):
        if change and 'is_approved' in form.changed_data and obj.is_approved:
            obj.approved_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_of_birth', 'has_shipping_address', 'has_billing_address')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    
    def has_shipping_address(self, obj):
        return bool(obj.shipping_address)
    has_shipping_address.boolean = True
    has_shipping_address.short_description = 'Shipping Address'
    
    def has_billing_address(self, obj):
        return bool(obj.billing_address)
    has_billing_address.boolean = True
    has_billing_address.short_description = 'Billing Address'


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'ip_address', 'created_at')
    list_filter = ('action', 'created_at')
    search_fields = ('user__email', 'action', 'ip_address')
    readonly_fields = ('user', 'action', 'ip_address', 'user_agent', 'details', 'created_at')
    ordering = ('-created_at',)
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
