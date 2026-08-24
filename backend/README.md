# 💰 Fintech Wallet — Billetera Virtual API

[![Python application](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml/badge.svg)](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Django](https://img.shields.io/badge/Django-5.x-092E20?logo=django)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker)

---

## 🎯 Qué resuelve

Backend de una billetera digital que permite a usuarios registrarse, mantener saldo en distintas monedas (ARS, USD, EUR), y transferir dinero entre cuentas de forma segura. Resuelve tres problemas típicos que rompen sistemas de pago mal diseñados:

- 🔒 Transferencias concurrentes que corrompen el saldo
- 🔁 Reintentos de red o dobles clics que duplican un movimiento de dinero
- 🧭 Falta de trazabilidad en errores de la API

---

## 🛠️ Stack técnico

| Capa | Tecnología |
|---|---|
| Lenguaje | Python 3.11 |
| Framework | Django 5.x + Django REST Framework |
| Base de datos | MySQL |
| Autenticación | SimpleJWT |
| Documentación | drf-spectacular (Swagger / Redoc) |
| Infraestructura | Docker / Docker Compose |

---

## 🧩 Decisiones técnicas destacadas

### 1. Bloqueo ordenado para evitar deadlocks
Una transferencia bloquea dos billeteras (origen y destino) con `select_for_update()`. Si dos transferencias cruzadas (A→B y B→A) se ejecutan al mismo tiempo y cada una bloquea las filas en un orden distinto, se genera un **deadlock**. Para evitarlo, las billeteras se bloquean siempre en el mismo orden (por `id` ascendente), sin importar cuál es origen y cuál destino en esa operación puntual.

### 2. Idempotencia en transferencias
El cliente puede enviar una `idempotency_key` (UUID) junto con la transferencia. Antes de procesarla, el sistema chequea si ya existe una transacción registrada con esa key — si existe, devuelve éxito **sin repetir el movimiento de dinero**. Esto protege contra dobles clics y reintentos automáticos de red.

### 3. Validación de formato vs. validación de negocio
Las validaciones que dependen solo del dato en sí (¿el monto es mayor a cero?, ¿el formato es correcto?) viven en los serializers. Las validaciones que dependen del estado actual de la base de datos (¿hay saldo suficiente?) se evalúan **dentro del bloque atómico, con los bloqueos ya aplicados** — así se garantiza que la decisión final se toma sobre el dato real y protegido, no sobre uno que pudo haber cambiado un instante antes.

---

## 💡 Lección aprendida

Al principio pensé que `select_for_update()` resolvía la concurrencia por sí solo. Recién al probar transferencias cruzadas (A→B y B→A al mismo tiempo) entendí que el mismo lock que evita el race condition puede generar un deadlock si no hay un orden fijo de bloqueo entre las dos filas. Ese fue el motivo real detrás del bloqueo ordenado por ID, no una decisión tomada de entrada.

---

## 📍 Estado actual

| | |
|---|---|
| **Local** | ✅ Corre vía Docker Compose |
| **CI** | ✅ GitHub Actions — tests automáticos en cada push |
| **Deploy** | ⏳ Pendiente — todavía no publicado en entorno accesible públicamente |

---

**Repo:** [github.com/Lulipro42/fintech-backend-django](https://github.com/Lulipro42/fintech-backend-django)