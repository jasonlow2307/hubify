from django.urls import path, include
from django.contrib import admin
from . import views

urlpatterns = [
    path('', views.login, name='login'),
    path('top_songs_query', views.topSongsQuery, name='top_songs_query'),
    path('get_top_songs', views.get_top_songs, name='get_top_songs'),
    path('index', views.index, name='index'),
    path('login_form', views.login_form, name='login_form'),
    path('auth/callback', views.callback, name='callback'),
    path('spotimatch', views.spotimatch, name='spotimatch'),
    path('gotify', views.gotify, name='gotify'),
    path('waiting_list', views.waiting_list, name='waiting_list'),
]

