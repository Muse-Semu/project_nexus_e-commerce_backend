# from django.db.models.signals import post_save, post_delete
# from django.dispatch import receiver
# from .models import Product, ProductReview
# from .tasks import (
#     send_low_stock_notification, send_out_of_stock_notification,
#     update_product_search_index, process_product_images
# )
# import logging

# logger = logging.getLogger(__name__)


# @receiver(post_save, sender=Product)
# def handle_product_stock_changes(sender, instance, created, **kwargs):
#     """
#     Handle product stock changes and send notifications
#     """
#     if not created:  # Only for updates
#         # Check if stock quantity changed
#         if hasattr(instance, '_stock_quantity_old'):
#             old_stock = instance._stock_quantity_old
#             new_stock = instance.stock_quantity
            
#             # Low stock notification
#             if (new_stock <= instance.low_stock_threshold and 
#                 new_stock > 0 and old_stock > instance.low_stock_threshold):
#                 try:
#                     send_low_stock_notification.delay(instance.id)
#                     logger.info(f"Low stock notification triggered for product {instance.id}")
#                 except Exception as e:
#                     logger.error(f"Error sending low stock notification: {e}")
            
#             # Out of stock notification
#             if new_stock == 0 and old_stock > 0:
#                 try:
#                     send_out_of_stock_notification.delay(instance.id)
#                     logger.info(f"Out of stock notification triggered for product {instance.id}")
#                 except Exception as e:
#                     logger.error(f"Error sending out of stock notification: {e}")


# @receiver(post_save, sender=Product)
# def update_search_index_on_product_save(sender, instance, created, **kwargs):
#     """
#     Update search index when product is saved
#     """
#     try:
#         update_product_search_index.delay(instance.id)
#         logger.info(f"Search index update triggered for product {instance.id}")
#     except Exception as e:
#         logger.error(f"Error updating search index: {e}")


# @receiver(post_save, sender=Product)
# def process_images_on_product_save(sender, instance, created, **kwargs):
#     """
#     Process product images when product is saved
#     """
#     if created:  # Only for new products
#         try:
#             process_product_images.delay(instance.id)
#             logger.info(f"Image processing triggered for product {instance.id}")
#         except Exception as e:
#             logger.error(f"Error processing product images: {e}")


# @receiver(post_delete, sender=Product)
# def update_search_index_on_product_delete(sender, instance, **kwargs):
#     """
#     Update search index when product is deleted
#     """
#     try:
#         # This would remove the product from search index
#         logger.info(f"Product {instance.id} removed from search index")
#     except Exception as e:
#         logger.error(f"Error removing product from search index: {e}")


# @receiver(post_save, sender=ProductReview)
# def handle_review_approval(sender, instance, created, **kwargs):
#     """
#     Handle review approval and update product rating
#     """
#     if not created and instance.is_approved:
#         try:
#             # Update product search index when review is approved
#             update_product_search_index.delay(instance.product.id)
#             logger.info(f"Search index updated after review approval for product {instance.product.id}")
#         except Exception as e:
#             logger.error(f"Error updating search index after review approval: {e}")


# def save_stock_quantity_old(sender, instance, **kwargs):
#     """
#     Save the old stock quantity before saving
#     """
#     if instance.pk:  # Only for existing instances
#         try:
#             old_instance = Product.objects.get(pk=instance.pk)
#             instance._stock_quantity_old = old_instance.stock_quantity
#         except Product.DoesNotExist:
#             instance._stock_quantity_old = 0


# # Connect the signal to save the old stock quantity
# from django.db.models.signals import pre_save
# pre_save.connect(save_stock_quantity_old, sender=Product) 