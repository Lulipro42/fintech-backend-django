import random, uuid
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
# Create your models here.

class Wallet(models.Model):
    CURRENCY_CHOICES = [
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
    ]
    
    # 1. Relación 1 a 1 con el usuario. Cada usuario tiene una sola billetera.
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    
    # 2. El saldo. Un campo Decimal con un máximo de 12 dígitos, 2 decimales y que empiece en 0.00
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    
    # Tipo de moneda de la billetera. Por defecto arranca en Pesos Argentinos ('ARS')
    moneda = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='ARS')
    
    # 3. Fecha de creación de la billetera
    creado_en = models.DateTimeField(auto_now_add=True)
    
    # Cvu para poder poner esto en vez de un id
    cvu = models.CharField(unique=True, max_length=22, blank=True, null=True)
    
    # Alias para poder mejorar la interfaz del usuario en vez de poner id 
    alias = models.CharField(unique=True, max_length=50, blank=True, null=True )
    
    def save(self, *args, **kwargs):
        if not self.id:
            numeros = random.choices('0123456789', k=22)
            self.cvu = "".join(numeros)
        
            palabras_semilla = [
                "perro","gato","sol","roca","guitarra","viento","mar","nube","fuego","tierra","arbol","luna","cumbia",
            ]      
        
            alias_generado = None
            for intento in range(5):
                candidato = ".".join(random.sample(palabras_semilla, k=3))
                existe = Wallet.objects.filter(alias=candidato).exists()
                
                if not existe:
                    alias_generado = candidato
                    break
        
            if alias_generado is None:
                raise ValueError("No se pudo generar un alias unico, intente de nuevo")
        
            self.alias = alias_generado
        # 🔴 Se borra el super().save() de acá adentro
        # 🔴 Se borran también las líneas viejas de palabras_elegidas, ya no hacen falta
    
        super().save(*args, **kwargs)   # ✅ Este es el ÚNICO save(), al final, para ambos casos (creación y actualización)
    def __str__(self) -> str:
        return f"Billetera de {self.user.username} ({self.moneda})"
            

class Transtaction(models.Model):
    # 1. Billetera de origen (el que manda). Si se borra la billetera, no queremos borrar el historial, ponemos SET_NULL.
    # Como tenemos dos ForeignKey apuntando al mismo modelo (Wallet), Django te obliga a poner related_name distintos.
    wallet_origen = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, db_index=True,related_name='transferencia_enviadas')
    
    # 2. Billetera de destino (el que recibe). Completá la ForeignKey igual que la de arriba pero cambiá el related_name.
    walle_destino = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True,db_index=True, related_name='transferencia_recibidas')
    
    # 3. El monto transferido. Poné un DecimalField igual que el saldo de la billetera.
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    
    # 4. Fecha de la transacciónd
    fecha = models.DateTimeField(auto_now_add=True)    
    
    idempotency_key = models.UUIDField(unique=True, null=True, blank=True)
    
            
    def __str__(self) -> str:
        origen = self.wallet_origen.user.username if self.wallet_origen else "Deposito externo"
        destino = self.walle_destino.user.username if self.walle_destino else "Retiro Externo"
        return f"Transacción de ${self.monto} ({origen} -> {destino})"
    
    
    
class Profile(models.Model):
    # 1. Conexión 1 a 1 con el usuario nativo de Django. Si se borra el usuario, se borra el perfil.
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    
    # 2. El documento de identidad (DNI). Queremos que sea un texto de máximo 20 caracteres y que sea ÚNICO.
    dni = models.CharField(max_length=20, unique=True)
    
    # 3. El teléfono celular. Un CharField de máximo 20 caracteres.
    telefono = models.CharField(max_length=20)
    
    def __str__(self) -> str:
        return f"Perfil de {self.user.username} - DNI: {self.dni}"