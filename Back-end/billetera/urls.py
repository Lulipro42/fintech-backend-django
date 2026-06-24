from django.urls import path
from .views import RegistroUsuarioView

urlpatterns = [
    # Definimos la ruta para el registro de usuarios
    path('registro/', RegistroUsuarioView.as_view(), name='registro_usuario'),
]