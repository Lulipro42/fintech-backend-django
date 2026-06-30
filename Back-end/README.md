# 💰 Billetera Virtual API - Django REST Framework
[![Python application](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml/badge.svg)](https://github.com/Lulipro42/fintech-backend-django/actions/workflows/test_and_build.yaml)

¡Bienvenido! Este proyecto es una API robusta para una billetera virtual que permite el registro de usuarios, perfiles, gestión de saldos y transferencias seguras en múltiples monedas (Pesos, Dólares y Euros), utilizando transacciones atómicas para asegurar la consistencia de los datos.

## 🚀 Características Clave

* **Multi-moneda:** Soporte nativo para cuentas en ARS, USD y EUR (las transferencias validan que coincida el tipo de moneda).
* **Seguridad Financiera:** Uso de `transaction.atomic()` para evitar inconsistencias en saldos durante transferencias o retiros.
* **Identificadores Únicos:** Generación automática de CVU de 22 dígitos y Alias aleatorios mediante palabras semilla al crear la cuenta.
* **Arquitectura Contenerizada:** Listo para producción y desarrollo local utilizando Docker y Docker Compose.

## 🛠️ Tecnologías Utilizadas

* **Backend:** Python 3.11 & Django 5.x
* **API Toolkit:** Django REST Framework (DRF)
* **Base de Datos:** MySQL
* **Entorno:** Docker & Docker Compose

## 📦 Instalación y Configuración con Docker

Para levantar este proyecto, necesitás tener instalado **Docker Desktop**.

1. **Clonar el repositorio:**
   ```bash
    git clone https://github.com/Lulipro42/fintech-backend-django.git