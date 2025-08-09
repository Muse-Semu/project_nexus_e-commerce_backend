from rest_framework import serializers
from django.contrib.auth import get_user_model
from jsonschema import validate, ValidationError as JSONSchemaValidationError
from .models import (
    Category, Brand, Product, ProductImage, ProductVariant, 
    ProductSpecification, ProductReview, ProductTag
)

User = get_user_model()

# JSON Schema for validation
PRODUCT_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "description": {
            "type": "string",
            "minLength": 10
        },
        "short_description": {
            "type": "string",
            "maxLength": 500
        },
        "base_price": {
            "type": "number",
            "minimum": 0
        },
        "sale_price": {
            "type": "number",
            "minimum": 0
        },
        "stock_quantity": {
            "type": "integer",
            "minimum": 0
        },
        "low_stock_threshold": {
            "type": "integer",
            "minimum": 0
        },
        "weight": {
            "type": "number",
            "minimum": 0
        },
        "condition": {
            "type": "string",
            "enum": ["new", "used", "refurbished"]
        },
        "status": {
            "type": "string",
            "enum": ["draft", "active", "inactive", "deleted"]
        }
    },
    "required": ["name", "description", "base_price", "stock_quantity","category"],
    "additionalProperties": True
}

CATEGORY_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 100
        },
        "description": {
            "type": "string",
            "maxLength": 1000
        }
    },
    "required": ["name"],
    "additionalProperties": False
}

BRAND_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {
            "type": "string",
            "minLength": 2,
            "maxLength": 100
        },
        "description": {
            "type": "string",
            "maxLength": 1000
        },
        "website": {
            "type": "string",
            "format": "uri"
        }
    },
    "required": ["name"],
    "additionalProperties": False
}

