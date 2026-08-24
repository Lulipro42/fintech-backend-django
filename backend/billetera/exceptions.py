import logging
import traceback
from rest_framework.views import exception_handler
from rest_framework.response import Response

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    # Imprimir traceback real
    traceback.print_exc()
    
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
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