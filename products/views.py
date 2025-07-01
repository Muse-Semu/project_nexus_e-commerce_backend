from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Avg, Count, F
from django.utils import timezone
from .models import (
    Category, Brand, Product, ProductImage, ProductVariant, 
    ProductSpecification, ProductReview, ProductTag
)
from .serializers import (
    CategorySerializer, BrandSerializer, ProductSerializer, ProductCreateSerializer,
    ProductImageSerializer, ProductVariantSerializer, ProductSpecificationSerializer,
    ProductReviewSerializer, ProductTagSerializer
)
from .permissions import (
    IsProductOwnerOrAdmin, IsReviewOwnerOrAdmin, CanCreateProduct,
    CanManageCategories, CanManageBrands, CanApproveReviews,
    CanViewProductDetails, CanSearchProducts
)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product categories
    """
    queryset = Category.objects.filter(is_active=True)
    serializer_class = CategorySerializer
    permission_classes = [CanManageCategories]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['parent', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products in a category"""
        category = self.get_object()
        products = Product.objects.filter(
            category=category, 
            is_active=True, 
            status='active'
        )
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def subcategories(self, request, pk=None):
        """Get all subcategories of a category"""
        category = self.get_object()
        subcategories = category.get_children()
        serializer = CategorySerializer(subcategories, many=True)
        return Response(serializer.data)


class BrandViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product brands
    """
    queryset = Brand.objects.filter(is_active=True)
    serializer_class = BrandSerializer
    permission_classes = [CanManageBrands]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products for a brand"""
        brand = self.get_object()
        products = Product.objects.filter(
            brand=brand, 
            is_active=True, 
            status='active'
        )
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)


class ProductViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing products
    """
    queryset = Product.objects.filter(is_active=True)
    serializer_class = ProductSerializer
    permission_classes = [CanViewProductDetails]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['category', 'brand', 'vendor', 'status', 'condition', 'is_featured']
    search_fields = ['name', 'description', 'short_description', 'sku']
    ordering_fields = ['name', 'base_price', 'created_at', 'updated_at']
    ordering = ['-created_at']
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'search', 'featured']:
            return [AllowAny()]
        elif self.action == 'create':
            return [CanCreateProduct()]
        elif self.action in ['update', 'partial_update', 'destroy']:
            return [IsProductOwnerOrAdmin()]
        return super().get_permissions()
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by price range
        min_price = self.request.query_params.get('min_price')
        max_price = self.request.query_params.get('max_price')
        if min_price:
            queryset = queryset.filter(base_price__gte=min_price)
        if max_price:
            queryset = queryset.filter(base_price__lte=max_price)
        
        # Filter by availability
        in_stock = self.request.query_params.get('in_stock')
        if in_stock == 'true':
            queryset = queryset.filter(stock_quantity__gt=0)
        elif in_stock == 'false':
            queryset = queryset.filter(stock_quantity=0)
        
        # Filter by sale items
        on_sale = self.request.query_params.get('on_sale')
        if on_sale == 'true':
            queryset = queryset.filter(sale_price__isnull=False).filter(sale_price__lt=F('base_price'))
        
        # Filter by rating
        min_rating = self.request.query_params.get('min_rating')
        if min_rating:
            queryset = queryset.annotate(
                avg_rating=Avg('reviews__rating')
            ).filter(avg_rating__gte=min_rating)
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def featured(self, request):
        """Get featured products"""
        featured_products = self.get_queryset().filter(is_featured=True)
        serializer = self.get_serializer(featured_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def on_sale(self, request):
        """Get products on sale"""
        sale_products = self.get_queryset().filter(
            sale_price__isnull=False
        ).filter(sale_price__lt=F('base_price'))
        serializer = self.get_serializer(sale_products, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """Get products with low stock (vendor only)"""
        if not request.user.is_vendor():
            return Response(
                {'error': 'Access denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        low_stock_products = self.get_queryset().filter(
            vendor=request.user,
            stock_quantity__lte=F('low_stock_threshold')
        )
        serializer = self.get_serializer(low_stock_products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_review(self, request, pk=None):
        """Add a review to a product"""
        product = self.get_object()
        serializer = ProductReviewSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save(product=product, user=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def add_image(self, request, pk=None):
        """Add an image to a product (owner only)"""
        product = self.get_object()
        
        if product.vendor != request.user:
            return Response(
                {'error': 'Access denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ProductImageSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(product=product)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProductImageViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product images
    """
    queryset = ProductImage.objects.all()
    serializer_class = ProductImageSerializer
    permission_classes = [IsProductOwnerOrAdmin]
    
    def get_queryset(self):
        return ProductImage.objects.filter(product__vendor=self.request.user)


class ProductVariantViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product variants
    """
    queryset = ProductVariant.objects.all()
    serializer_class = ProductVariantSerializer
    permission_classes = [IsProductOwnerOrAdmin]
    
    def get_queryset(self):
        return ProductVariant.objects.filter(product__vendor=self.request.user)


class ProductSpecificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product specifications
    """
    queryset = ProductSpecification.objects.all()
    serializer_class = ProductSpecificationSerializer
    permission_classes = [IsProductOwnerOrAdmin]
    
    def get_queryset(self):
        return ProductSpecification.objects.filter(product__vendor=self.request.user)


class ProductReviewViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product reviews
    """
    queryset = ProductReview.objects.filter(is_approved=True)
    serializer_class = ProductReviewSerializer
    permission_classes = [IsReviewOwnerOrAdmin]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['product', 'rating', 'is_verified_purchase']
    ordering_fields = ['rating', 'created_at']
    ordering = ['-created_at']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        elif self.action in ['approve', 'reject']:
            return [CanApproveReviews()]
        return super().get_permissions()
    
    def get_queryset(self):
        if self.request.user.is_authenticated and self.request.user.is_admin():
            return ProductReview.objects.all()
        return ProductReview.objects.filter(is_approved=True)
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a review (admin only)"""
        review = self.get_object()
        review.is_approved = True
        review.save()
        return Response({'status': 'review approved'})
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject a review (admin only)"""
        review = self.get_object()
        review.is_approved = False
        review.save()
        return Response({'status': 'review rejected'})


class ProductTagViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing product tags
    """
    queryset = ProductTag.objects.all()
    serializer_class = ProductTagSerializer
    permission_classes = [CanManageCategories]  # Only admins can manage tags
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ['name']
    
    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [AllowAny()]
        return super().get_permissions()
    
    @action(detail=True, methods=['get'])
    def products(self, request, pk=None):
        """Get all products with this tag"""
        tag = self.get_object()
        products = tag.products.filter(is_active=True, status='active')
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)
