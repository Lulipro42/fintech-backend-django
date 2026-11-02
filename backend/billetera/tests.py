from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.db import connections
from django.test import RequestFactory,override_settings
from rest_framework.test import force_authenticate
from billetera.views import TransferenciaView, DepositoView
from billetera.models import Wallet, Transaction

from uuid import uuid4
@override_settings(
    REST_FRAMEWORK={
        'DEFAULT_THROTTLE_CLASSES': [],
        'DEFAULT_THROTTLE_RATES': {},
    }
)
class TransferenciaConcurrenciaTest(TransactionTestCase):

    def setUp(self):
        # Crear usuarios
        self.user_a = User.objects.create_user(username='user_a', password='test123')
        self.user_b = User.objects.create_user(username='user_b', password='test123')

        # Crear wallets con saldo inicial
        self.wallet_a = Wallet.objects.create(user=self.user_a, saldo=Decimal('1000.00'))
        self.wallet_b = Wallet.objects.create(user=self.user_b, saldo=Decimal('1000.00'))

    def _transferir(self, origen_id, destino_id, monto):
        """Helper que simula una transferencia llamando a la vista directamente."""

        try:
            factory = RequestFactory()
            wallet_destino = Wallet.objects.get(id=destino_id)
            destino_str = wallet_destino.alias

            data = {
                'destino': destino_str,
                'monto': str(monto),
            }

            user = Wallet.objects.get(id=origen_id).user

            request = factory.post('/api/transferir/', data, content_type='application/json')
            force_authenticate(request, user=user)

            view = TransferenciaView.as_view()
            response = view(request)

            return {
                'status_code': response.status_code,
                'data': response.data,
                'origen': origen_id,
                'destino': destino_id,
                'monto': monto,
            }
        finally:
            connections.close_all()

    def test_transferencias_cruzadas_sin_deadlock(self):
        monto = Decimal('10.00')
        num_transferencias = 10

        tareas = []

        for _ in range(num_transferencias):
            tareas.append((self.wallet_a.id, self.wallet_b.id, monto))

        for _ in range(num_transferencias):
            tareas.append((self.wallet_b.id, self.wallet_a.id, monto))

        resultados = []
        errores = []

        with ThreadPoolExecutor(max_workers=20) as executor:
            futuros = {
                executor.submit(self._transferir, origen, destino, m): (origen, destino, m)
                for origen, destino, m in tareas
            }

            for futuro in as_completed(futuros):
                try:
                    resultado = futuro.result(timeout=30)
                    resultados.append(resultado)
                except Exception as e:
                    errores.append(str(e))

        # Refrescar wallets desde DB
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        # Debug: ver qué error devuelven las respuestas 400
        fallidos = [r for r in resultados if r['status_code'] != 200]
        for r in fallidos[:3]:
            print(f"ERROR {r['status_code']}: {r['data']}")

        # ASSERT 1: No hay errores de deadlock
        self.assertEqual(len(errores), 0, f"Errores encontrados: {errores}")

        # ASSERT 2: Ningún saldo es negativo
        self.assertGreaterEqual(self.wallet_a.saldo, Decimal('0'))
        self.assertGreaterEqual(self.wallet_b.saldo, Decimal('0'))

        # ASSERT 3: Saldo total se conserva (1000 + 1000 = 2000)
        saldo_total = self.wallet_a.saldo + self.wallet_b.saldo
        self.assertEqual(saldo_total, Decimal('2000.00'))


        exitosos = [r for r in resultados if r['status_code'] == 200]
        self.assertEqual(len(exitosos), 20, f"Se esperaban 20 éxitos, pero hubo {len(exitosos)}")


    def test_idempotencia_concurrente(self):
        idempotency_key = str(uuid4())
        monto = Decimal('10.00')

        tareas = [
            (self.wallet_a.id, self.wallet_b.id, monto, idempotency_key),
            (self.wallet_a.id, self.wallet_b.id, monto, idempotency_key),
        ]

        resultados = []

        with ThreadPoolExecutor(max_workers=2) as executor:
            futuros = [
                executor.submit(self._transferir_con_idempotencia, origen, destino, m, key)
                for origen, destino, m, key in tareas
            ]

            for futuro in as_completed(futuros):
                resultados.append(futuro.result(timeout=30))


        # Refrescar
        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        # Una debe ser 200 (éxito), otra debe ser 200 (ya procesada)
        status_codes = [r['status_code'] for r in resultados]
        self.assertIn(200, status_codes)

        # El saldo debe haberse debitado solo una vez
        self.assertEqual(self.wallet_a.saldo, Decimal('990.00'))
        self.assertEqual(self.wallet_b.saldo, Decimal('1010.00'))

        # Debe haber exactamente 1 transacción con esa key
        count = Transaction.objects.filter(idempotency_key=idempotency_key).count()
        self.assertEqual(count, 1)

    def _transferir_con_idempotencia(self, origen_id, destino_id, monto, idempotency_key):
        try:
            factory = RequestFactory()
            wallet_destino = Wallet.objects.get(id=destino_id)
            destino_str = wallet_destino.alias

            data = {
                'destino': destino_str,
                'monto': str(monto),
                'idempotency_key': idempotency_key,
            }

            user = Wallet.objects.get(id=origen_id).user

            request = factory.post('/api/transferir/', data, content_type='application/json')
            force_authenticate(request, user=user)

            view = TransferenciaView.as_view()
            response = view(request)

            return {
                'status_code': response.status_code,
                'data': response.data,
            }
        finally:
            connections.close_all()
        
    def test_fondos_insuficientes(self):
        monto = Decimal('9999.00')  # wallet_a tiene 1000.00

        resultado = self._transferir(self.wallet_a.id, self.wallet_b.id, monto)

        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        self.assertEqual(resultado['status_code'], 400)
        self.assertEqual(self.wallet_a.saldo, Decimal('1000.00'))
        self.assertEqual(self.wallet_b.saldo, Decimal('1000.00'))
        self.assertEqual(Transaction.objects.count(), 0)

    def test_usuario_sin_billetera(self):
        user_sin_wallet = User.objects.create_user(username='user_c', password='test123')

        factory = RequestFactory()
        data = {
            'destino': self.wallet_b.alias,
            'monto': '10.00',
        }
        request = factory.post('/api/transferir/', data, content_type='application/json')
        force_authenticate(request, user=user_sin_wallet)

        view = TransferenciaView.as_view()
        response = view(request)

        self.assertEqual(response.status_code, 404)
        self.assertEqual(Transaction.objects.count(), 0)

    def test_reintento_tras_fondos_insuficientes_no_queda_bloqueado(self):
        idempotency_key = str(uuid4())

        # Primer intento: monto excesivo, debe fallar
        resultado_1 = self._transferir_con_idempotencia(
            self.wallet_a.id, self.wallet_b.id, Decimal('9999.00'), idempotency_key
        )
        self.assertEqual(resultado_1['status_code'], 400)
        self.assertEqual(Transaction.objects.filter(idempotency_key=idempotency_key).count(), 0)

        # Segundo intento: misma key, monto válido, debe procesarse de verdad
        resultado_2 = self._transferir_con_idempotencia(
            self.wallet_a.id, self.wallet_b.id, Decimal('10.00'), idempotency_key
        )
        self.assertEqual(resultado_2['status_code'], 200)

        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()

        self.assertEqual(self.wallet_a.saldo, Decimal('990.00'))
        self.assertEqual(self.wallet_b.saldo, Decimal('1010.00'))
        self.assertEqual(Transaction.objects.filter(idempotency_key=idempotency_key).count(), 1)

    def test_no_permite_saldo_negativo_bajo_concurrencia(self):
        wallet_origen = Wallet.objects.create(
            user=User.objects.create_user(username='user_saldo_limitado', password='test123'),
            saldo=Decimal('100.00')
        )
        monto = Decimal('10.00')
        num_intentos = 20 

        resultados = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futuros = [
                executor.submit(self._transferir, wallet_origen.id, self.wallet_b.id, monto)
                for _ in range(num_intentos)
            ]
            for futuro in as_completed(futuros):
                resultados.append(futuro.result(timeout=30))

        wallet_origen.refresh_from_db()

        exitosos = [r for r in resultados if r['status_code'] == 200]
        fallidos = [r for r in resultados if r['status_code'] != 200]

        # Debe haber exactamente 10 éxitos (100 / 10) y 10 fallos por fondos insuficientes
        self.assertEqual(len(exitosos), 10, f"Se esperaban 10 éxitos, hubo {len(exitosos)}")
        self.assertEqual(len(fallidos), 10, f"Se esperaban 10 fallos 400, hubo {len(resultados) - len(exitosos)}")

        for fallo in fallidos:
            mensaje_error = str(fallo['data'])
            self.assertIn("Fondos insuficientes", mensaje_error)
            
        # El saldo nunca debe quedar negativo
        self.assertEqual(wallet_origen.saldo, Decimal('0.00'))
        self.assertGreaterEqual(wallet_origen.saldo, Decimal('0.00'))

    def test_transferencias_concurrentes_al_mismo_destino_no_pierden_updates(self):
        """
        Verifica que múltiples transferencias concurrentes hacia un mismo destino 
        utilizando select_for_update() no sufran pérdida de actualizaciones (lost updates).
        """
        monto = Decimal('10.00')
        num_origenes = 15

        wallets_origen = []
        for i in range(num_origenes):
            user = User.objects.create_user(username=f'user_origen_{i}', password='test123')
            wallet = Wallet.objects.create(user=user, saldo=Decimal('100.00'))
            wallets_origen.append(wallet)

        with ThreadPoolExecutor(max_workers=num_origenes) as executor:
            futuros = [
                executor.submit(self._transferir, w.id, self.wallet_b.id, monto)
                for w in wallets_origen
            ]
            resultados = [f.result(timeout=30) for f in as_completed(futuros)]


        self.wallet_b.refresh_from_db()

        exitosos = [r for r in resultados if r['status_code'] == 200]
        self.assertEqual(len(exitosos), num_origenes)

        # Saldo esperado: 1000 inicial + (10 * 15 transferencias) = 1150
        esperado = Decimal('1000.00') + (monto * num_origenes)
        self.assertEqual(self.wallet_b.saldo, esperado)

    def test_monto_invalido_es_rechazado(self):
        for monto_invalido in [Decimal('0.00'), Decimal('-10.00')]:
            resultado = self._transferir(self.wallet_a.id, self.wallet_b.id, monto_invalido)
            self.assertEqual(resultado['status_code'], 400)

        self.wallet_a.refresh_from_db()
        self.wallet_b.refresh_from_db()
        self.assertEqual(self.wallet_a.saldo, Decimal('1000.00'))
        self.assertEqual(self.wallet_b.saldo, Decimal('1000.00'))

    def test_transaccion_registra_datos_correctos(self):
        monto = Decimal('50.00')
        resultado = self._transferir(self.wallet_a.id, self.wallet_b.id, monto)

        self.assertEqual(resultado['status_code'], 200)

        tx = Transaction.objects.get(wallet_origen=self.wallet_a, wallet_destino=self.wallet_b)
        self.assertEqual(tx.monto, monto)
        self.assertEqual(tx.wallet_origen_id, self.wallet_a.id)
        self.assertEqual(tx.wallet_destino_id, self.wallet_b.id)

    def test_sin_idempotency_key_permite_transferencias_duplicadas(self):
        monto = Decimal('10.00')

        r1 = self._transferir(self.wallet_a.id, self.wallet_b.id, monto)
        r2 = self._transferir(self.wallet_a.id, self.wallet_b.id, monto)

        self.assertEqual(r1['status_code'], 200)
        self.assertEqual(r2['status_code'], 200)

        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.saldo, Decimal('980.00'))  # 1000 - 10 - 10
        self.assertEqual(Transaction.objects.filter(idempotency_key__isnull=True).count(), 2)


