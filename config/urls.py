# D:\New_GAT\config\urls.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
]

# Этот блок будет работать только в режиме разработки (DEBUG=True)
if settings.DEBUG:
    # Оставляем только маршрут для медиа-файлов
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Строку для статики мы убрали, так как Django обрабатывает её автоматически
    # при DEBUG=True, если 'django.contrib.staticfiles' есть в INSTALLED_APPS.