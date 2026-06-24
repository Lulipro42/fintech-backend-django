from django.contrib import admin
from .models import Wallet, Transtaction # From here impor my models created
# Register your models here.
admin.site.register(Wallet)
admin.site.register(Transtaction)