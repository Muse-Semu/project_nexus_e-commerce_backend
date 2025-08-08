from django.shortcuts import render
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.conf import settings
import json
import hmac
import hashlib
import logging

from carts.models import CheckoutSession
from orders.utils import create_order_from_checkout

logger = logging.getLogger(__name__)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
def chapa_webhook(request):
    """
    Webhook handler for Chapa payment notifications
    """
    try:
        # Get the raw body
        body = request.body.decode('utf-8')
        signature = request.headers.get('Chapa-Signature')
        
        # Verify webhook signature
        if not verify_chapa_signature(body, signature):
            logger.warning("Invalid webhook signature from Chapa")
            return Response(
                {'error': 'Invalid signature'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse webhook data
        webhook_data = json.loads(body)
        
        # Extract transaction details
        tx_ref = webhook_data.get('tx_ref')
        status = webhook_data.get('status')
        amount = webhook_data.get('amount')
        currency = webhook_data.get('currency')
        
        if not tx_ref:
            logger.error("No transaction reference in webhook")
            return Response(
                {'error': 'No transaction reference'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Find checkout session
        try:
            checkout_session = CheckoutSession.objects.get(transaction_id=tx_ref)
        except CheckoutSession.DoesNotExist:
            logger.error(f"Checkout session not found for tx_ref: {tx_ref}")
            return Response(
                {'error': 'Checkout session not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Process payment status
        if status == 'success':
            # Payment successful - create order
            try:
                order = create_order_from_checkout(checkout_session)
                
                # Update checkout session payment status
                checkout_session.payment_status = 'completed'
                checkout_session.save()
                
                logger.info(f"Order {order.order_number} created from successful payment")
                
            except Exception as e:
                logger.error(f"Failed to create order from checkout session: {str(e)}")
                return Response(
                    {'error': 'Failed to create order'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
        elif status == 'failed':
            # Payment failed
            checkout_session.payment_status = 'failed'
            checkout_session.status = 'cancelled'
            checkout_session.save()
            
            logger.info(f"Payment failed for checkout session: {checkout_session.id}")
        
        return Response({'status': 'success'})
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in webhook body")
        return Response(
            {'error': 'Invalid JSON'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Webhook processing error: {str(e)}")
        return Response(
            {'error': 'Webhook processing failed'}, 
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def verify_chapa_signature(body, signature):
    """
    Verify Chapa webhook signature
    """
    if not signature:
        return False
    
    # Get webhook secret from settings
    webhook_secret = getattr(settings, 'CHAPA_WEBHOOK_SECRET', '')
    
    if not webhook_secret:
        logger.warning("Chapa webhook secret not configured")
        return True  # Allow if no secret configured
    
    # Calculate expected signature
    expected_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        body.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@api_view(['GET'])
@permission_classes([AllowAny])
def payment_status(request, transaction_id):
    """
    Check payment status
    """
    try:
        checkout_session = CheckoutSession.objects.get(transaction_id=transaction_id)
        
        return Response({
            'transaction_id': transaction_id,
            'status': checkout_session.payment_status,
            'amount': checkout_session.total_amount,
            'currency': 'USD'
        })
        
    except CheckoutSession.DoesNotExist:
        return Response(
            {'error': 'Transaction not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def payment_webhook(request):
    """
    Generic payment webhook handler
    """
    # This is a fallback for any payment gateway
    return chapa_webhook(request)
