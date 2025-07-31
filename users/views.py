from django.shortcuts import render
from rest_framework import status, generics, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
import random
import string
from datetime import timedelta
from django.conf import settings

from .models import PhoneVerification, VendorProfile, CustomerProfile, AuditLog
from .serializers import (
    UserCreateSerializer, UserSerializer, PhoneVerificationSerializer,
    VendorProfileSerializer, CustomerProfileSerializer, AuditLogSerializer,
    TwoFactorSetupSerializer, TwoFactorVerifySerializer
)
from .permissions import IsAdmin, IsVendor, IsCustomer, IsOwnerOrAdmin, IsVerifiedUser, IsApprovedVendor
from .tasks import send_sms_verification, send_email_notification

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for user management
    """
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        if self.request.user.is_admin():
            return User.objects.all()
        return User.objects.filter(id=self.request.user.id)
    
    def get_permissions(self):
        if self.action == 'create':
            return [AllowAny()]
        elif self.action in ['list', 'destroy']:
            return [IsAdmin()]
        elif self.action in ['update', 'partial_update']:
            return [IsOwnerOrAdmin()]
        return [IsAuthenticated()]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user details"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        """Approve a user (admin only)"""
        user = self.get_object()
        user.is_active = True
        user.is_verified = True
        user.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action='user_activate',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={'target_user_id': user.id}
        )
        
        return Response({'message': 'User approved successfully'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def deactivate(self, request, pk=None):
        """Deactivate a user (admin only)"""
        user = self.get_object()
        user.is_active = False
        user.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action='user_deactivate',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={'target_user_id': user.id}
        )
        
        return Response({'message': 'User deactivated successfully'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def change_role(self, request, pk=None):
        """Change user role (admin only)"""
        user = self.get_object()
        new_role = request.data.get('role')
        
        if new_role not in ['admin', 'vendor', 'customer']:
            return Response(
                {'error': 'Invalid role'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        old_role = user.role
        user.role = new_role
        user.save()
        
        # Create audit log
        AuditLog.objects.create(
            user=request.user,
            action='role_change',
            ip_address=self.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            details={
                'target_user_id': user.id,
                'old_role': old_role,
                'new_role': new_role
            }
        )
        
        return Response({'message': f'User role changed to {new_role}'})
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class PhoneVerificationView(generics.CreateAPIView):
    """
    View for sending and verifying phone verification codes
    """
    serializer_class = PhoneVerificationSerializer
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        action = request.data.get('action')
        
        if action == 'send':
            return self.send_verification_code(request)
        elif action == 'verify':
            return self.verify_code(request)
        else:
            return Response(
                {'error': 'Invalid action. Use "send" or "verify"'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def send_verification_code(self, request):
        """Send verification code via SMS"""
        phone_number = request.data.get('phone_number')
        
        if not phone_number:
            return Response(
                {'error': 'Phone number is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate 6-digit code
        code = ''.join(random.choices(string.digits, k=6))
        
        # Create or update verification record
        verification, created = PhoneVerification.objects.get_or_create(
            user=request.user,
            defaults={
                'code': code,
                'expires_at': timezone.now() + timedelta(minutes=10)
            }
        )
        
        if not created:
            verification.code = code
            verification.is_used = False
            verification.expires_at = timezone.now() + timedelta(minutes=10)
            verification.save()
        
        # Send SMS via Celery task
        send_sms_verification.delay(phone_number, code)
        
        return Response({
            'message': 'Verification code sent successfully',
            'expires_at': verification.expires_at
        })
    
    def verify_code(self, request):
        """Verify the SMS code"""
        phone_number = request.data.get('phone_number')
        code = request.data.get('code')
        
        if not phone_number or not code:
            return Response(
                {'error': 'Phone number and code are required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            verification = PhoneVerification.objects.get(
                user=request.user,
                code=code,
                is_used=False
            )
            
            if verification.is_expired():
                return Response(
                    {'error': 'Verification code has expired'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark as used and verify user
            verification.is_used = True
            verification.save()
            
            request.user.is_verified = True
            request.user.save()
            
            # Create audit log
            AuditLog.objects.create(
                user=request.user,
                action='profile_update',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                details={'verification_type': 'phone'}
            )
            
            return Response({'message': 'Phone number verified successfully'})
            
        except PhoneVerification.DoesNotExist:
            return Response(
                {'error': 'Invalid verification code'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class VendorProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for vendor profile management
    """
    serializer_class = VendorProfileSerializer
    permission_classes = [IsAuthenticated, IsVendor]
    
    def get_queryset(self):
        if self.request.user.is_admin():
            return VendorProfile.objects.all()
        return VendorProfile.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdmin])
    def approve(self, request, pk=None):
        """Approve a vendor (admin only)"""
        profile = self.get_object()
        profile.is_approved = True
        profile.approved_at = timezone.now()
        profile.approved_by = request.user
        profile.save()
        
        # Send notification to vendor (handle Celery errors gracefully)
        # Set SEND_EMAIL_NOTIFICATIONS=False in settings to disable
        if getattr(settings, 'SEND_EMAIL_NOTIFICATIONS', True):
            try:
                send_email_notification.delay(
                    profile.user.email,
                    'Vendor Approval',
                    f'Congratulations! Your vendor account has been approved.'
                )
            except Exception as e:
                # Log the error but don't fail the approval
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to send vendor approval email for vendor {profile.id}: {e}")
        
        return Response({'message': 'Vendor approved successfully'})


class CustomerProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for customer profile management
    """
    serializer_class = CustomerProfileSerializer
    permission_classes = [IsAuthenticated, IsCustomer]
    
    def get_queryset(self):
        return CustomerProfile.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class TwoFactorView(generics.GenericAPIView):
    """
    View for two-factor authentication
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        action = request.data.get('action')
        
        if action == 'setup':
            return self.setup_2fa(request)
        elif action == 'verify':
            return self.verify_2fa(request)
        else:
            return Response(
                {'error': 'Invalid action. Use "setup" or "verify"'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def setup_2fa(self, request):
        """Setup two-factor authentication"""
        serializer = TwoFactorSetupSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        if serializer.validated_data['enable']:
            # Generate secret key (in production, use proper 2FA library)
            import secrets
            user.two_factor_secret = secrets.token_hex(16)
            user.two_factor_enabled = True
            user.save()
            
            return Response({
                'message': 'Two-factor authentication enabled',
                'secret': user.two_factor_secret
            })
        else:
            user.two_factor_enabled = False
            user.two_factor_secret = None
            user.save()
            
            return Response({'message': 'Two-factor authentication disabled'})
    
    def verify_2fa(self, request):
        """Verify two-factor authentication code"""
        serializer = TwoFactorVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        code = serializer.validated_data['code']
        
        # Simple verification (in production, use proper 2FA library)
        if user.two_factor_secret and code == '123456':  # Demo code
            return Response({'message': 'Two-factor authentication verified'})
        else:
            return Response(
                {'error': 'Invalid verification code'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for audit logs (admin only)
    """
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdmin]
    
    def get_queryset(self):
        return AuditLog.objects.all().order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def user_actions(self, request):
        """Get audit logs for a specific user"""
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response(
                {'error': 'user_id parameter is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logs = AuditLog.objects.filter(user_id=user_id).order_by('-created_at')
        serializer = self.get_serializer(logs, many=True)
        return Response(serializer.data)
