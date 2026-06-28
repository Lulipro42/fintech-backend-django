# 1. Usamos una imagen oficial de Python ligera como base
FROM python:3.11-slim

# 2. Evita que Python escriba archivos .pyc en el contenedor
ENV PYTHONDONTWRITEBYTECODE 1
# 3. Mantiene los logs limpios y en tiempo real sin búfer
ENV PYTHONUNBUFFERED 1

# 4. Creamos y nos paramos en la carpeta de trabajo dentro del contenedor
WORKDIR /app

# 5. Instalamos las dependencias del sistema necesarias para MySQL
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 6. Copiamos el archivo de requerimientos primero (para aprovechar el cache de Docker)
COPY requirements.txt /app/

# 7. Instalamos todas las librerías de Python
RUN pip install --no-cache-dir -r requirements.txt

# 8. Copiamos todo el resto del código de nuestro proyecto a la carpeta /app
COPY . /app/