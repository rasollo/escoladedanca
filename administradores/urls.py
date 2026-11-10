from django.urls import path
from . import views

app_name = 'administradores'

urlpatterns = [
    path('', views.index, name='administradores'),
]