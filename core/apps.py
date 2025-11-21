# D:\GAT\core\apps.py

from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    verbose_name = 'Центр управления GAT'
    
    def ready(self):
        """
        Метод ready выполняется при загрузке приложения.
        Здесь можно добавить сигналы или другие инициализации.
        """
        try:
            # Импортируем сигналы здесь, чтобы избежать circular imports
            from . import signals
        except ImportError:
            pass