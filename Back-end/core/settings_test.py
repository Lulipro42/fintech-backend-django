# Primero definimos las variables que Django va a buscar sí o sí
import os
os.environ['DB_NAME'] = 'dummy'
os.environ['DB_USER'] = 'dummy'
os.environ['DB_PASSWORD'] = 'dummy'
os.environ['DB_HOST'] = 'dummy'
os.environ['DB_PORT'] = 'dummy'

# Ahora importamos todo lo demás
from .settings import *

# Y finalmente sobrescribimos la base de datos con SQLite
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}