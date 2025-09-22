# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')), # Все запросы отправляем в core
]

# Этот блок будет работать только в режиме разработки (DEBUG=True)
if settings.DEBUG:
    # Маршрут для медиа-файлов (загруженных пользователями, как фото профиля)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)