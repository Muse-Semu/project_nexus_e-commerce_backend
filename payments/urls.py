from django.urls import path
from .views import chapa_webhook, payment_status, payment_webhook

urlpatterns = [
    path('webhook/chapa/', chapa_webhook, name='chapa-webhook'),
    path('webhook/', payment_webhook, name='payment-webhook'),
    path('status/<str:transaction_id>/', payment_status, name='payment-status'),
] 