class DepositoTest(TransactionTestCase):
    def setUp(self) -> None:
        self.user_a = User.objects.create_user(username='user_a', password='test_16')
        self.user_b = User.objects.create_user(username='user_b', password='test_16')
        
        self.wallet_a = Wallet.objects.create(user=self.user_a, saldo=Decimal('1000.00'))
        self.wallet_b = Wallet.objects.create(user=self.user_b, saldo=Decimal('1000.00'))
        
    def _depositar(self, user, monto): # 👈 1. Agregamos los parámetros user y monto aquí
        try:
            factory = RequestFactory()
            
            data = {
                'monto': str(monto)
            }
        
            request = factory.post('/api/depositar/', data, content_type='application/json')
            force_authenticate(request, user=user)
            
            view = DepositoView.as_view()
            response = view(request)
            
            return {
                'status_code': response.status_code,
                'data': response.data,
            }
        finally:
            connections.close_all()

    def test_deposito_exitoso(self):
        monto_a_depositar = Decimal('500.00')
        
        resultado = self._depositar(self.user_a, monto_a_depositar)
        
        self.assertEqual(resultado['status_code'], 200)
        
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.saldo, Decimal('1500.00'))

    def test_deposito_monto_invalido(self):
        monto_a_depositar = Decimal('-100.00')
        
        resultado = self._depositar(self.user_a, monto_a_depositar)
        
        # Dependiendo de cómo valide tu serializer, un monto inválido suele dar 400 (Bad Request)
        # Si tu API devuelve 400, ajústalo aquí:
        self.assertEqual(resultado['status_code'], 400) 
        
        self.wallet_a.refresh_from_db()
        self.assertEqual(self.wallet_a.saldo, Decimal('1000.00')) # 👈 Corregido a 2 decimales exactos