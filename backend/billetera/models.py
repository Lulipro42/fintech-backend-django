import random, uuid
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal

class Wallet(models.Model):
    CURRENCY_CHOICES = [
        ('ARS', 'Pesos Argentinos'),
        ('USD', 'Dólares'),
        ('EUR', 'Euros'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    moneda = models.CharField(max_length=3, choices=CURRENCY_CHOICES, default='ARS')
    
    creado_en = models.DateTimeField(auto_now_add=True)
    
    cvu = models.CharField(unique=True, max_length=22, blank=True, null=True)

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
    
        super().save(*args, **kwargs)   
    def __str__(self) -> str:
        return f"Billetera de {self.user.username} ({self.moneda})"
            

class Transaction(models.Model):
    
    wallet_origen = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, db_index=True, related_name='transferencia_enviadas')

    wallet_destino = models.ForeignKey(Wallet, on_delete=models.SET_NULL, null=True, db_index=True, related_name='transferencia_recibidas')
    
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    
    fecha = models.DateTimeField(auto_now_add=True)    

    idempotency_key = models.UUIDField(null=True, blank=True)
    
    def __str__(self) -> str:
        origen = self.wallet_origen.user.username if self.wallet_origen else "Deposito externo"
        destino = self.wallet_destino.user.username if self.wallet_destino else "Retiro Externo"
        return f"Transacción de ${self.monto} ({origen} -> {destino})"
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['wallet_origen','idempotency_key'],
                name='unique_user_idempotency_key',
                
                condition=models.Q(idempotency_key__isnull=False) 
            )
        ]

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')

    dni = models.CharField(max_length=20, unique=True)

    telefono = models.CharField(max_length=20)

    def __str__(self) -> str:
        return f"Perfil de {self.user.username} - DNI: {self.dni}"