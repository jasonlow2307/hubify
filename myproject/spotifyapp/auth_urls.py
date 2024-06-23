from django.urls import path, include
from django.contrib import admin
from . import views

urlpatterns = [
    path('login', views.login, name='login'),
    path('login_form', views.login_form, name='login_form'),
    path('callback', views.callback, name='callback'),
]
