from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import get_user_model

class EmailBackend(BaseBackend):
    """
    Кастомный бэкенд аутентификации.
    Позволяет пользователям входить, используя их email адрес.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()
        try:
            # Ищем пользователя по email, который пришел в поле 'username'
            user = UserModel.objects.filter(email=username).first()
        except UserModel.DoesNotExist:
            # Если пользователь не найден, аутентификация провалена
            return None
        
        # Если пользователь найден, проверяем его пароль
        if user.check_password(password):
            return user # Пароль верный, возвращаем пользователя
        return None

    def get_user(self, user_id):
        UserModel = get_user_model()
        try:
            return UserModel.objects.get(pk=user_id)
        except UserModel.DoesNotExist:
            return None