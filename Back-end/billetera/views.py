from django.shortcuts import render, redirect, get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction, IntegrityError  # 👈 Para activar el escudo de transacciones atómicas
from .serializers import UserSerializer, ProfileSerializer,TransactionSerializer, TransactionHistorialSerializer, WalletSerializer
from .models import Wallet, Transtaction,Profile
from rest_framework.permissions import IsAuthenticated
from decimal import Decimal
from django.db.models import Q
# Create your views here.
class RegistroUsuarioView(APIView):
    def post(self, request):
        data_usuario = request.data
        data_perfil = request.data.get('profile') # El bloque anidado
        
        # 2. Activamos la transacción atómica
        with transaction.atomic():
            # 1. Instanciamos el serializador con los datos del usuario
            seralizer_user = UserSerializer(data=data_usuario)
            
            # 2. Validamos (si falla, DRF corta acá)
            seralizer_user.is_valid(raise_exception=True)
            
            # 3. ¡ESTO ES TODO! El serializador ahora crea y encripta al usuario al mismo tiempo
            usuario = seralizer_user.save()
            
            # (El resto del código de perfil y wallet queda igual abajo...)
            seriliazer_perfil = ProfileSerializer(data=data_perfil)
            seriliazer_perfil.is_valid(raise_exception=True)
            perfil = seriliazer_perfil.save(user=usuario)
            
            wallet = Wallet.objects.create(
                user=usuario,
                saldo=0.0
            )
            
            return Response(
                {"mensaje": "Usuario, perfil y billetera creados con exito"}, status=status.HTTP_201_CREATED
            )
            

#### ----------------------
        # SALDO DE LA BILLETERA 
### ----------------

class SaldoWalletView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self,request):
        # 1. Buscamos la billetera que le pertenece al usuario logueado
        billetera = Wallet.objects.filter(user=request.user).first()
        
        # 2. Validamos si el usuario realmente tiene una wallet creada
        if billetera is not None:
            # Si existe, extraemos y devolvemos su saldo real
            return Response({"saldo": billetera.saldo})
        else:
            # Si no existe, devolvemos un error controlado y un código 404
            return Response({
                "detail": "Este usuario no tiene una billetera asociada"
            }, status=404 )
            
            
#### ----------------------
        # ENVIAR DINERO A OTRA BILLETERA
### ----------------

