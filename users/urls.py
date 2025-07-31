from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, PhoneVerificationView, VendorProfileViewSet,
    CustomerProfileViewSet, TwoFactorView, AuditLogViewSet
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'vendor-profiles', VendorProfileViewSet, basename='vendor-profile')
router.register(r'customer-profiles', CustomerProfileViewSet, basename='customer-profile')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
    path('phone-verification/', PhoneVerificationView.as_view(), name='phone-verification'),
    path('two-factor/', TwoFactorView.as_view(), name='two-factor'),
    path('auth/', include('djoser.urls')),
    path('auth/', include('djoser.urls.jwt')),
] 