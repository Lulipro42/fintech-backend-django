from .settings import *

# Sobrescribimos la base de datos para usar SQLite solo durante los tests
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}