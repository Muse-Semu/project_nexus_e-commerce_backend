from django.urls import path
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """Health check endpoint"""
    return JsonResponse({
        'status': 'healthy',
        'message': 'E-commerce Backend is running'
    })


@csrf_exempt
@require_http_methods(["POST"])
def webhook_handler(request):
    """Generic webhook handler"""
    try:
        data = json.loads(request.body)
        return JsonResponse({
            'status': 'success',
            'message': 'Webhook received'
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid JSON'
        }, status=400)


urlpatterns = [
    path('', health_check, name='health_check'),
    path('webhook/', webhook_handler, name='webhook_handler'),
] 