import logging
import traceback
from rest_framework.views import exception_handler
from rest_framework.response import Response
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError as DRFValidationError
logger = logging.getLogger(__name__)



def custom_exception_handler(exc, context):
    traceback.print_exc()
    
    # Manejar explícitamente el ValidationError de Django y transformarlo en 400
    if isinstance(exc, DjangoValidationError):
        message = exc.messages if hasattr(exc, 'messages') else str(exc)
        return Response({
            "error": True,
            "message": message,
            "code": 400
        }, status=400)

    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            "error": "true" if response.status_code >= 400 else False,
            "error": True,
            "message": response.data.get('detail', 'Ocurrio un error en el servidor. lo sentimos'),
            "code": response.status_code
        }
        response.data = custom_response_data
        return response
    
    if isinstance(exc, ValueError):
        return Response({
            "error": True,
            "message": str(exc),
            "code": 400
        }, status=400)
        
    logger.error(f"Error critico no controlado: {str(exc)}", exc_info=True)
    return Response({
        "error": True,
        "message": "Ocurrio un error interno en el servidor",
        "code": 500
    }, status=500)