REVIEW_CREATE_SCHEMA = {
    "type": "object",
    "properties": {
        "rating": {
            "type": "integer",
            "minimum": 1,
            "maximum": 5
        },
        "title": {
            "type": "string",
            "minLength": 3,
            "maxLength": 200
        },
        "comment": {
            "type": "string",
            "minLength": 10
        }
    },
    "required": ["rating", "title", "comment"],
    "additionalProperties": False
}


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for categories
    """
    slug = serializers.CharField(required=False, allow_blank=True)
    children = serializers.SerializerMethodField()
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = (
            'id', 'name', 'slug', 'description', 'image', 'parent', 
            'is_active', 'children', 'product_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_children(self, obj):
        """Get active children categories"""
        children = obj.get_children()
        return CategorySerializer(children, many=True).data
    
    def get_product_count(self, obj):
        """Get count of active products in this category"""
        return obj.products.filter(is_active=True).count()
    
    def validate(self, attrs):
        try:
            validate(attrs, CATEGORY_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        return attrs


class BrandSerializer(serializers.ModelSerializer):
    """
    Serializer for brands
    """
    product_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Brand
        fields = (
            'id', 'name', 'slug', 'description', 'logo', 'website', 
            'is_active', 'product_count', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'created_at', 'updated_at')
    
    def get_product_count(self, obj):
        """Get count of active products for this brand"""
        return obj.products.filter(is_active=True).count()
    
    def validate(self, attrs):
        try:
            validate(attrs, BRAND_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        return attrs


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer for product images
    """
    class Meta:
        model = ProductImage
        fields = ('id', 'image', 'alt_text', 'is_primary', 'order', 'created_at')
        read_only_fields = ('id', 'created_at')


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer for product variants
    """
    current_price = serializers.ReadOnlyField()
    
    class Meta:
        model = ProductVariant
        fields = (
            'id', 'name', 'sku', 'price_adjustment', 'stock_quantity', 
            'is_active', 'current_price', 'created_at'
        )
        read_only_fields = ('id', 'current_price', 'created_at')


class ProductSpecificationSerializer(serializers.ModelSerializer):
    """
    Serializer for product specifications
    """
    class Meta:
        model = ProductSpecification
        fields = ('id', 'name', 'value', 'order')
        read_only_fields = ('id',)


class ProductReviewSerializer(serializers.ModelSerializer):
    """
    Serializer for product reviews
    """
    user = serializers.ReadOnlyField(source='user.email')
    user_full_name = serializers.ReadOnlyField(source='user.full_name')
    
    class Meta:
        model = ProductReview
        fields = (
            'id', 'product', 'user', 'user_full_name', 'rating', 'title', 
            'comment', 'is_verified_purchase', 'is_approved', 'created_at', 'updated_at'
        )
        read_only_fields = ('id', 'user', 'is_verified_purchase', 'is_approved', 'created_at', 'updated_at')
    
    def validate(self, attrs):
        try:
            validate(attrs, REVIEW_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        
        # Check if user has already reviewed this product
        user = self.context['request'].user
        product = attrs['product']
        if ProductReview.objects.filter(product=product, user=user).exists():
            raise serializers.ValidationError({
                'error': 'Review already exists',
                'details': 'You have already reviewed this product.'
            })
        
        return attrs


class ProductTagSerializer(serializers.ModelSerializer):
    """
    Serializer for product tags
    """
    class Meta:
        model = ProductTag
        fields = ('id', 'name', 'slug', 'created_at')
        read_only_fields = ('id', 'slug', 'created_at')


class ProductSerializer(serializers.ModelSerializer):
    """
    Serializer for products with nested relationships
    """
    category = CategorySerializer(read_only=True)
    brand = BrandSerializer(read_only=True)
    vendor = serializers.ReadOnlyField(source='vendor.email')
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    specifications = ProductSpecificationSerializer(many=True, read_only=True)
    reviews = ProductReviewSerializer(many=True, read_only=True)
    tags = ProductTagSerializer(many=True, read_only=True)
    
    # Computed fields
    current_price = serializers.ReadOnlyField()
    discount_percentage = serializers.ReadOnlyField()
    is_on_sale = serializers.ReadOnlyField()
    is_low_stock = serializers.ReadOnlyField()
    is_out_of_stock = serializers.ReadOnlyField()
    average_rating = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = (
            'id', 'name', 'slug', 'description', 'short_description',
            'vendor', 'category', 'brand', 'base_price', 'sale_price',
            'current_price', 'discount_percentage', 'is_on_sale',
            'sku', 'stock_quantity', 'low_stock_threshold',
            'is_low_stock', 'is_out_of_stock', 'condition', 'weight',
            'dimensions', 'status', 'is_featured', 'is_active',
            'meta_title', 'meta_description', 'meta_keywords',
            'images', 'variants', 'specifications', 'reviews', 'tags',
            'average_rating', 'review_count', 'created_at', 'updated_at', 'published_at'
        )
        read_only_fields = (
            'id', 'slug', 'sku', 'current_price', 'discount_percentage',
            'is_on_sale', 'is_low_stock', 'is_out_of_stock', 'average_rating',
            'review_count', 'created_at', 'updated_at', 'published_at'
        )
    
    def get_average_rating(self, obj):
        """Calculate average rating from approved reviews"""
        approved_reviews = obj.reviews.filter(is_approved=True)
        if approved_reviews.exists():
            return sum(review.rating for review in approved_reviews) / approved_reviews.count()
        return 0
    
    def get_review_count(self, obj):
        """Get count of approved reviews"""
        return obj.reviews.filter(is_approved=True).count()
    
    def validate(self, attrs):
        try:
            validate(attrs, PRODUCT_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        
        # Validate sale price is less than base price
        if attrs.get('sale_price') and attrs.get('base_price'):
            if attrs['sale_price'] >= attrs['base_price']:
                raise serializers.ValidationError({
                    'error': 'Invalid sale price',
                    'details': 'Sale price must be less than base price.'
                })
        
        return attrs


class ProductCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating products
    """
    slug = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Product
        fields = (
            'name', 'slug', 'description', 'short_description', 'category', 'brand',
            'base_price', 'sale_price', 'stock_quantity', 'low_stock_threshold',
            'condition', 'weight', 'dimensions', 'status', 'is_featured',
            'meta_title', 'meta_description', 'meta_keywords'
        )
    
    def validate(self, attrs):
        try:
            validate(attrs, PRODUCT_CREATE_SCHEMA)
        except JSONSchemaValidationError as e:
            raise serializers.ValidationError({
                'error': 'Validation failed',
                'details': f"Schema validation failed: {e.message}"
            })
        
        # Validate sale price is less than base price
        if attrs.get('sale_price') and attrs.get('base_price'):
            if attrs['sale_price'] >= attrs['base_price']:
                raise serializers.ValidationError({
                    'error': 'Invalid sale price',
                    'details': 'Sale price must be less than base price.'
                })
        
        return attrs
    
    def create(self, validated_data):
        # Set the vendor to the current user
        validated_data['vendor'] = self.context['request'].user
        return super().create(validated_data)