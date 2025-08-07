from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Category, Brand, Product, ProductImage, ProductVariant, 
    ProductSpecification, ProductReview, ProductTag
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'parent', 'is_active', 'product_count', 'created_at')
    list_filter = ('is_active', 'parent', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    def product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    product_count.short_description = 'Products'


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active', 'product_count', 'website', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at', 'updated_at')
    
    def product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    product_count.short_description = 'Products'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('image', 'alt_text', 'is_primary', 'order')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('name', 'sku', 'price_adjustment', 'stock_quantity', 'is_active')


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1
    fields = ('name', 'value', 'order')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'vendor', 'category', 'brand', 'current_price', 
        'stock_quantity', 'status', 'is_featured', 'is_active', 'created_at'
    )
    list_filter = (
        'status', 'condition', 'is_featured', 'is_active', 
        'category', 'brand', 'created_at'
    )
    search_fields = ('name', 'description', 'sku', 'vendor__email')
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = (
        'sku', 'current_price', 'discount_percentage', 'is_on_sale',
        'is_low_stock', 'is_out_of_stock', 'created_at', 'updated_at'
    )
    inlines = [ProductImageInline, ProductVariantInline, ProductSpecificationInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'description', 'short_description')
        }),
        ('Relationships', {
            'fields': ('vendor', 'category', 'brand')
        }),
        ('Pricing', {
            'fields': ('base_price', 'sale_price', 'cost_price')
        }),
        ('Inventory', {
            'fields': ('sku', 'stock_quantity', 'low_stock_threshold')
        }),
        ('Product Details', {
            'fields': ('condition', 'weight', 'dimensions')
        }),
        ('Status & Visibility', {
            'fields': ('status', 'is_featured', 'is_active')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description', 'meta_keywords'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'published_at'),
            'classes': ('collapse',)
        }),
    )
    
    def current_price(self, obj):
        return f"${obj.current_price}"
    current_price.short_description = 'Current Price'
    
    def discount_percentage(self, obj):
        if obj.discount_percentage > 0:
            return f"{obj.discount_percentage:.1f}%"
        return "-"
    discount_percentage.short_description = 'Discount'


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product', 'image_preview', 'alt_text', 'is_primary', 'order', 'created_at')
    list_filter = ('is_primary', 'created_at')
    search_fields = ('product__name', 'alt_text')
    readonly_fields = ('created_at',)
    
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 50px; max-width: 50px;" />',
                obj.image.url
            )
        return "No image"
    image_preview.short_description = 'Preview'


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'sku', 'price_adjustment', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('product__name', 'name', 'sku')
    readonly_fields = ('created_at',)


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'value', 'order')
    list_filter = ('order',)
    search_fields = ('product__name', 'name', 'value')
    ordering = ('product', 'order')


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = (
        'product', 'user', 'rating', 'title', 'is_verified_purchase', 
        'is_approved', 'created_at'
    )
    list_filter = ('rating', 'is_verified_purchase', 'is_approved', 'created_at')
    search_fields = ('product__name', 'user__email', 'title', 'comment')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['approve_reviews', 'reject_reviews']
    
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)
        self.message_user(request, f"{queryset.count()} reviews approved.")
    approve_reviews.short_description = "Approve selected reviews"
    
    def reject_reviews(self, request, queryset):
        queryset.update(is_approved=False)
        self.message_user(request, f"{queryset.count()} reviews rejected.")
    reject_reviews.short_description = "Reject selected reviews"


@admin.register(ProductTag)
class ProductTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'product_count', 'created_at')
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ('created_at',)
    
    def product_count(self, obj):
        return obj.products.filter(is_active=True).count()
    product_count.short_description = 'Products'
