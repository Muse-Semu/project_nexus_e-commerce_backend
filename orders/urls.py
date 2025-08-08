from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import OrderViewSet, ReturnViewSet, ShippingLabelViewSet

router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'returns', ReturnViewSet, basename='return')
router.register(r'shipping-labels', ShippingLabelViewSet, basename='shipping-label')

urlpatterns = [
    path('', include(router.urls)),
] 