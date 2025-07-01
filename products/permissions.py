from rest_framework import permissions
from users.permissions import IsVendor, IsAdmin


class IsProductOwner(permissions.BasePermission):
    """
    Custom permission to only allow owners of a product to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner of the product
        return obj.vendor == request.user


class IsProductOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow product owners or admins to edit products.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the owner or admin
        return obj.vendor == request.user or request.user.is_admin()


class IsReviewOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission to allow review owners or admins to edit reviews.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed for any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the review owner or admin
        return obj.user == request.user or request.user.is_admin()


class CanCreateProduct(permissions.BasePermission):
    """
    Custom permission to allow only vendors to create products.
    """
    def has_permission(self, request, view):
        # Only vendors can create products
        if request.method == 'POST':
            return request.user.is_vendor()
        return True


class CanManageCategories(permissions.BasePermission):
    """
    Custom permission to allow only admins to manage categories.
    """
    def has_permission(self, request, view):
        # Only admins can manage categories
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return request.user.is_admin()
        return True


class CanManageBrands(permissions.BasePermission):
    """
    Custom permission to allow only admins to manage brands.
    """
    def has_permission(self, request, view):
        # Only admins can manage brands
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return request.user.is_admin()
        return True


class CanApproveReviews(permissions.BasePermission):
    """
    Custom permission to allow only admins to approve reviews.
    """
    def has_permission(self, request, view):
        # Only admins can approve reviews
        if request.method in ['POST', 'PUT', 'PATCH', 'DELETE']:
            return request.user.is_admin()
        return True


class CanViewProductDetails(permissions.BasePermission):
    """
    Custom permission to allow viewing product details.
    """
    def has_permission(self, request, view):
        # Anyone can view product details
        return True


class CanSearchProducts(permissions.BasePermission):
    """
    Custom permission to allow searching products.
    """
    def has_permission(self, request, view):
        # Anyone can search products
        return True 