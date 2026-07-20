import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response

logger = logging.getLogger(__name__)

def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    
    if response is not None:
        custom_response_data = {
            "error":True,
            "message":response.data.get('detail','Ocurrio un error en el servidor. lo sentimos'),
            "code": response.status_code
        }
        response.data = custom_response_data
        return response
    
    # 🆕 Caso específico: ValueError son errores de negocio (fondos insuficientes, etc) → 400
    if isinstance(exc, ValueError):
        return Response({
            "error":True,
            "message":str(exc),
            "code":400
        },status=400)
        
    # Cualquier otra cosa no contemplada → 500, con logging
    logger.error(f"Error critico no controlado: {str(exc)}", exc_info=True)
    return Response({
        "error":True,
        "message": "Ocurrio un error interno en el servidor",
        "code": 500
    }, status=500)