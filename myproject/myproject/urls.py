from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('spotifyapp.urls')),
    path('auth/', include('spotifyapp.auth_urls')),  # Separate authentication-related URLs
]
