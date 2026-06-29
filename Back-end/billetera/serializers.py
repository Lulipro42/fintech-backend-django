from rest_framework import serializers
from django.db.models import Q
from django.contrib.auth.models import User
from .models import Profile, Transtaction,Wallet
from decimal import Decimal

class UserSerializer(serializers.ModelSerializer): # Today create a new serializer for my new project
    
    class Meta: # and her create model and field for the project 
        model = User
        fields = ['username','email','id', 'password']
        
        extra_kwargs = {
            'password': {
                'write_only': True # Hace que la contrasena no se exponga al consultar los datos
            }
        }
    def create(self, validated_data):
        # create_user se encarga de encriptar la contraseña automáticamente en la DB
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
        
        
    def validate_dni(self,value): # and ther i approbade the sintaxys for the erorrs
        dni_limpio = (value or '').strip()
        
        # Validamos que solo contenga números y que tenga el largo mínimo de la sintaxis de un DNI
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
    # Campo temporal que no se guarda en la tabla de transacciones, sirve para que el usuario escriba el CVU o Alias
    destino = serializers.CharField(write_only=True)
    
    class Meta:
        model = Transtaction
        fields = ['monto', 'destino']
    
    def validate(self, data):
        # 1. Capturamos el texto (CVU o Alias) que mandó el usuario
        destino = data.get('destino')
        
        # 2. Buscamos en MySQL usando el operador OR ( | ) con Q
        billetera = Wallet.objects.filter(Q(cvu=destino) | Q(alias=destino)).first()
        
        # 3. Si no se encontró ninguna billetera con ese CVU/Alias, rebotamos
        if not billetera:
            raise serializers.ValidationError("La billetera de destino no existe.")
            
        # 4. Obtenemos la billetera del usuario logueado
        usuario = self.context['request'].user
        billetera_origen = Wallet.objects.filter(user=usuario).first()
        
        # 5. Evitamos que se transfiera a sí mismo (comparando los objetos)
        if billetera_origen == billetera:
            raise serializers.ValidationError("No podés transferirte a vos mismo.")
        
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
    # SlugRelatedField nos permite mostrar un atributo del objeto relacionado (el username del dueño) en lugar de su ID numérico
    wallet_origen = serializers.SlugRelatedField(read_only=True, slug_field='user__username')
    walle_destino = serializers.SlugRelatedField(read_only=True,slug_field='user__username')
    
    class Meta:
        model = Transtaction
        fields = ['id','monto','wallet_origen','walle_destino','fecha']
        
        

class WalletSerializer(serializers.ModelSerializer):
    # Esto es para que en vez de mostrar el ID del usuario, muestre su nombre (username)
    usuario = serializers.SlugRelatedField(read_only=True, slug_field='username', source='user')    
    
    class Meta:
        model = Wallet
        fields = ['usuario', 'saldo','cvu','alias','moneda']