from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CategoryViewSet, BrandViewSet, ProductViewSet, ProductImageViewSet,
    ProductVariantViewSet, ProductSpecificationViewSet, ProductReviewViewSet,
    ProductTagViewSet
)

# Create routers for each viewset
router = DefaultRouter()
router.register(r'categories', CategoryViewSet)
router.register(r'brands', BrandViewSet)
router.register(r'products', ProductViewSet)
router.register(r'product-images', ProductImageViewSet)
router.register(r'product-variants', ProductVariantViewSet)
router.register(r'product-specifications', ProductSpecificationViewSet)
router.register(r'reviews', ProductReviewViewSet)
router.register(r'tags', ProductTagViewSet)

urlpatterns = [
    path('', include(router.urls)),
] 