from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from django.db import connection

from billetera.models import Wallet, Transaction


class TransferenciaConcurrenciaTest(TransactionTestCase):
    """
    Tests de concurrencia para transferencias entre wallets.
    Usa TransactionTestCase porque TestCase envuelve en savepoint
    que no son visibles para otros hilos.
    """

    def setUp(self):
        # Crear usuarios
        self.user_a = User.objects.create_user(username='user_a', password='test123')
        self.user_b = User.objects.create_user(username='user_b', password='test123')

        # Crear wallets con saldo inicial
        self.wallet_a = Wallet.objects.create(user=self.user_a, saldo=Decimal('1000.00'))
        self.wallet_b = Wallet.objects.create(user=self.user_b, saldo=Decimal('1000.00'))

    def _transferir(self, origen_id, destino_id, monto):
        """Helper que simula una transferencia llamando a la vista directamente."""
        from django.test import RequestFactory
        from rest_framework.test import force_authenticate
        from billetera.views import TransferenciaView

        factory = RequestFactory()

        # Obtener el destino (CVU o Alias) de la billetera destino
        wallet_destino = Wallet.objects.get(id=destino_id)
        destino_str = wallet_destino.alias  # Usamos alias como identificador

        data = {
            'destino': destino_str,  # ← CAMBIO: el serializer espera 'destino', no 'billetera_destino'
            'monto': str(monto),
        }

        # Determinar usuario origen
        if origen_id == self.wallet_a.id:
            user = self.user_a
        else:
            user = self.user_b

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

    def test_transferencias_cruzadas_sin_deadlock(self):
        """
        Smoke test de concurrencia para transferencias cruzadas.
    
        Verifica que el sistema no falle bajo carga concurrente (20 threads).
        La correctitud del bloqueo ordenado por ID se validó manualmente:
        - Sin select_for_update(): deadlocks observados en desarrollo
        - Con select_for_update(): sin deadlocks, saldo se conserva
        """ 
        monto = Decimal('10.00')
        num_transferencias = 10

        tareas = []

        # 10 transferencias A→B
        for _ in range(num_transferencias):
            tareas.append((self.wallet_a.id, self.wallet_b.id, monto))

        # 10 transferencias B→A
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

        # Cerrar conexiones de los hilos
        connection.close()

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

        # ASSERT 4: Algunas transferencias tuvieron éxito
        exitosos = [r for r in resultados if r['status_code'] == 200]
        self.assertGreater(len(exitosos), 0, "Ninguna transferencia tuvo éxito")

    def test_idempotencia_concurrente(self):
        """
        Dos threads intentan la misma transferencia con la misma idempotency_key.
        Solo una debe tener éxito, la otra debe recibir "ya procesada".
        """
        from uuid import uuid4

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

        connection.close()

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
        """Helper con idempotency_key."""
        from django.test import RequestFactory
        from rest_framework.test import force_authenticate
        from billetera.views import TransferenciaView

        factory = RequestFactory()

        # Obtener el destino (CVU o Alias)
        wallet_destino = Wallet.objects.get(id=destino_id)
        destino_str = wallet_destino.alias

        data = {
            'destino': destino_str,  # ← CAMBIO: el serializer espera 'destino'
            'monto': str(monto),
            'idempotency_key': idempotency_key,
        }

        if origen_id == self.wallet_a.id:
            user = self.user_a
        else:
            user = self.user_b

        request = factory.post('/api/transferir/', data, content_type='application/json')
        force_authenticate(request, user=user)

        view = TransferenciaView.as_view()
        response = view(request)

        return {
            'status_code': response.status_code,
            'data': response.data,
        }