from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from .models import PhoneVerification, VendorProfile, CustomerProfile, AuditLog
import logging

User = get_user_model()
logger = logging.getLogger(__name__)

# JSON Schema for validation
USER_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "email": {
            "type": "string",
            "format": "email",
            "pattern": "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$"
        },
        "phone_number": {
            "type": "string",
            "pattern": "^\\+?1?\\d{9,15}$"
        },
        "first_name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 30,
            "pattern": "^[a-zA-Z\\s]+$"
        },
        "last_name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 30,
            "pattern": "^[a-zA-Z\\s]+$"
        },
        "password": {
            "type": "string",
            "minLength": 8
        },
        "re_password": {
            "type": "string",
            "minLength": 8
        },
        "role": {
            "type": "string",
            "enum": ["customer", "vendor"]
        }
    },
    "required": ["email", "phone_number", "first_name", "last_name", "password"],
    "additionalProperties": True
}

PHONE_VERIFICATION_SCHEMA = {
    "type": "object",
    "properties": {
        "phone_number": {
            "type": "string",
            "pattern": "^\\+?1?\\d{9,15}$"
        },
        "code": {
            "type": "string",
            "pattern": "^\\d{6}$"
        }
    },
    "required": ["phone_number", "code"],
    "additionalProperties": False
}

VENDOR_PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "company_name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 100
        },
        "business_address": {
            "type": "string",
            "minLength": 10,
            "maxLength": 500
        },
        "tax_id": {
            "type": "string",
            "maxLength": 50
        },
        "business_license": {
            "type": "string",
            "maxLength": 100
        }
    },
    "required": ["company_name", "business_address"],
    "additionalProperties": False
}


class UserCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration with jsonschema validation
    """
    re_password = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = ('id', 'email', 'phone_number', 'first_name', 'last_name', 
                 'password', 're_password', 'role')
        extra_kwargs = {
            'password': {'write_only': True},
            'role': {'required': False}  # Remove default to allow role selection
        }
    
    def validate(self, attrs):
        try:
            # JSON Schema validation
            validate(attrs, USER_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            logger.error(f"Schema validation failed: {e.message}")
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        
        # Password validation
        if attrs['password'] != attrs['re_password']:
            raise serializers.ValidationError({
                'error': 'Password mismatch',
                'details': "Passwords don't match."
            })
        
        try:
            validate_password(attrs['password'])
        except ValidationError as e:
            raise serializers.ValidationError({
                'error': 'Password validation failed',
                'details': e.messages
            })
        
        # Check email uniqueness
        if User.objects.filter(email=attrs['email']).exists():
            raise serializers.ValidationError({
                'error': 'Email already exists',
                'details': "A user with this email already exists."
            })
        
        # Check phone number uniqueness
        if User.objects.filter(phone_number=attrs['phone_number']).exists():
            raise serializers.ValidationError({
                'error': 'Phone number already exists',
                'details': "A user with this phone number already exists."
            })
        
        # Validate role
        role = attrs.get('role', 'customer')
        if role not in ['customer', 'vendor']:
            raise serializers.ValidationError({
                'error': 'Invalid role',
                'details': "Role must be either 'customer' or 'vendor'."
            })
        
        # Set default role to customer if not provided
        if 'role' not in attrs:
            attrs['role'] = 'customer'
        
        return attrs
    
    def create(self, validated_data):
        try:
            validated_data.pop('re_password')
            user = User.objects.create_user(**validated_data)
            logger.info(f"User created successfully: {user.email} with role: {user.role}")
            return user
        except Exception as e:
            logger.error(f"Error creating user: {str(e)}")
            raise serializers.ValidationError({
                'error': 'User creation failed',
                'details': 'An error occurred while creating the user. Please try again.'
            })


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user details
    """
    full_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ('id', 'email', 'phone_number', 'first_name', 'last_name', 
                 'full_name', 'role', 'is_active', 'is_verified', 'created_at')
        read_only_fields = ('id', 'email', 'role', 'is_active', 'is_verified', 'created_at')


class PhoneVerificationSerializer(serializers.ModelSerializer):
    """
    Serializer for phone verification
    """
    class Meta:
        model = PhoneVerification
        fields = ('code',)
    
    def validate(self, attrs):
        # JSON Schema validation
        try:
            validate(attrs, PHONE_VERIFICATION_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError(f"Validation error: {e.message}")
        
        return attrs


class VendorProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for vendor profile
    """
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = VendorProfile
        fields = ('id', 'user', 'company_name', 'business_address', 'tax_id', 
                 'business_license', 'is_approved', 'approved_at', 'approved_by')
        read_only_fields = ('id', 'is_approved', 'approved_at', 'approved_by')
    
    def validate(self, attrs):
        # JSON Schema validation
        try:
            validate(attrs, VENDOR_PROFILE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError(f"Validation error: {e.message}")
        
        return attrs


class CustomerProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for customer profile
    """
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = CustomerProfile
        fields = ('id', 'user', 'date_of_birth', 'shipping_address', 
                 'billing_address', 'preferences')


class AuditLogSerializer(serializers.ModelSerializer):
    """
    Serializer for audit logs
    """
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ('id', 'user', 'action', 'ip_address', 'user_agent', 
                 'details', 'created_at')
        read_only_fields = ('id', 'user', 'action', 'ip_address', 'user_agent', 
                           'details', 'created_at')


class TwoFactorSetupSerializer(serializers.Serializer):
    """
    Serializer for 2FA setup
    """
    enable = serializers.BooleanField()
    
    def validate_enable(self, value):
        user = self.context['request'].user
        if value and user.two_factor_enabled:
            raise serializers.ValidationError("Two-factor authentication is already enabled.")
        return value


class TwoFactorVerifySerializer(serializers.Serializer):
    """
    Serializer for 2FA verification
    """
    code = serializers.CharField(max_length=6, min_length=6)
    
    def validate_code(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("Code must contain only digits.")
        return value 