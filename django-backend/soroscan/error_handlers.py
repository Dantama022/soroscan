"""
Custom error handlers that return JSON responses instead of HTML.
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods


def custom_404(request, exception=None):
    """
    Handle 404 errors by returning JSON response.
    
    This handler is triggered when a requested resource is not found.
    """
    return JsonResponse(
        {
            'error': 'Not Found',
            'status_code': 404,
            'message': 'The requested resource was not found.',
        },
        status=404,
        content_type='application/json',
    )


def custom_500(request):
    """
    Handle 500 errors by returning JSON response.
    
    This handler is triggered when an unexpected server error occurs.
    """
    return JsonResponse(
        {
            'error': 'Internal Server Error',
            'status_code': 500,
            'message': 'An unexpected error occurred on the server.',
        },
        status=500,
        content_type='application/json',
    )
