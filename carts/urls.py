from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CartViewSet, CartItemViewSet, CouponViewSet, GuestCartView,
    CheckoutViewSet, GuestCheckoutView
)

router = DefaultRouter()
router.register(r'carts', CartViewSet, basename='cart')
router.register(r'cart-items', CartItemViewSet, basename='cart-item')
router.register(r'coupons', CouponViewSet, basename='coupon')
router.register(r'checkout', CheckoutViewSet, basename='checkout')

urlpatterns = [
    path('', include(router.urls)),
    path('guest-cart/', GuestCartView.as_view(), name='guest-cart'),
    path('guest-checkout/', GuestCheckoutView.as_view(), name='guest-checkout'),
] 