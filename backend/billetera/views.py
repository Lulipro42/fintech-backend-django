from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status,response
from django.db import transaction, IntegrityError  # Escudo protector para transacciones atómicas
from .serializers import (
    UserSerializer, ProfileSerializer, TransactionSerializer, 
    TransactionHistorialSerializer, WalletSerializer,DepostivoSerializer,RetiroSerializer
)
from .models import Wallet, Transaction, Profile  # Mantenido 'Transtaction' según tu modelo
from rest_framework.permissions import IsAuthenticated, AllowAny
from decimal import Decimal
from django.db.models import Q, F
from django.core.exceptions import ValidationError
from rest_framework.throttling import UserRateThrottle
from rest_framework.pagination import PageNumberPagination
import logging
import json
import time






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
        billetera = Wallet.objects.select_related('user').filter(user=request.user).first()
        
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
    #permission_classes = [IsAuthenticated]
    #throttle_classes = [UserRateThrottle]

    def post(self, request):
        start_time = time.time()
        status_log = "ok"
        error_log = None
        billetera_origen = None
        billetera_destino = None

        try:
            serializer = TransactionSerializer(data=request.data, context={'request': request})
            serializer.is_valid(raise_exception=True)

            monto = serializer.validated_data.get('monto')
            billetera_destino_id = serializer.validated_data.get('billetera_destino').id
            idempotency_key = serializer.validated_data.get('idempotency_key')

            # Obtener ID de la billetera origen del usuario autenticado
            billetera_origen_id = Wallet.objects.filter(user=request.user).values_list('id', flat=True).first()
            
            if not billetera_origen_id:
                status_log = "error"
                error_log = "Usuario sin billetera"
                return Response(
                    {"detail": "El usuario no posee una billetera activa"},
                    status=status.HTTP_404_NOT_FOUND
                )

            with transaction.atomic():
                # Bloqueo ordenado por ID para evitar deadlock
                wallet_ids = sorted([billetera_origen_id, billetera_destino_id])
                wallets = list(Wallet.objects.select_for_update().filter(id__in=wallet_ids).order_by('id'))

                if len(wallets) != 2:
                    raise ValidationError("Las billeteras no son válidas")

                wallet_a, wallet_b = wallets
                
                if wallet_a.id == billetera_origen_id:
                    billetera_origen = wallet_a
                    billetera_destino = wallet_b
                else:
                    billetera_origen = wallet_b
                    billetera_destino = wallet_a

                # Idempotencia: intentar crear, si existe → ya procesado
                if idempotency_key:
                    try:
                        Transaction.objects.create(
                            wallet_origen=billetera_origen,
                            wallet_destino=billetera_destino,
                            monto=monto,
                            idempotency_key=idempotency_key,
                        )
                    except IntegrityError:
                        status_log = "idempotencia"
                        error_log = "Transferencia ya procesada"
                        return Response(
                            {"detail": "Transferencia ya procesada anteriormente"},
                            status=status.HTTP_200_OK)
                else:
                    Transaction.objects.create(
                        wallet_origen=billetera_origen,
                        wallet_destino=billetera_destino,
                        monto=monto,
                    )

                if billetera_origen.saldo < monto:
                    raise ValidationError("Fondos insuficientes")

                billetera_origen.saldo -= monto
                billetera_destino.saldo += monto
                
                billetera_origen.save(update_fields=['saldo'])
                billetera_destino.save(update_fields=['saldo'])

            return Response(
                {"detail": "Transferencia procesada con éxito"},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            status_log = "error"
            error_log = str(e)
            raise

        finally:
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            logger.info(json.dumps({
                "event": "transferencia",
                "origen_id": str(billetera_origen.id) if billetera_origen else None,
                "destino_id": str(billetera_destino.id) if billetera_destino else None,
                "monto": str(monto) if 'monto' in locals() else None,
                "status": status_log,
                "duration_ms": duration_ms,
                "error": error_log,
            }))


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
        transacciones = Transaction.objects.select_related('wallet_origen__user', 'walle_destino__user').filter(
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
            
            Transaction.objects.create(
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
            
            Transaction.objects.create(
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
