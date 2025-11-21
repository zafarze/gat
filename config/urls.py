# D:\GAT\config\urls.py (ОБНОВЛЕННАЯ ВЕРСИЯ С КОММЕНТАРИЯМИ)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # =========================================================================
    # --- АДМИН-ПАНЕЛЬ ---
    # =========================================================================
    path('admin/', admin.site.urls),
    
    # =========================================================================
    # --- ОСНОВНОЕ ПРИЛОЖЕНИЕ (CORE) ---
    # Включает: аутентификацию, dashboard, управление, аналитику, Центр Вопросов
    # =========================================================================
    path('', include('core.urls')),
]

# =============================================================================
# --- РАЗДАЧА МЕДИА-ФАЙЛОВ В РЕЖИМЕ РАЗРАБОТКИ ---
# =============================================================================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Дополнительно: Добавить debug toolbar для разработки (опционально)
    # try:
    #     import debug_toolbar
    #     urlpatterns = [
    #         path('__debug__/', include(debug_toolbar.urls)),
    #     ] + urlpatterns
    # except ImportError:
    #     pass