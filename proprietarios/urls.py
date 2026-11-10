from django.urls import path
from . import views

app_name = 'proprietarios'

urlpatterns = [
    path('', views.index, name='proprietarios'),
]