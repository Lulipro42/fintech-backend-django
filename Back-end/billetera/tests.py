from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from .models import Wallet, Transtaction

# Create your tests here.

class RegistroUsuarioTestCase(APITestCase):
    def setUp(self):
        # reverse() busca automáticamente la URL usando el 'name' que pusiste en urls.py
        # Cambiá 'registro' por el nombre real que le hayas puesto a tu ruta de registro.
        self.url_registro = reverse('registro_usuario')
        
        # Dejamos armado el diccionario con los datos listos para enviar
        self.datos_usuario = {
            "username": "usuario_test",
            "password": "PasswordSegura123",
            "email": "test@banco.com",
            "profile": {                         # 👈 Bloque anidado que extrae request.data.get('profile')
                "dni": "12345678",               # 👈 Pasa tu validación de .isdigit() y len >= 7
                "telefono": "1122334455"
            }
        }
    def test_registro_exitoso_crea_usuario_y_wallet(self,):
        # 1 y 2. Enviamos los datos mediante POST y guardamos la respuesta
        response = self.client.post(self.url_registro, data=self.datos_usuario, format='json')


        # 🌟 AGREGÁ ESTA LÍNEA TEMPORAL PARA ESPIAR EL ERROR:
        print("Detalle del error 400:", response.data)
        
        # 3. Verificamos que el status code sea 201 (CREATED)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        # 4. Chequeamos que el usuario se haya guardado en la base de datos
        usuario_existe = User.objects.filter(username="usuario_test").exists()
        
        self.assertTrue(usuario_existe)
        
        # 5. Chequeamos que la billetera (Wallet) se haya creado automáticamente para ese usuario
        billetera_existe = Wallet.objects.filter(user__username="usuario_test").exists()
        
        self.assertTrue(billetera_existe)




class TransferenciasTestCase(APITestCase):
    def setUp(self):
    
        # 1. Creamos al Usuario Origen (El que manda la plata) y su billetera con saldo inicial
        self.user_origen = User.objects.create_user(username="juan_origen", password='juan12345')
        self.wallet_origen = Wallet.objects.create(user=self.user_origen, saldo=1000.00) # Arranca en mil
    
        # 2. Creamos al Usuario Destino (El que recibe la plata) y su billetera vacía
        self.user_destino = User.objects.create_user(username="pedro_origen",password="pedro123")
        self.walle_destino = Wallet.objects.create(user=self.user_destino,saldo=0.00) # Y arranca en 0
        # 3. Buscamos la URL de la vista de transferencias.
        self.url_transferencia = reverse('transferir')
        # 4. 🌟 ¡CLAVE!: Autenticamos al cliente de pruebas como "juan_origen" 
        # para que request.user funcione correctamente en la vista.
        self.client.force_authenticate(user=self.user_origen)
        
        
    def test_transferencia_exitosa(self):
        """Prueba una transferencia exitosa entre dos cuentas usando el Alias"""
        # Traemos el CVU y Alias reales generados por el método save()
        self.wallet_origen.refresh_from_db()
        self.walle_destino.refresh_from_db()
        
        datos_deploy = {
            "monto": 400.00,
            "destino": self.walle_destino.alias  # 👈 Usamos la clave y el alias correcto
        }
        
        response = self.client.post(self.url_transferencia, data=datos_deploy, format='json')
        
        # A) Verificamos respuesta de la API
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # B) Refrescamos saldos
        self.wallet_origen.refresh_from_db()
        self.walle_destino.refresh_from_db()
        
        # C) Verificaciones de saldo ($1000 - $400 = $600 | $0 + $400 = $400)
        self.assertEqual(self.wallet_origen.saldo, 600.00)
        self.assertEqual(self.walle_destino.saldo, 400.00)
        
        
    def test_transferencia_saldo_insuficiente(self):
        """Prueba que el sistema rechace la transferencia si el usuario quiere mandar más de lo que tiene"""
        self.wallet_origen.refresh_from_db()
        self.walle_destino.refresh_from_db()
        
        datos_paylod = {
            "monto": 3000.00,
            "destino": self.walle_destino.alias  # 👈 Cambiado también acá
        }
        
        response = self.client.post(self.url_transferencia, data=datos_paylod, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Aseguramos que nadie perdió ni ganó plata
        self.wallet_origen.refresh_from_db()
        self.walle_destino.refresh_from_db()
        self.assertEqual(self.wallet_origen.saldo, 1000.00)
        self.assertEqual(self.walle_destino.saldo, 0.00)
    
    def test_transferencia_destino_no_existe(self):
        """Prueba que falle si el Alias de destino no existe en el sistema"""
        datos_falsos = {
            "monto": 100.00,
            "destino": "alias.falso.inexistente"
        }
        response = self.client.post(self.url_transferencia, data=datos_falsos, format='json')
        
        # Debe rebotar con un 400 Bad Request
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # El saldo de origen tiene que seguir intacto
        self.wallet_origen.refresh_from_db()
        self.assertEqual(self.wallet_origen.saldo, 1000.00)
        
    def test_transferencia_monto_negativo(self):
        """Prueba que el sistema rechace montos menores o iguales a cero"""
        datos_negativos = {
            "monto": -50.00,
            "destino": self.walle_destino.alias
        }
        response = self.client.post(self.url_transferencia, data=datos_negativos,format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)