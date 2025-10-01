# D:\New_GAT\core\views\auth.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages

def login_view(request):
    """Обрабатывает вход пользователя в систему."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Неверный email или пароль.")
            return render(request, 'index.html', {'error': "Неверный email или пароль."})
    return render(request, 'index.html')

@login_required
def logout_view(request):
    """Выход пользователя из системы."""
    logout(request)
    messages.info(request, "Вы успешно вышли из системы.")
    return redirect('login')