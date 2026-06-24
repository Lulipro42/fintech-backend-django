from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction  # 👈 Para activar el escudo de transacciones atómicas
from .serializers import UserSerializer, ProfileSerializer
from .models import Wallet

# Create your views here.
class RegistroUsuarioView(APIView):
    def post(self, request):
        data_usuario = request.data
        data_perfil = request.data.get('profile') # El bloque anidado
        
        # 2. Activamos la transacción atómica
        with transaction.atomic():
            # 1. Instanciamos el serializador con los datos del usuario
            seralizer_user = UserSerializer(data=data_usuario)
            
            # 2. Validamos (si falla, DRF corta acá y devuelve el error al frontend)
            seralizer_user.is_valid(raise_exception=True)
            
            # 3. Guardamos el usuario en memoria/base de datos
            usuario = seralizer_user.save()
            
            # 4. Encriptamos la contraseña usando tu lógica anterior
            usuario.set_password(usuario.password)
            usuario.save()
            
            # This is serailizer Profile and actually i need the pass the code for the go japan 
            
            seriliazer_perfil = ProfileSerializer(data=data_perfil) # for her called profileseralizer
            
            seriliazer_perfil.is_valid(raise_exception=True) # And then validate this code 
            
            perfil = seriliazer_perfil.save()

            
            # This is Wallet
            
            wallet = Wallet.objects.create( # And this is a new list for me create 
                user='usuario',
                saldo=0.0
            )
            
            return Response(
                {"mensaje": "Usuario, perfil y billetera creados con exito"}, status=status.HTTP_201_CREATED
            )