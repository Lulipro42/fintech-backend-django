# 💰 Billetera Virtual API - Django REST Framework
[![Python application](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml/badge.svg)](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml)

¡Bienvenido! Este proyecto es una API robusta para una billetera virtual que permite el registro de usuarios, perfiles, gestión de saldos y transferencias seguras en múltiples monedas (Pesos, Dólares y Euros), utilizando transacciones atómicas para asegurar la consistencia de los datos.

## 🚀 Características Clave

* **Multi-moneda:** Soporte nativo para cuentas en ARS, USD y EUR (las transferencias validan que coincida el tipo de moneda).
* **Seguridad Financiera:** Uso de `transaction.atomic()` para evitar inconsistencias en saldos durante transferencias o retiros.
* **Identificadores Únicos:** Generación automática de CVU de 22 dígitos y Alias aleatorios mediante palabras semilla al crear la cuenta.
* **Arquitectura Contenerizada:** Listo para producción y desarrollo local utilizando Docker y Docker Compose.
* **Concurrencia segura:** Bloqueo ordenado de billeteras (`select_for_update`) en transferencias simultáneas, para prevenir deadlocks y condiciones de carrera.
* **Idempotencia:** Las transferencias aceptan una `idempotency_key` para que un reintento de red o un doble clic no descuente el saldo dos veces.
* **Manejo de errores centralizado:** Exception handler propio de DRF, con formato de respuesta uniforme para toda la API.
* **Control de tráfico:** Rate limiting en endpoints críticos para prevenir abuso.
* **Paginación:** Historial de transacciones paginado para soportar cuentas con alto volumen de movimientos.
* **Autenticación robusta:** JWT (SimpleJWT) con soporte de refresh token.
* **Documentación interactiva:** Swagger / Redoc generados automáticamente con drf-spectacular.
* **Testing:** Cobertura de tests automatizados para los flujos críticos (registro, transferencias, depósitos, retiros, idempotencia).

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3.11 & Django 5.x
* **API Toolkit:** Django REST Framework (DRF)
* **Base de Datos:** MySQL
* **Entorno:** Docker & Docker Compose
* **Documentación:** drf-spectacular (Swagger / Redoc)

## 📦 Instalación y Configuración con Docker

Para levantar este proyecto, necesitás tener instalado **Docker Desktop**.

1. **Clonar el repositorio:**
   ```bash
   git clone https://github.com/Lulipro42/fintech-backend-django.git
   cd fintech-backend-django
   ```

2. **Levantar el ecosistema:**
   ```bash
   docker-compose up --build
   ```

3. **Aplicar migraciones** (si no se aplican solas al levantar):
   ```bash
   docker-compose exec web python manage.py migrate
   ```

4. **Documentación interactiva:**

   Accedé a `http://localhost:8000/api/docs/` para probar los endpoints desde Swagger, o a `http://localhost:8000/api/redoc/` para la versión de solo lectura.

## 🧪 Testing

Ejecutá el siguiente comando para correr toda la suite de tests:

```bash
docker-compose exec web python manage.py test
```

## 🔧 Decisiones técnicas destacadas

### Bloqueo ordenado para evitar deadlocks

Cuando una transferencia bloquea dos billeteras (origen y destino) con `select_for_update()`, el orden en que se toman esos bloqueos importa: si dos transferencias simultáneas se bloquean mutuamente esperando la fila que tiene la otra, ocurre un deadlock. Para evitarlo, las billeteras se bloquean siempre en el mismo orden (por `id` ascendente), sin importar cuál es origen y cuál destino en esa operación puntual.

### Idempotencia en transferencias

El cliente puede enviar una `idempotency_key` (UUID) junto con la transferencia. Antes de procesarla, el sistema chequea si ya existe una transacción registrada con esa key — si existe, devuelve éxito sin repetir el movimiento de dinero. Esto protege contra dobles clics y reintentos automáticos de red, un problema real en cualquier sistema financiero.

### Validación de formato vs. validación de negocio

Las validaciones que dependen solo del dato en sí (¿el monto es mayor a cero?, ¿el formato es correcto?) viven en los serializers. Las validaciones que dependen del estado actual de la base de datos (¿hay saldo suficiente en este momento?) viven en la vista, evaluadas dentro del bloque con los bloqueos ya aplicados — así se garantiza que la decisión final se toma sobre el dato real y protegido, no sobre uno que pudo haber cambiado un instante antes.

### Manejo de errores centralizado

Un `exception_handler` propio, registrado globalmente en DRF, unifica el formato de todas las respuestas de error de la API y evita repetir el mismo bloque `try/except` en cada vista.

## 💡 Lecciones Aprendidas

* **Concurrencia:** Cómo dos operaciones simultáneas sobre el mismo dato pueden generar inconsistencias si no se controla el orden de los bloqueos.
* **Idempotencia:** Por qué un sistema que mueve dinero necesita ser seguro ante reintentos, no solo funcionar en el camino feliz.
* **Separación de responsabilidades:** Dónde termina la validación de un dato y dónde empieza una regla de negocio.
* **Testing real:** La diferencia entre un test que pasa por casualidad y uno que realmente prueba el comportamiento bajo condiciones límite (saldo insuficiente, duplicados, datos inválidos).

---

Desarrollado como proyecto de práctica en arquitectura backend orientada a sistemas financieros.