# Arquitectura — Fintech Wallet

## Decisiones técnicas

### 1. PostgreSQL en vez de MySQL

Problema: Necesitaba una base de datos que garantice consistencia en transferencias concurrentes. Sin bloqueos de fila, dos transferencias simultáneas leen el mismo saldo, pasan la validación, y el resultado es saldo negativo.

Opciones consideradas: MySQL (InnoDB) y PostgreSQL. Ambos soportan transacciones ACID y bloqueos de fila.

Decisión: PostgreSQL. Elegí select_for_update() que en PostgreSQL usa row-level locks sin gap locks innecesarios (a diferencia de InnoDB en ciertos niveles de aislamiento). Además, PostgreSQL maneja mejor los deadlocks con detección automática y error 40P01.

Trade-off: PostgreSQL consume más recursos por conexión que MySQL. En un escenario de miles de conexiones baratas (ej: lecturas simples sin transacciones), MySQL con connection pooling agresivo podría ser más eficiente. Para una fintech donde cada operación es una transacción crítica, acepto ese costo.

### 2. Django en vez de FastAPI

Problema: Necesitaba iterar rápido en la lógica de negocio (creación de cuentas, flujos de transferencias) sin implementar desde cero autenticación, permisos, panel de administración y protecciones básicas de seguridad.

Opciones consideradas: FastAPI (asíncrono nativo, ligero, ideal para microservicios de alta concurrencia) y Django (monolítico, baterías incluidas).

Decisión: Django. Elegí un framework con ORM maduro que maneja transacciones atómicas con PostgreSQL, autenticación con permisos de grupo, panel de administración listo para usar, y protecciones incorporadas contra SQLi, CSRF y XSS sin configuración adicional.

Trade-off: Pierdo el rendimiento bruto de async nativo y la ligereza de FastAPI. Django consume más memoria, su soporte async es más reciente y menos maduro, y su arquitectura monolítica reduce la flexibilidad para patrones personalizados. En una fintech donde la consistencia de datos es prioridad sobre la latencia de milisegundos, acepto ese costo.

### 3. Pessimistic locking en vez de Optimistic locking
Problema: Necesitaba evitar race condition al actualizar saldos. Ejemplo: un usuario con $100 intenta dos transferencias de $80 casi simultáneas. El sistema debe procesar una, rechazar la otra por fondos insuficientes, y nunca permitir saldo negativo.

Opciones consideradas:
Optimistic locking: columna version en la fila. Leer saldo + versión, validar, actualizar solo si la versión no cambió. Si falla, retry.
Pessimistic locking: select_for_update(). Bloquear la fila antes de leer, validar y actualizar en una transacción atómica.

Decisión: select_for_update(). Bloquea la fila a nivel del motor de PostgreSQL (row-level lock). Otros procesos pueden leer el saldo (MVCC), pero no pueden adquirir otro lock ni modificar la fila hasta que la transacción actual haga commit o rollback. Esto garantiza que la validación de "saldo suficiente" se hace sobre el dato real, no sobre un valor stale.

Trade-off: Pierdo paralelismo en la misma fila. Si el proceso tarda (ej: llamada a pasarela de pagos externa), otras solicitudes sobre la misma cuenta quedan en cola esperando el lock. Esto aumenta la latencia percebida y consume conexiones de PostgreSQL. En una fintech, acepto ese costo porque la consistencia del saldo es prioridad sobre la latencia

## Deuda técnica conocida
- Tests de concurrencia son smoke tests, no demuestran race conditions forzadas
- Deploy pendiente para noviembre
- No implementé optimistic locking como alternativa validada

## Estado actual
- Local: Docker Compose
- CI: GitHub Actions
- Deploy: Pendiente