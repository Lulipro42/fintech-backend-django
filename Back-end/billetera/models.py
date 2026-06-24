from django.db import models
from django.contrib.auth.models import User
# Create your models here.

class Wallet(models.Model):
    # 1. Relación 1 a 1 con el usuario. Cada usuario tiene una sola billetera.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet')
    
    # 2. El saldo. Un campo Decimal con un máximo de 12 dígitos, 2 decimales y que empiece en 0.00
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    # 3. Fecha de creación de la billetera
    creado_en = models.DateTimeField(auto_now_add=True)
    

class Transtaction(models.Model):
    # 1. Billetera de origen (el que manda). Si se borra la billetera, no queremos borrar el historial, ponemos SET_NULL.
    # Como tenemos dos ForeignKey apuntando al mismo modelo (Wallet), Django te obliga a poner related_name distintos.
    wallet_origen = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, related_name='transferencia_enviadas')
    
    # 2. Billetera de destino (el que recibe). Completá la ForeignKey igual que la de arriba pero cambiá el related_name.
    walle_destino = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, related_name='transferencia_recibidas')
    
    # 3. El monto transferido. Poné un DecimalField igual que el saldo de la billetera.
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    
    # 4. Fecha de la transacciónd
    fecha = models.DateTimeField(auto_now_add=True)    
    def __str__(self) -> str:
        return f"Transaccion de ${self.monto} desde {self.wallet_origen} a {self.walle_destino}"
    
    
class Profile(models.Model):
    # 1. Conexión 1 a 1 con el usuario nativo de Django. Si se borra el usuario, se borra el perfil.
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='perfil')
    
    # 2. El documento de identidad (DNI). Queremos que sea un texto de máximo 20 caracteres y que sea ÚNICO.
    dni = models.CharField(max_length=20, unique=True)
    
    # 3. El teléfono celular. Un CharField de máximo 20 caracteres.
    telefono = models.CharField(max_length=20)
    
    def __str__(self) -> str:
        return f"Perfil de {self.user.username} - DNI: {self.dni}"