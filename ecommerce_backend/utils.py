import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from jsonschema import ValidationError as JSONSchemaValidationError

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler to provide consistent error responses
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Handle known REST framework exceptions
        if hasattr(exc, 'detail'):
            if isinstance(exc.detail, dict):
                response.data = {
                    'error': 'Validation failed',
                    'details': exc.detail
                }
            else:
                response.data = {
                    'error': 'Request failed',
                    'details': str(exc.detail)
                }
        return response
    
    # Handle Django exceptions
    if isinstance(exc, DjangoValidationError):
        logger.error(f"Django validation error: {exc}")
        return Response({
            'error': 'Validation failed',
            'details': exc.messages if hasattr(exc, 'messages') else str(exc)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle database integrity errors
    if isinstance(exc, IntegrityError):
        logger.error(f"Database integrity error: {exc}")
        return Response({
            'error': 'Database error',
            'details': 'A database constraint was violated. Please check your input.'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle JSON schema validation errors
    if isinstance(exc, JSONSchemaValidationError):
        logger.error(f"JSON schema validation error: {exc}")
        return Response({
            'error': 'Schema validation failed',
            'details': str(exc)
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Handle any other unexpected exceptions
    logger.error(f"Unexpected error: {exc}", exc_info=True)
    return Response({
        'error': 'Internal server error',
        'details': 'An unexpected error occurred. Please try again later.'
    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR) 