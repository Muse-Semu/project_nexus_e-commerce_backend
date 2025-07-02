from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache
import logging
import requests
from datetime import timedelta

from .models import Cart, CartItem, Coupon, CartCoupon, CheckoutSession
from .serializers import (
    CartSerializer, CartCreateSerializer, CartItemSerializer, CartItemCreateSerializer,
    CouponSerializer, ApplyCouponSerializer, CartSummarySerializer,
    CheckoutSessionSerializer, CheckoutCreateSerializer, PaymentInitiateSerializer
)

User = get_user_model()
logger = logging.getLogger(__name__)


class CartViewSet(viewsets.ModelViewSet):
    """
    ViewSet for cart management
    """
    serializer_class = CartSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get user's cart or create one if it doesn't exist"""
        user = self.request.user
        cart, created = Cart.objects.get_or_create(user=user)
        return Cart.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CartCreateSerializer
        return CartSerializer
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get cart summary for checkout"""
        cart = self.get_queryset().first()
        if not cart:
            return Response({'message': 'Cart is empty'}, status=status.HTTP_404_NOT_FOUND)
        
        serializer = CartSummarySerializer(cart)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def apply_coupon(self, request):
        """Apply coupon to cart"""
        cart = self.get_queryset().first()
        if not cart or cart.is_empty:
            return Response(
                {'error': 'Cart is empty'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            coupon = Coupon.objects.get(code=serializer.validated_data['code'])
            
            # Check if coupon is already applied
            if hasattr(cart, 'applied_coupon'):
                return Response(
                    {'error': 'Coupon already applied'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Apply coupon
            CartCoupon.objects.create(cart=cart, coupon=coupon)
            
            # Update coupon usage count
            coupon.used_count += 1
            coupon.save()
            
            return Response({'message': 'Coupon applied successfully'})
            
        except Coupon.DoesNotExist:
            return Response(
                {'error': 'Invalid coupon code'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def remove_coupon(self, request):
        """Remove applied coupon from cart"""
        cart = self.get_queryset().first()
        if not cart:
            return Response(
                {'error': 'Cart not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if hasattr(cart, 'applied_coupon'):
            cart.applied_coupon.delete()
            return Response({'message': 'Coupon removed successfully'})
        
        return Response(
            {'error': 'No coupon applied'}, 
            status=status.HTTP_400_BAD_REQUEST
        )
    
    @action(detail=False, methods=['post'])
    def clear(self, request):
        """Clear all items from cart"""
        cart = self.get_queryset().first()
        if cart:
            cart.items.all().delete()
            if hasattr(cart, 'applied_coupon'):
                cart.applied_coupon.delete()
            return Response({'message': 'Cart cleared successfully'})
        
        return Response(
            {'error': 'Cart not found'}, 
            status=status.HTTP_404_NOT_FOUND
        )


class CartItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet for cart item management
    """
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get items from user's cart"""
        user = self.request.user
        cart, created = Cart.objects.get_or_create(user=user)
        return CartItem.objects.filter(cart=cart)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CartItemCreateSerializer
        return CartItemSerializer
    
    def create(self, request, *args, **kwargs):
        """Add item to cart"""
        user = request.user
        cart, created = Cart.objects.get_or_create(user=user)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if item already exists in cart
        existing_item = CartItem.objects.filter(
            cart=cart,
            product=serializer.validated_data['product'],
            variant=serializer.validated_data.get('variant')
        ).first()
        
        if existing_item:
            # Update quantity
            new_quantity = existing_item.quantity + serializer.validated_data['quantity']
            existing_item.quantity = new_quantity
            existing_item.save()
            
            response_serializer = CartItemSerializer(existing_item)
            return Response(response_serializer.data, status=status.HTTP_200_OK)
        else:
            # Create new item
            serializer.save(cart=cart)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def update(self, request, *args, **kwargs):
        """Update cart item quantity"""
        instance = self.get_object()
        quantity = request.data.get('quantity', 1)
        
        if quantity <= 0:
            instance.delete()
            return Response({'message': 'Item removed from cart'})
        
        # Validate stock availability
        product = instance.product
        variant = instance.variant
        
        if variant:
            available_stock = variant.stock_quantity
        else:
            available_stock = product.stock_quantity
        
        if quantity > available_stock:
            return Response(
                {'error': f'Only {available_stock} items available in stock'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.quantity = quantity
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def increase_quantity(self, request, pk=None):
        """Increase item quantity by 1"""
        instance = self.get_object()
        new_quantity = instance.quantity + 1
        
        # Check stock availability
        product = instance.product
        variant = instance.variant
        
        if variant:
            available_stock = variant.stock_quantity
        else:
            available_stock = product.stock_quantity
        
        if new_quantity > available_stock:
            return Response(
                {'error': f'Only {available_stock} items available in stock'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.quantity = new_quantity
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def decrease_quantity(self, request, pk=None):
        """Decrease item quantity by 1"""
        instance = self.get_object()
        new_quantity = instance.quantity - 1
        
        if new_quantity <= 0:
            instance.delete()
            return Response({'message': 'Item removed from cart'})
        
        instance.quantity = new_quantity
        instance.save()
        
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CouponViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for coupon management (read-only for customers)
    """
    queryset = Coupon.objects.filter(is_active=True)
    serializer_class = CouponSerializer
    permission_classes = [AllowAny]
    
    @action(detail=False, methods=['get'])
    def validate(self, request):
        """Validate a coupon code"""
        code = request.query_params.get('code')
        if not code:
            return Response(
                {'error': 'Coupon code is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            coupon = Coupon.objects.get(code=code)
            if coupon.is_valid():
                serializer = self.get_serializer(coupon)
                return Response(serializer.data)
            else:
                return Response(
                    {'error': 'Coupon is not valid or has expired'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Coupon.DoesNotExist:
            return Response(
                {'error': 'Invalid coupon code'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


class GuestCartView(generics.GenericAPIView):
    """
    View for guest cart management (session-based)
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """Get guest cart"""
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        
        serializer = CartSerializer(cart)
        return Response(serializer.data)
    
    def post(self, request):
        """Add item to guest cart"""
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        
        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check if item already exists
        existing_item = CartItem.objects.filter(
            cart=cart,
            product=serializer.validated_data['product'],
            variant=serializer.validated_data.get('variant')
        ).first()
        
        if existing_item:
            new_quantity = existing_item.quantity + serializer.validated_data['quantity']
            existing_item.quantity = new_quantity
            existing_item.save()
        else:
            serializer.save(cart=cart)
        
        return Response({'message': 'Item added to cart'})


class CheckoutViewSet(viewsets.ModelViewSet):
    """
    ViewSet for checkout management
    """
    serializer_class = CheckoutSessionSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Get user's checkout sessions"""
        user = self.request.user
        return CheckoutSession.objects.filter(user=user)
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CheckoutCreateSerializer
        return CheckoutSessionSerializer
    
    def create(self, request, *args, **kwargs):
        """Create checkout session"""
        user = request.user
        
        # Get or create user's cart
        cart, created = Cart.objects.get_or_create(user=user)
        
        if cart.is_empty:
            return Response(
                {'error': 'Cart is empty'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create checkout session
        checkout_session = CheckoutSession.objects.create(
            user=user,
            cart=cart,
            shipping_address=serializer.validated_data['shipping_address'],
            billing_address=serializer.validated_data['billing_address'],
            shipping_phone=serializer.validated_data['shipping_phone'],
            payment_method=serializer.validated_data.get('payment_method', 'chapa'),
            expires_at=timezone.now() + timedelta(hours=24)  # 24 hour expiry
        )
        
        # Calculate totals
        totals = checkout_session.calculate_totals()
        
        response_serializer = CheckoutSessionSerializer(checkout_session)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def initiate_payment(self, request, pk=None):
        """Initiate payment for checkout session"""
        checkout_session = self.get_object()
        
        if checkout_session.is_expired():
            return Response(
                {'error': 'Checkout session has expired'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if checkout_session.status != 'pending':
            return Response(
                {'error': 'Checkout session is not in pending status'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Initiate Chapa payment
        try:
            payment_data = self._initiate_chapa_payment(checkout_session)
            return Response(payment_data)
        except Exception as e:
            logger.error(f"Payment initiation failed: {str(e)}")
            return Response(
                {'error': 'Payment initiation failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    def _initiate_chapa_payment(self, checkout_session):
        """Initiate payment with Chapa"""
        from django.conf import settings
        
        # Chapa API configuration
        chapa_api_key = getattr(settings, 'CHAPA_API_KEY', '')
        chapa_base_url = 'https://api.chapa.co/v1'
        
        if not chapa_api_key:
            raise Exception("Chapa API key not configured")
        
        # Prepare payment data
        payment_data = {
            "amount": str(checkout_session.total_amount),
            "currency": "USD",
            "email": checkout_session.user.email,
            "first_name": checkout_session.user.first_name,
            "last_name": checkout_session.user.last_name,
            "tx_ref": f"tx-{checkout_session.id}",
            "callback_url": f"{settings.BASE_URL}/api/payments/webhook/",
            "return_url": f"{settings.BASE_URL}/checkout/success/",
            "customization": {
                "title": "E-commerce Payment",
                "description": f"Payment for order {checkout_session.id}"
            }
        }
        
        # Make API request to Chapa
        headers = {
            "Authorization": f"Bearer {chapa_api_key}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(
            f"{chapa_base_url}/transaction/initialize",
            json=payment_data,
            headers=headers
        )
        
        if response.status_code == 200:
            response_data = response.json()
            
            # Update checkout session with transaction ID
            checkout_session.transaction_id = response_data.get('data', {}).get('reference')
            checkout_session.payment_status = 'pending'
            checkout_session.save()
            
            return {
                'payment_url': response_data.get('data', {}).get('checkout_url'),
                'transaction_id': checkout_session.transaction_id,
                'status': 'pending'
            }
        else:
            raise Exception(f"Chapa API error: {response.text}")


class GuestCheckoutView(generics.GenericAPIView):
    """
    View for guest checkout (session-based)
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Create guest checkout session"""
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key
        
        # Get or create guest cart
        cart, created = Cart.objects.get_or_create(
            session_key=session_key,
            user=None
        )
        
        if cart.is_empty:
            return Response(
                {'error': 'Cart is empty'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = CheckoutCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Create checkout session
        checkout_session = CheckoutSession.objects.create(
            session_key=session_key,
            cart=cart,
            shipping_address=serializer.validated_data['shipping_address'],
            billing_address=serializer.validated_data['billing_address'],
            shipping_phone=serializer.validated_data['shipping_phone'],
            payment_method=serializer.validated_data.get('payment_method', 'chapa'),
            expires_at=timezone.now() + timedelta(hours=24)
        )
        
        # Calculate totals
        totals = checkout_session.calculate_totals()
        
        response_serializer = CheckoutSessionSerializer(checkout_session)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
