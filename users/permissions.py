from rest_framework import permissions


class IsAdmin(permissions.BasePermission):
    """
    Custom permission to only allow admin users
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_admin()


class IsVendor(permissions.BasePermission):
    """
    Custom permission to only allow vendor users
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_vendor()


class IsCustomer(permissions.BasePermission):
    """
    Custom permission to only allow customer users
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_customer()


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object or admins
    """
    def has_object_permission(self, request, view, obj):
        # Admin can access everything
        if request.user.is_admin():
            return True
        
        # Check if the object has a user attribute
        if hasattr(obj, 'user'):
            return obj.user == request.user
        
        # Check if the object is the user itself
        return obj == request.user


class IsVerifiedUser(permissions.BasePermission):
    """
    Custom permission to only allow verified users
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_verified


class IsApprovedVendor(permissions.BasePermission):
    """
    Custom permission to only allow approved vendors
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated or not request.user.is_vendor():
            return False
        
        # Check if vendor has an approved profile
        try:
            return request.user.vendor_profile.is_approved
        except:
            return False 