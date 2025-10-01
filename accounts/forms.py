# accounts/forms.py

from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm
from .models import UserProfile

# Общий CSS класс для полей ввода, который мы будем использовать везде
input_class = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'

class CustomUserCreationForm(forms.ModelForm):
    """
    Новая, упрощенная форма для создания пользователя.
    Удалено поле 'username' и стандартные подсказки для пароля.
    """
    email = forms.EmailField(
        required=True,
        label="Email (будет использоваться для входа)",
        widget=forms.EmailInput(attrs={'class': input_class})
    )
    first_name = forms.CharField(max_length=150, required=True, label="Имя", widget=forms.TextInput(attrs={'class': input_class}))
    last_name = forms.CharField(max_length=150, required=True, label="Фамилия", widget=forms.TextInput(attrs={'class': input_class}))
    
    # Поля для пароля, чтобы мы могли применить к ним стили
    password = forms.CharField(
        label="Пароль", 
        widget=forms.PasswordInput(attrs={'class': input_class})
    )
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name', 'password')

    def save(self, commit=True):
        user = super().save(commit=False)
        # Устанавливаем пароль правильным образом
        user.set_password(self.cleaned_data["password"])
        # Автоматически создаем username из email, так как это поле обязательно в Django
        user.username = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class UserProfileForm(forms.ModelForm):
    """
    Форма для редактирования профиля (роль и привязки).
    """
    class Meta:
        model = UserProfile
        fields = ('role', 'school', 'subject')
        widgets = {
            # Добавляем id для связи с Alpine.js
            'role': forms.Select(attrs={'class': input_class, 'x-model': 'role'}),
            'school': forms.Select(attrs={'class': input_class}),
            'subject': forms.Select(attrs={'class': input_class}),
        }
        labels = {
            'role': 'Роль пользователя',
            'school': 'Привязанная школа (для директора)',
            'subject': 'Предмет экспертизы (для эксперта)',
        }

class CustomUserEditForm(forms.ModelForm):
    """
    Форма для редактирования основных данных пользователя (без пароля).
    """
    class Meta:
        model = User
        fields = ('email', 'first_name', 'last_name')
        widgets = {
            'email': forms.EmailInput(attrs={'class': input_class}),
            'first_name': forms.TextInput(attrs={'class': input_class}),
            'last_name': forms.TextInput(attrs={'class': input_class}),
        }
        labels = {
            'email': 'Email',
            'first_name': 'Имя',
            'last_name': 'Фамилия',
        }