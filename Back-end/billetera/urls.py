from django.urls import path
from .views import RegistroUsuarioView, SaldoWalletView, TransferenciaView, HistorialTransactionsView, DepostivoView,RetiroMoneyView, MiBilleteraView

urlpatterns = [
    # Definimos la ruta para el registro de usuarios
    path('registro/', RegistroUsuarioView.as_view(), name='registro_usuario'),

#----------------
# TRANSACCIONES URL
#-----------------
    path('saldo/', SaldoWalletView.as_view(), name='saldo'),
    path('transferir/', TransferenciaView.as_view(), name='transferir'), 
    path('historial/', HistorialTransactionsView.as_view(), name='historial_transaccion'),
    path('depositar/', DepostivoView.as_view(), name='deposito_de_fondos'),
    path('wallet/retiro/', RetiroMoneyView.as_view(), name='wallet_retiro'),
    path('mi_billetera/', MiBilleteraView.as_view(), name='mi_billetera'),

]