class TransferenciaView(APIView):
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        # 1. Buscamos la billetera del usuario que está enviando la plata (Origen)
        billetera_origen = Wallet.objects.select_related('user').filter(user=request.user).first()
        
        if not billetera_origen:
            return Response({
                "detail":"El usuario no posee una billetera activa"
            }, status=status.HTTP_404_NOT_FOUND)
        
        # 2. Instanciás el serializador y ejecutás is_valid(raise_exception=True)
        serializer = TransactionSerializer(data=request.data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        
        # 3. Extraés monto y billetera_id desde serializer.validated_data
        monto = serializer.validated_data.get('monto')
        billetera_destino = serializer.validated_data.get('billetera_destino')
        
        try:
            with transaction.atomic():
                # Buscar la billetera destino
                
                # Cambiar los saldos
                billetera_origen.saldo -= monto
                billetera_origen.save()
                
                billetera_destino.saldo += monto
                billetera_destino.save()
                
                # Guardar la transacción (corregidos typos de 'Transtaction' y 'walle_destino')
                Transtaction.objects.create(
                    wallet_origen=billetera_origen,
                    walle_destino=billetera_destino,
                    monto=monto
                )
            
            return Response({
                "detail":"Transferencia procesada con exito (debito real)"
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "detail":f"Ocurrio un error en el servidor lo sentimos: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
### ------------------

# ---- HISTORIAL DE TRANSACCIONES

### ------------------

class HistorialTransactionsView(APIView):
    
    permission_classes = [IsAuthenticated]

    def get(self, request):

        billetera_usuario = Wallet.objects.filter(user=request.user).first()
        if not billetera_usuario:
            return Response({
                "detail":"El usuario no tiene una billetera"
            }, status=status.HTTP_404_NOT_FOUND )
            
            
        transacciones = Transtaction.objects.select_related('wallet_origen', 'walle_destino').filter(
            Q(wallet_origen=billetera_usuario) | # Sirve practicamente para remplazar a los filter que usan muchos Y en cambio Q usa como: |, &, ~ y nada mas
            Q(walle_destino=billetera_usuario)
        ).order_by('-id')
        
        serializer = TransactionHistorialSerializer(transacciones, many=True)
        
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    
class DepostivoView(APIView):
    
    permission_classes = [IsAuthenticated] # This is authenticated for the security for the user
    
    def post(self,request):
        billetera = Wallet.objects.filter(user=request.user).first() # Users Wallet
        if not billetera:
            return Response({
                "detail": "El usuario no posee una billetera activa."
            }, status=status.HTTP_404_NOT_FOUND)

        monto_raw = request.data.get("monto") # Get the amount from request data
        if not monto_raw:
            return Response({
                "detail":"El monto no es valido"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            monto = Decimal(str(monto_raw))
        except(TypeError, ValueError):
            return Response({
                "detail":"Invalid format"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        # Validate that the amount is greater than zero
        if monto <= 0:
            return Response({
                "detail":"The amount must be greater than zero"
            },status=status.HTTP_400_BAD_REQUEST )
            
        # Update the wallet balance and save
        try:
            with transaction.atomic():
                billetera.saldo += monto
                billetera.save()

                # Create the transaction record
                Transtaction.objects.create(
                    wallet_origen=None, # No origin wallet for deposits
                    walle_destino=billetera,
                    monto=monto
                )
            
            return Response({
                "detail":"Deposit successful."
            },status=status.HTTP_200_OK)

        except Exception as e:
            return Response({
                "detail":f"Hubo un error en el servidor lo sentimos:{str(e)}"
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            
## ----------

## RETIRAR DINERO DEL "BANCO"

# -----------

class RetiroMoneyView(APIView):
    
    permission_classes = [IsAuthenticated]
    
    def post(self,request):
        wallet_origen = Wallet.objects.filter(user=request.user).select_related(
            'user'
        ).first()
        
        monto_raw = request.data.get('monto') #Aca definimos la variable para que haga un data get y lo meta como monto
        
        try: # ACA hacemos un try/except
            monto = Decimal(str(monto_raw)) # Aca implementamos los decimales para que los numeros se cuenten bien 
        except(TypeError, ValueError):
            return Response({
                "detail":"Invalid format"
            }, status=status.HTTP_400_BAD_REQUEST)
            
        if monto  <= 0:
            return Response({
                "detail":"The amount must be greater than zero"
            }, status=status.HTTP_400_BAD_REQUEST) 
            
        if monto > wallet_origen.saldo:
            return Response({
                "detail":"Fondos insufientes para realizar el retiro"
            },status=status.HTTP_400_BAD_REQUEST)
            
        try:
            with transaction.atomic():
                wallet_origen.saldo -= monto
                wallet_origen.save()
                
                Transtaction.objects.create(
                    wallet_origen=wallet_origen,
                    walle_destino=None,
                    monto=monto
                    
                )
                
                return Response({
                    "detail":"La creacion de los datos esta bien"
                }, status=status.HTTP_200_OK)
                
                
        except Exception as e:
            return Response({
                "detail":f"El servidor se cayo lo sentimos: {str(e)}"
            },status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class MiBilleteraView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self,request):
        # 1. Buscamos la billetera del usuario que hace la consulta
        billetera = Wallet.objects.select_related('user').filter(user=request.user).first()
        # Seguridad: Si por algún motivo raro no tiene billetera, avisamos
        if not billetera:
            return Response({
                "detail":"El usuario no tiene una billetera asociada"
            }, status=status.HTTP_404_NOT_FOUND)
            
        # 2. Pasamos el objeto de la base de datos por el serializador
        serializer = WalletSerializer(billetera)
        
        # 3. Devolvemos la data limpia lista para el frontend
        return Response(serializer.data, status=status.HTTP_200_OK)