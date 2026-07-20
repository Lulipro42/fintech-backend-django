from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib.auth.models import User
from .models import Wallet, Transtaction
import uuid

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
        

class IdempotenciaTestCase(APITestCase): # Bueno aca creo la clase
    def setUp(self): # Aca defino el def
        self.user_origen = User.objects.create_user(username="ana_origen", password="ana2132") # Aca creo el usuario en el cual el test, tiene que utilizar
        self.wallet_origen = Wallet.objects.create(user=self.user_origen, saldo=1000.00) # Aca defino el saldo de ese usuario creado
        
        
        self.user_destino = User.objects.create_user(username="luis_destino", password="luis1234") # bueno aca lo mismo solo que este va a ser el destinatario
        self.wallet_destino = Wallet.objects.create(user=self.user_destino, saldo=0.00) # lo mismo solo que este arranca con 0
        
        self.url_transferencia = reverse('transferir') # Aca defino la accion que va a tomar el test, y lo que hce es una transferencia
        self.client.force_authenticate(user=self.user_origen) # Aca defino que usuario agarra para la transferendia 
        
    def test_transferencia_duplicada_con_la_misma_key_no_descuenta_dos_veces(self):
        """Si se manda la misma transferencia dos veces con la misma idempotency_key, el saldo no debe descontarse dos vec
        es"""
        # 1. Generá una key fija para usar en ambos requests
        key = str(uuid.uuid4())
        # Aca genero una key que yo quiera 
        self.wallet_origen.refresh_from_db()
        self.wallet_destino.refresh_from_db()
        
        datos = {
            "monto": 300.00,
            "destino": self.wallet_destino.alias,
            "idempotency_key": key,
        } # Aca creo una lista quje es del user
        
        response_1 = self.client.post(self.url_transferencia, data=datos, format='json') 
        self.assertEqual(response_1.status_code, status.HTTP_200_OK)
        # Aca pongo eso proque si da bien dtiene que dar ok
        response_2 = self.client.post(self.url_transferencia, data=datos,format='json')
        self.assertEqual(response_2.status_code, status.HTTP_200_OK) # Aca lo puse basandome en otro codigo que tengo y ademas pienso que esta bien debido a que si las dos se chocan pueda dar error, perdon si esta mal explicado 
        
        self.wallet_origen.refresh_from_db()
        self.wallet_destino.refresh_from_db()
        
        self.assertEqual(self.wallet_origen.saldo,700.00) # Y aca lo mismo basandome en los demas codigos, y ademas tambien, te soy sincero es que no comprendo del todo bien como se hace que descveunte esos 300  
        self.assertEqual(self.wallet_destino.saldo, 300.00)  # y bueno aca esta lo recibido 
    
class DepositoTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="benja_prueba", password="benja123") # Bueno aca cree un usuraio para poder testear
        self.wallet = Wallet.objects.create(user=self.user, saldo=100.00) #aca lo que hice es crear la biletera del usuario para poder transferirr 
        
        self.url_deposito = reverse('deposito_de_fondos') # Aca hice la accion que iba a ser el usuario 
        
        self.client.force_authenticate(user=self.user) # Esto es para qeu el usuario sea identificado por asi decirlo 
        
    def test_deposito_exitoso_aumenta_saldo(self): # Aca cree el def 
        """Prueba que un depósito válido aumente el saldo correctamente"""
        datos = { # Aca cree la lista de datos que tenai que transferir
            "monto":50.00
        }
        response = self.client.post(self.url_deposito,data=datos,format='json') # Bueno aca cree la accion y en que formato 
        
        self.assertEqual(response.status_code, status.HTTP_200_OK) # Bueno aca si me da bien tien que dar 200 0K
        
        self.wallet.refresh_from_db() # Bueno aca refresca la db 
        self.assertEqual(self.wallet.saldo, 150) # y aca el resultado 
        
    def test_deposito_monto_negativo_falla(self):
        """Prueba que el sistema rechace un depósito con monto negativo"""
        datos = {
            "monto": -70.00
        } # Aca le puise ese monto
        
        response = self.client.post(self.url_deposito, data=datos, format='json') # Bueno aca configure a donde se iba a enviar esos datos 
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Aca defini qeu error iba dar 
        self.wallet.refresh_from_db() # Bueno aca puse eel refresh 
        self.assertEqual(self.wallet.saldo, 100.00) 
        

class RetiroTestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="benja_test", password="benja12345")
        self.wallet = Wallet.objects.create(user=self.user, saldo=100.00)
        
        self.url_retiro = reverse('wallet_retiro')
        self.client.force_authenticate(user=self.user)
        
        
    def test_retiro_exitoso_disminuye_saldo(self):
        """Prueba que un retiro válido disminuya el saldo correctamente"""
        datos = {
            "monto": 40.00
        }
        
        response = self.client.post(self.url_retiro, data=datos, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.wallet.refresh_from_db()
        
        self.assertEqual(self.wallet.saldo, 60.00)

    def test_retiro_monto_negativo_falla(self):
        """Prueba que el sistema rechace un retiro con monto negativo"""
        datos = {
            "monto": -40.00
        }
        response = self.client.post(self.url_retiro, data=datos, format='json') 
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.saldo, 100) # Aca queda en 100, porque como me dijiste antes y me acorde, al ser negativo el saldo ni se gasta en revisar si puede pasar, si no directamente lo niega ya que es negativo 
        
    def test_retiro_fondos_insuficientes_falla(self):
        """Prueba que el sistema rechace un retiro mayor al saldo disponible"""
        datos = {
            "monto": 200.00
        }
        response = self.client.post(self.url_retiro, data=datos, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.saldo, 100) # Y bueno aca algo parecido solo qeu el monto al ser mayor al saldo que tiene el cliente, tampco se completa la transferencia