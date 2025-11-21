# D:\GAT\core\backends.py (УЛУЧШЕННАЯ ВЕРСИЯ)

from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameBackend(BaseBackend):
    """
    Кастомный бэкенд аутентификации.
    Позволяет пользователям входить, используя их email ИЛИ username.
    
    Особенности:
    - Поддерживает аутентификацию по email или username
    - Case-insensitive сравнение (независимо от регистра)
    - Обрабатывает случаи с несколькими совпадениями
    - Совместим со стандартной системой аутентификации Django
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        
        # Если не предоставлены учетные данные, выходим
        if username is None or password is None:
            return None
        
        try:
            # Ищем пользователя по username или email (без учета регистра)
            users = UserModel.objects.filter(
                Q(username__iexact=username) | Q(email__iexact=username)
            ).distinct()
            
            # Если найдено несколько пользователей, берем первого активного
            user = None
            if users.exists():
                # Предпочитаем пользователя с точным совпадением username
                exact_username_match = users.filter(username__iexact=username).first()
                if exact_username_match:
                    user = exact_username_match
                else:
                    # Иначе берем первого подходящего
                    user = users.first()
            
            # Проверяем пароль и активность пользователя
            if user and user.check_password(password) and self.user_can_authenticate(user):
                return user
                
        except Exception as e:
            # Логирование ошибки (в продакшене можно добавить логи)
            # print(f"Authentication error: {e}")
            pass
            
        return None

    def user_can_authenticate(self, user):
        """
        Проверяет, может ли пользователь аутентифицироваться.
        Переопределяет стандартную проверку Django.
        """
        is_active = getattr(user, 'is_active', None)
        return is_active or is_active is None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            user = UserModel.objects.get(pk=user_id)
            return user if self.user_can_authenticate(user) else None
        except UserModel.DoesNotExist:
            return None