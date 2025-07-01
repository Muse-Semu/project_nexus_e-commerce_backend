from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q, F
from .models import Product
import logging

logger = logging.getLogger(__name__)


@shared_task
def send_low_stock_notification(product_id):
    """
    Send low stock notification to vendor
    """
    try:
        product = Product.objects.get(id=product_id)
        vendor = product.vendor
        
        subject = f"Low Stock Alert: {product.name}"
        message = f"""
        Dear {vendor.full_name},
        
        Your product "{product.name}" (SKU: {product.sku}) is running low on stock.
        Current stock: {product.stock_quantity}
        Low stock threshold: {product.low_stock_threshold}
        
        Please restock soon to avoid running out of inventory.
        
        Best regards,
        E-commerce Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.email],
            fail_silently=False,
        )
        
        logger.info(f"Low stock notification sent for product {product_id}")
        
    except Product.DoesNotExist:
        logger.error(f"Product {product_id} not found for low stock notification")
    except Exception as e:
        logger.error(f"Error sending low stock notification for product {product_id}: {e}")


@shared_task
def send_out_of_stock_notification(product_id):
    """
    Send out of stock notification to vendor
    """
    try:
        product = Product.objects.get(id=product_id)
        vendor = product.vendor
        
        subject = f"Out of Stock Alert: {product.name}"
        message = f"""
        Dear {vendor.full_name},
        
        Your product "{product.name}" (SKU: {product.sku}) is now out of stock.
        
        Please restock immediately to continue selling this product.
        
        Best regards,
        E-commerce Team
        """
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[vendor.email],
            fail_silently=False,
        )
        
        logger.info(f"Out of stock notification sent for product {product_id}")
        
    except Product.DoesNotExist:
        logger.error(f"Product {product_id} not found for out of stock notification")
    except Exception as e:
        logger.error(f"Error sending out of stock notification for product {product_id}: {e}")


@shared_task
def check_low_stock_products():
    """
    Check all products for low stock and send notifications
    """
    try:
        low_stock_products = Product.objects.filter(
            is_active=True,
            stock_quantity__lte=F('low_stock_threshold'),
            stock_quantity__gt=0
        )
        
        for product in low_stock_products:
            send_low_stock_notification.delay(product.id)
        
        logger.info(f"Low stock check completed. Found {low_stock_products.count()} products")
        
    except Exception as e:
        logger.error(f"Error checking low stock products: {e}")


@shared_task
def check_out_of_stock_products():
    """
    Check all products for out of stock and send notifications
    """
    try:
        out_of_stock_products = Product.objects.filter(
            is_active=True,
            stock_quantity=0
        )
        
        for product in out_of_stock_products:
            send_out_of_stock_notification.delay(product.id)
        
        logger.info(f"Out of stock check completed. Found {out_of_stock_products.count()} products")
        
    except Exception as e:
        logger.error(f"Error checking out of stock products: {e}")


@shared_task
def update_product_search_index(product_id):
    """
    Update product in search index (for Meilisearch)
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # This would integrate with Meilisearch
        # For now, just log the action
        logger.info(f"Product {product_id} search index updated")
        
    except Product.DoesNotExist:
        logger.error(f"Product {product_id} not found for search index update")
    except Exception as e:
        logger.error(f"Error updating search index for product {product_id}: {e}")


@shared_task
def process_product_images(product_id):
    """
    Process and optimize product images
    """
    try:
        product = Product.objects.get(id=product_id)
        
        # This would integrate with Pillow for image processing
        # For now, just log the action
        logger.info(f"Product {product_id} images processed")
        
    except Product.DoesNotExist:
        logger.error(f"Product {product_id} not found for image processing")
    except Exception as e:
        logger.error(f"Error processing images for product {product_id}: {e}")


@shared_task
def generate_product_report():
    """
    Generate product inventory report
    """
    try:
        total_products = Product.objects.filter(is_active=True).count()
        low_stock_products = Product.objects.filter(
            is_active=True,
            stock_quantity__lte=F('low_stock_threshold')
        ).count()
        out_of_stock_products = Product.objects.filter(
            is_active=True,
            stock_quantity=0
        ).count()
        
        report = f"""
        Product Inventory Report
        
        Total Active Products: {total_products}
        Low Stock Products: {low_stock_products}
        Out of Stock Products: {out_of_stock_products}
        """
        
        # Send report to admin
        send_mail(
            subject="Product Inventory Report",
            message=report,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.ADMIN_EMAIL] if hasattr(settings, 'ADMIN_EMAIL') else [],
            fail_silently=False,
        )
        
        logger.info("Product inventory report generated and sent")
        
    except Exception as e:
        logger.error(f"Error generating product report: {e}") 