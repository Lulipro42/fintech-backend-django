from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status,response
from django.db import transaction, IntegrityError  # Escudo protector para transacciones atómicas
from .serializers import (
    UserSerializer, ProfileSerializer, TransactionSerializer, 
    TransactionHistorialSerializer, WalletSerializer,DepostivoSerializer,RetiroSerializer
)
from .models import Wallet, Transtaction, Profile  # Mantenido 'Transtaction' según tu modelo
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.db.models import Q
from django.core.exceptions import ValidationError
from rest_framework.throttling import UserRateThrottle
from rest_framework.pagination import PageNumberPagination
import logging

# Create your views here.
# ==========================================
# REGISTRO DE USUARIO, PERFIL Y BILLETERA
# ==========================================
logger = logging.getLogger(__name__)


class RegistroUsuarioView(APIView):
    def post(self, request):
        data_usuario = request.data
        data_perfil = request.data.get('profile')  # Bloque de datos anidado para el perfil
        
        # Capturamos la moneda opcional que mande el cliente (si no manda nada, va 'ARS' por defecto)
        moneda_elegida = request.data.get('moneda', 'ARS')
        
        # Activamos la transacción atómica: si algo falla adentro, no se crea nada en la DB
        try:
            with transaction.atomic():
                # 1. Validamos y creamos el usuario base (encriptando contraseña)
                seralizer_user = UserSerializer(data=data_usuario)
                seralizer_user.is_valid(raise_exception=True)
                usuario = seralizer_user.save()
            
                # 2. Validamos y creamos el perfil asociado
                seriliazer_perfil = ProfileSerializer(data=data_perfil)
                seriliazer_perfil.is_valid(raise_exception=True)
                perfil = seriliazer_perfil.save(user=usuario)
            
                # 3. Creamos la billetera asignándole la moneda correspondiente
                wallet = Wallet.objects.create(
                    user=usuario,
                    saldo=Decimal('0.00'),
                    moneda=moneda_elegida  # Guarda la billetera en la moneda que corresponda
                    )
            
                return Response(
                    {"mensaje": "Usuario, perfil y billetera creados con éxito"}, 
                    status=status.HTTP_201_CREATED
                )
                
        except ValueError as e:
            return Response({
                "detail": str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
# ==========================================
# CONSULTA RÁPIDA DE SALDO
# ==========================================
class SaldoWalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Buscamos la billetera que le pertenece al usuario autenticado
        billetera = Wallet.objects.filter(user=request.user).first()
        
        # 2. Validamos si el usuario realmente tiene una billetera asociada
        if billetera is not None:
            # Si existe, devolvemos el saldo junto con su tipo de moneda
            return Response({
                "saldo": billetera.saldo,
                "moneda": billetera.moneda
            })
        else:
            return Response({
                "detail": "Este usuario no tiene una billetera asociada"
            }, status=status.HTTP_404_NOT_FOUND)

# ==========================================
# ENVIAR DINERO A OTRA BILLETERA
# ==========================================
class TransferenciaView(APIView):
    permission_classes = [IsAuthenticated]
    
    throttle_classes = [UserRateThrottle]
    
    def post(self, request):
        # 1. Buscamos la billetera del usuario de origen (select_related optimiza la consulta SQL)
        billetera_origen = Wallet.objects.select_related('user').filter(user=request.user).first()
        
        if not billetera_origen:
            return Response({
                "detail": "El usuario no posee una billetera activa"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 2. Instanciamos el serializador pasándole el contexto del request para las validaciones
        serializer = TransactionSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # 3. Extraemos el monto y la billetera destino ya validados por el Serializer
        monto = serializer.validated_data.get('monto')
        billetera_destino = serializer.validated_data.get('billetera_destino')

        # 1. Extraé la idempotency_key de los datos validados (puede no venir, usá .get())
        idempotency_key = serializer.validated_data.get('idempotency_key') # Aca con el tema de uqe me dijiste para validar los datros obte por el billetrea origen ya que es el que tiene los datros del usuario, como para poder verificarlos
        
        if idempotency_key: # Bueno aca tambien use mi logica 
            transaccion_existe = Transtaction.objects.filter(idempotency_key=idempotency_key).exists()

            if transaccion_existe:
                return Response({
                    "detail":"Transferencia ya procesada anteriormente"
                }, status=status.HTTP_200_OK)
            # Iniciamos el proceso crítico de transferencia en la base de datos
# 👇 Ahora SIEMPRE se ejecuta, tenga o no idempotency_key
        with transaction.atomic():
            id_origen = billetera_origen.id
            id_destino = billetera_destino.id
            ids_ordenados = sorted([id_origen, id_destino])
            wallet_a = Wallet.objects.select_for_update().get(id=ids_ordenados[0])
            wallet_b = Wallet.objects.select_for_update().get(id=ids_ordenados[1])
    
            if wallet_a.user == request.user:
                billetera_origen = wallet_a
                billetera_destino = wallet_b
            else:
                billetera_origen = wallet_b
                billetera_destino = wallet_a
    
            if billetera_origen.saldo < monto:
                raise ValueError("Fondos insuficientes")
    
            billetera_origen.saldo -= monto
            billetera_origen.save()
            billetera_destino.saldo += monto
            billetera_destino.save()
    
            Transtaction.objects.create(
                wallet_origen=billetera_origen,
                walle_destino=billetera_destino,
                monto=monto,
                idempotency_key=idempotency_key,
            )

        return Response({"detail": "Transferencia procesada con éxito"}, status=status.HTTP_200_OK)
            

# ==========================================
# HISTORIAL DE MOVIMIENTOS (ENTRANTES Y SALIENTES)
# ==========================================
class HistorialTransactionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Buscamos la billetera del usuario logueado
        billetera_usuario = Wallet.objects.filter(user=request.user).first()
        if not billetera_usuario:
            return Response({
                "detail": "El usuario no tiene una billetera"
            }, status=status.HTTP_404_NOT_FOUND)
            
        # 2. Filtramos transacciones donde el usuario sea origen O destino usando Q
        transacciones = Transtaction.objects.select_related('wallet_origen', 'walle_destino').filter(
            Q(wallet_origen=billetera_usuario) | Q(walle_destino=billetera_usuario)
        ).order_by('-id')  # Ordenado del más reciente al más antiguo
        
        
        paginator = PageNumberPagination()
        paginator.page_size = 10
        
        result_page = paginator.paginate_queryset(transacciones, request)
        
        serializer = TransactionHistorialSerializer(result_page, many=True)
        
        return paginator.get_paginated_response(serializer.data)
    
# ==========================================
# DEPOSITAR DINERO DESDE EL BANCO externos
# ==========================================
class DepostivoView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        billetera = Wallet.objects.filter(user=request.user).first()
        if not billetera:
            return Response({"detail":"El usuario no posee una billetera activa"},status=status.HTTP_404_NOT_FOUND)
        
        # 1. Pasamos los datos al serializer
        serializer = DepostivoSerializer(data=request.data)
        
        # 2. Si el serializer no es válido, devuelve un error 400 automáticamente
        # con el formato que ya definimos en el exception_handler
        serializer.is_valid(raise_exception=True)

        monto = serializer.validated_data['monto']


        
        with transaction.atomic():
            billetera.saldo += monto
            billetera.save()
            
            Transtaction.objects.create(
                wallet_origen=None,
                walle_destino=billetera,
                monto=monto
            )
        
        return Response(
            {"detail": f"Depósito exitoso en tu cuenta de {billetera.moneda}."}, 
            status=status.HTTP_200_OK
        )
# ==========================================
# RETIRAR DINERO HACIA FUERA DEL SISTEMA
# ==========================================
class RetiroMoneyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        wallet_origen = Wallet.objects.filter(user=request.user).select_related('user').first()
        if not wallet_origen:
            return Response({
                "detail":"No posee billetera activa"
            },status=status.HTTP_404_NOT_FOUND)
            

        serializer = RetiroSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        monto = serializer.validated_data['monto']


        if monto > wallet_origen.saldo:
            return Response({
                "detail":"Fondos insuficientes"
            },status=status.HTTP_400_BAD_REQUEST)
        
        with transaction.atomic():
            wallet_origen.saldo -= monto
            wallet_origen.save()
            
            Transtaction.objects.create(
                wallet_origen=wallet_origen,
                walle_destino=None,
                monto=monto
            )
            
        return Response({"detail":"Retiro procesado"},status=status.HTTP_200_OK)
            
# ==========================================
# CONSULTA COMPLETA DEL ESTADO DE LA BILLETERA
# ==========================================
class MiBilleteraView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        # 1. Buscamos el estado global de la billetera del usuario
        billetera = Wallet.objects.select_related('user').filter(user=request.user).first()
        
        if not billetera:
            return Response({
                "detail": "El usuario no tiene una billetera asociada"
            }, status=status.HTTP_404_NOT_FOUND)
            
        # 2. Transformamos la información usando el serializador (incluye saldo, alias, cvu y moneda)
        serializer = WalletSerializer(billetera)
        
        # 3. Retornamos los datos limpios estructurados hacia el cliente
        return Response(serializer.data, status=status.HTTP_200_OK)
