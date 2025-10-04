# D:\New_GAT\core\views\profile.py (ФИНАЛЬНАЯ ВЕРСИЯ С УЛУЧШЕНИЕМ БЕЗОПАСНОСТИ)

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import DeleteView
from django.contrib.auth.models import User

from accounts.models import UserProfile
from accounts.forms import (
    CustomUserCreationForm, UserProfileForm, CustomUserEditForm
)
from ..forms import ProfileUpdateForm, CustomPasswordChangeForm, EmailChangeForm


@login_required
def profile_view(request):
    # Эта функция для личного профиля, она в порядке и не требует изменений
    user = request.user
    # ... (весь код profile_view остается без изменений)
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile, initial={'first_name': user.first_name, 'last_name': user.last_name})
            if profile_form.is_valid():
                user.first_name = profile_form.cleaned_data['first_name']
                user.last_name = profile_form.cleaned_data['last_name']
                user.save()
                # Сохраняем только поле 'photo' из формы профиля
                profile.photo = profile_form.cleaned_data['photo']
                profile.save()
                messages.success(request, 'Ваши данные успешно обновлены.')
                return redirect('profile')

        elif action == 'change_password':
            password_form = CustomPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Ваш пароль успешно изменен.')
                return redirect('profile')

        elif action == 'change_email':
            email_form = EmailChangeForm(request.POST, instance=user)
            if email_form.is_valid():
                email_form.save()
                user.username = user.email # Синхронизируем username с email
                user.save()
                messages.success(request, 'Ваш email успешно изменен.')
                return redirect('profile')
    
    # Если GET-запрос или формы невалидны
    profile_form = ProfileUpdateForm(instance=profile, initial={'first_name': user.first_name, 'last_name': user.last_name})
    password_form = CustomPasswordChangeForm(user)
    email_form = EmailChangeForm(instance=user)

    context = {
        'title': 'Мой профиль',
        'profile_form': profile_form,
        'password_form': password_form,
        'email_form': email_form,
    }
    return render(request, 'accounts/profile.html', context) # Убедитесь, что путь к шаблону верный

@login_required
def user_list_view(request):
    # Эта функция уже была нами обновлена, она в порядке
    queryset = User.objects.all().select_related('profile').order_by('last_name', 'first_name')
    active_tab = request.GET.get('role', 'all')
    if active_tab == 'directors': queryset = queryset.filter(profile__role='SCHOOL_DIRECTOR')
    elif active_tab == 'experts': queryset = queryset.filter(profile__role='EXPERT')
    elif active_tab == 'admins': queryset = queryset.filter(is_superuser=True)
    context = {'title': 'Управление пользователями', 'users': queryset, 'active_tab': active_tab}
    return render(request, 'accounts/user_list.html', context)

@login_required
def user_create_view(request):
    # --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ ---
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для создания пользователей.")
        return redirect('user_list')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---

    if request.method == 'POST':
        user_form = CustomUserCreationForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            profile = profile_form.save(commit=False)
            profile.user = user
            profile.save()
            messages.success(request, f'Пользователь {user.username} успешно создан.')
            return redirect('user_list')
    else:
        user_form = CustomUserCreationForm()
        profile_form = UserProfileForm()

    context = {'title': 'Добавить нового пользователя', 'user_form': user_form, 'profile_form': profile_form}
    return render(request, 'accounts/user_form.html', context)

@login_required
def user_update_view(request, pk):
    # --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ ---
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для редактирования пользователей.")
        return redirect('user_list')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---
        
    user = get_object_or_404(User, pk=pk)
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = CustomUserEditForm(request.POST, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f'Данные пользователя {user.username} успешно обновлены.')
            return redirect('user_list')
    else:
        user_form = CustomUserEditForm(instance=user)
        profile_form = UserProfileForm(instance=profile)

    context = {'title': f'Редактировать пользователя: {user.username}', 'user_form': user_form, 'profile_form': profile_form}
    return render(request, 'accounts/user_form.html', context)

# --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ ДЛЯ КЛАССА ---
class UserDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = User
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')
    extra_context = {'title': 'Удалить пользователя'}

    def test_func(self):
        # Разрешаем доступ только суперпользователю
        return self.request.user.is_superuser

    def form_valid(self, form):
        messages.success(self.request, f"Пользователь {self.object.username} был успешно удален.")
        return super().form_valid(form)
    
@login_required
def user_toggle_active_view(request, pk):
    # --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ ---
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для изменения статуса пользователей.")
        return redirect('user_list')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---

    user = get_object_or_404(User, pk=pk)
    if not user.is_superuser:
        user.is_active = not user.is_active
        user.save()
        status = "активирован" if user.is_active else "деактивирован"
        messages.success(request, f"Пользователь {user.username} был успешно {status}.")
    else:
        messages.error(request, "Нельзя деактивировать администратора.")
        
    return redirect('user_list')