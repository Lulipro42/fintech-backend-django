from rest_framework import serializers
from django.db.models import Q
from django.contrib.auth.models import User
from .models import Profile, Transaction,Wallet
from decimal import Decimal, InvalidOperation

class UserSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['username','email','id', 'password']
        
        extra_kwargs = {
            'password': {
                'write_only': True 
            }
        }
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    

# ==========================================
# SERIALIZADOR DE PERFIL
# ==========================================
class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        """
    Maneja los datos complementarios del usuario como el DNI y el teléfono.
    """
        model = Profile
        fields = ['dni', 'telefono']
        
        
    def validate_dni(self,value):
        dni_limpio = (value or '').strip()
        
        if not dni_limpio.isdigit() or len(dni_limpio) < 7 :
            raise serializers.ValidationError("Tu dni da error ")
        
        return dni_limpio


# ==========================================
# SERIALIZADOR PARA EJECUTAR TRANSFERENCIAS
# ==========================================
class TransactionSerializer(serializers.ModelSerializer):
    """
    Controla la lógica de negocios cuando un usuario intenta realizar una transferencia.
    """
    destino = serializers.CharField(write_only=True)
    idempotency_key = serializers.UUIDField(required=False)
    
    class Meta:
        model = Transaction
        fields = ['monto', 'destino', 'idempotency_key']
    
    def validate(self, data):
        destino = data.get('destino')
           
        billetera = Wallet.objects.filter(Q(cvu=destino) | Q(alias=destino)).first()
        
        if not billetera:
            raise serializers.ValidationError("La billetera de destino no existe.")
            
        usuario = self.context['request'].user
        billetera_origen = Wallet.objects.filter(user=usuario).first()
        
        if billetera_origen is None:
            raise serializers.ValidationError("El usuario no posee una billetera activa")
        
        # 6. Control de saldo
        monto = data.get('monto')
        if monto <= 0:
            raise serializers.ValidationError("El monto de la transferencia debe ser positivo")
        
        if billetera_origen.saldo < monto:
            raise serializers.ValidationError("Saldo insuficiente.")
        # Guardamos la billetera de destino encontrada en el diccionario 'data' 
        # para que la Vista pueda usarla fácilmente después.
        data['billetera_destino'] = billetera
        
        return data
    
# ==========================================
# SERIALIZADOR PARA EL HISTORIAL DE TRANSACCIONES
# ==========================================
class TransactionHistorialSerializer(serializers.ModelSerializer):
    """
    Muestra los movimientos históricos en formato de texto limpio.
    """
    wallet_origen = serializers.SerializerMethodField()
    wallet_destino = serializers.SerializerMethodField()
    
    class Meta:
        model = Transaction
        fields = ['id','monto','wallet_origen','wallet_destino','fecha']
    
    def get_wallet_origen(self, obj):
        if obj.wallet_origen and obj.wallet_origen.user:
            return obj.wallet_origen.user.username
        return None
    def get_wallet_destino(self, obj):

        if obj.wallet_destino and obj.wallet_destino.user:
            return obj.wallet_destino.user.username
        return None
        

class WalletSerializer(serializers.ModelSerializer):
    usuario = serializers.SlugRelatedField(read_only=True, slug_field='username', source='user')    
    
    class Meta:
        model = Wallet
        fields = ['usuario', 'saldo','cvu','alias','moneda']
        


class DepositoSerializer(serializers.Serializer):
    monto = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    
    
    def validate_monto(self, value):
        # Aquí movemos toda la lógica de validación de negocio
        if value <= 0:
            raise serializers.ValidationError("El monto debe ser mayor a cero")
        return value

class RetiroSerializer(serializers.Serializer):
    
    monto = serializers.DecimalField(max_digits=15, decimal_places=2, required=True)
    
    def validate_monto(self, value):
        if value <=0:
            raise serializers.ValidationError("El monto debe ser mayor a cero.")
        return value


