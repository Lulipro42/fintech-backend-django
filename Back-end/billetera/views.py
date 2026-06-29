from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction, IntegrityError  # Escudo protector para transacciones atómicas
from .serializers import (
    UserSerializer, ProfileSerializer, TransactionSerializer, 
    TransactionHistorialSerializer, WalletSerializer
)
from .models import Wallet, Transtaction, Profile  # Mantenido 'Transtaction' según tu modelo
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.db.models import Q
# Create your views here.
# ==========================================
# REGISTRO DE USUARIO, PERFIL Y BILLETERA
# ==========================================
class RegistroUsuarioView(APIView):
    def post(self, request):
        data_usuario = request.data
        data_perfil = request.data.get('profile')  # Bloque de datos anidado para el perfil
        
        # Capturamos la moneda opcional que mande el cliente (si no manda nada, va 'ARS' por defecto)
        moneda_elegida = request.data.get('moneda', 'ARS')
        
        # Activamos la transacción atómica: si algo falla adentro, no se crea nada en la DB
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
        
        try:
            # Iniciamos el proceso crítico de transferencia en la base de datos
            with transaction.atomic():
                # Restamos el saldo de la billetera de origen
                billetera_origen.saldo -= monto
                billetera_origen.save()
                
                # Sumamos el saldo a la billetera de destino
                billetera_destino.saldo += monto
                billetera_destino.save()
                
                # Registramos el movimiento histórico del dinero
                Transtaction.objects.create(
                    wallet_origen=billetera_origen,
                    walle_destino=billetera_destino,
                    monto=monto
                )
            
            return Response({
                "detail": "Transferencia procesada con éxito (débito real)"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "detail": f"Ocurrió un error en el servidor, lo sentimos: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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
        
        # 3. Pasamos la lista de transacciones por el serializador histórico
        serializer = TransactionHistorialSerializer(transacciones, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
# ==========================================
# DEPOSITAR DINERO DESDE EL BANCO externos
# ==========================================
class DepostivoView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # 1. Obtenemos la billetera del usuario
        billetera = Wallet.objects.filter(user=request.user).first()
        if not billetera:
            return Response({
                "detail": "El usuario no posee una billetera activa."
            }, status=status.HTTP_404_NOT_FOUND)

        monto_raw = request.data.get("monto")
        if not monto_raw:
            return Response({
                "detail": "El monto no es válido"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 2. Intentamos convertir el string a Decimal de forma segura
        try:
            monto = Decimal(str(monto_raw))
        except (TypeError, ValueError):
            return Response({
                "detail": "Formato de monto inválido"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 3. Validamos que el depósito sea una cifra positiva
        if monto <= 0:
            return Response({
                "detail": "El monto debe ser mayor a cero"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Modificamos la DB de forma segura
            with transaction.atomic():
                billetera.saldo += monto
                billetera.save()

                # Registramos el depósito (wallet_origen queda en None porque entra de afuera)
                Transtaction.objects.create(
                    wallet_origen=None,
                    walle_destino=billetera,
                    monto=monto
                )
            
            return Response({
                "detail": f"Depósito exitoso en tu cuenta de {billetera.moneda}."
            }, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "detail": f"Hubo un error en el servidor, lo sentimos: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# ==========================================
# RETIRAR DINERO HACIA FUERA DEL SISTEMA
# ==========================================
class RetiroMoneyView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # 1. Cargamos la billetera del usuario
        wallet_origen = Wallet.objects.filter(user=request.user).select_related('user').first()
        
        if not wallet_origen:
            return Response({
                "detail": "El usuario no posee una billetera activa."
            }, status=status.HTTP_404_NOT_FOUND)
        
        monto_raw = request.data.get('monto')
        
        # 2. Validación de formato numérico decimal
        try:
            monto = Decimal(str(monto_raw))
        except (TypeError, ValueError):
            return Response({
                "detail": "Formato de monto inválido"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # 3. El monto a retirar no puede ser cero ni negativo
        if monto <= 0:
            return Response({
                "detail": "El monto debe ser mayor a cero"
            }, status=status.HTTP_400_BAD_REQUEST) 
            
        # 4. Control estricto de fondos disponibles
        if monto > wallet_origen.saldo:
            return Response({
                "detail": "Fondos insuficientes para realizar el retiro"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            # Impactamos los cambios de forma atómica
            with transaction.atomic():
                wallet_origen.saldo -= monto
                wallet_origen.save()
                
                # Registramos el retiro (walle_destino queda en None porque sale del ecosistema)
                Transtaction.objects.create(
                    wallet_origen=wallet_origen,
                    walle_destino=None,
                    monto=monto
                )
                
                return Response({
                    "detail": "Retiro procesado de forma correcta"
                }, status=status.HTTP_200_OK)
                
        except Exception as e:
            return Response({
                "detail": f"El servidor falló, lo sentimos: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
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