# D:\GAT\accounts\views.py (SAFE VERSION)

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db import transaction
from django.contrib.auth.models import User
from django.db.models import Q

# Локальные импорты
from .forms import (
    CustomUserCreationForm,
    CustomUserEditForm,
    UserProfileForm,
    EmailChangeForm
)
from .models import UserProfile
from .permissions import UserManagementPermissionMixin

# =============================================================================
# --- Представления для обычных пользователей ---
# =============================================================================

def user_login(request):
    """ Обрабатывает вход пользователя. """
    if request.user.is_authenticated:
        if hasattr(request.user, 'profile') and request.user.profile.is_student:
            return redirect('core:student_dashboard')
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if hasattr(user, 'profile') and user.profile.is_student:
                return redirect('core:student_dashboard')
            return redirect('core:dashboard')
        else:
            messages.error(request, "Пожалуйста, проверьте правильность логина и пароля.")
    else:
        form = AuthenticationForm()
    return render(request, 'accounts/login.html', {'form': form})

@login_required
def user_logout(request):
    """ Обрабатывает выход пользователя. """
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect('core:login')

@login_required
def profile(request):
    """ Отображает и обрабатывает формы на странице профиля пользователя. """
    # --- ✨ SAFE IMPORT: Импортируем здесь, чтобы избежать Circular Import ---
    from core.models import Notification 
    
    user = request.user
    profile_instance, _ = UserProfile.objects.get_or_create(user=user)

    user_edit_form = CustomUserEditForm(instance=user)
    profile_form = UserProfileForm(instance=profile_instance, user=user)
    password_form = PasswordChangeForm(user)
    email_form = EmailChangeForm(user=user, initial={'new_email': user.email})

    if request.method == 'POST':
        action = request.POST.get('action')
        old_email = user.email

        if action == 'update_profile':
            user_edit_form = CustomUserEditForm(request.POST, instance=user)
            profile_form = UserProfileForm(request.POST, request.FILES, instance=profile_instance, user=user)

            if user_edit_form.is_valid() and profile_form.is_valid():
                user_edit_form.save()
                profile_form.save()
                messages.success(request, 'Данные профиля успешно обновлены.')
                return redirect('core:profile')

        elif action == 'change_password':
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Ваш пароль был успешно изменен.')
                return redirect('core:profile')

        elif action == 'change_email':
            email_form = EmailChangeForm(request.POST, user=user)
            if email_form.is_valid():
                new_email = email_form.cleaned_data['new_email']
                try:
                    user.email = new_email
                    user.username = new_email
                    user.save()
                    messages.success(request, f'Ваш Email успешно изменен на {new_email}.')

                    # Уведомление для суперадминов
                    superusers = User.objects.filter(is_superuser=True)
                    message_text = f"Пользователь '{user.get_full_name() or user.username}' изменил email с '{old_email}' на '{new_email}'."
                    admin_user_url = reverse('admin:auth_user_change', args=[user.pk])
                    
                    for admin_user in superusers:
                        Notification.objects.create(user=admin_user, message=message_text, link=admin_user_url)

                    return redirect('core:profile')
                except Exception as e:
                    messages.error(request, f"Произошла ошибка при сохранении нового Email: {e}")

    context = {
        'user_edit_form': user_edit_form,
        'profile_form': profile_form,
        'password_form': password_form,
        'email_form': email_form,
    }
    return render(request, 'accounts/profile.html', context)

# =============================================================================
# --- CRUD-представления (Админка/Директор) ---
# =============================================================================

class UserListView(UserManagementPermissionMixin, ListView):
    model = User
    template_name = 'accounts/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        base_queryset = User.objects.exclude(profile__role=UserProfile.Role.STUDENT).select_related('profile')
        user = self.request.user

        if not user.is_superuser and hasattr(user, 'profile') and user.profile.is_director:
            director_schools = user.profile.schools.all()
            base_queryset = base_queryset.filter(
                Q(profile__school__in=director_schools) |
                Q(profile__homeroom_class__school__in=director_schools),
                profile__role__in=[UserProfile.Role.TEACHER, UserProfile.Role.HOMEROOM_TEACHER]
            ).distinct()

        role_filter = self.request.GET.get('role', 'all')
        if role_filter == 'administrators':
            return base_queryset.filter(is_staff=True).order_by('last_name', 'first_name')
        elif role_filter != 'all':
            return base_queryset.filter(profile__role=role_filter).order_by('last_name', 'first_name')

        return base_queryset.order_by('last_name', 'first_name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Управление пользователями'
        context['active_tab'] = self.request.GET.get('role', 'all')
        context['role_tabs'] = [
            {'key': 'all', 'name': 'Все'},
            {'key': 'administrators', 'name': 'Администраторы'},
            {'key': UserProfile.Role.GENERAL_DIRECTOR, 'name': 'Ген. директоры'},
            {'key': UserProfile.Role.DIRECTOR, 'name': 'Директоры'},
            {'key': UserProfile.Role.EXPERT, 'name': 'Эксперты'},
            {'key': UserProfile.Role.TEACHER, 'name': 'Учителя'},
            {'key': UserProfile.Role.HOMEROOM_TEACHER, 'name': 'Кл. руководители'},
        ]
        
        if not self.request.user.is_superuser and hasattr(self.request.user, 'profile') and self.request.user.profile.is_director:
             context['role_tabs'] = [tab for tab in context['role_tabs'] if tab['key'] in ['all', UserProfile.Role.TEACHER, UserProfile.Role.HOMEROOM_TEACHER]]
             if context['active_tab'] not in ['all', UserProfile.Role.TEACHER, UserProfile.Role.HOMEROOM_TEACHER]:
                 context['active_tab'] = 'all'
        return context

class UserCreateView(UserManagementPermissionMixin, CreateView):
    template_name = 'accounts/user_form.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('core:user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Добавление пользователя'
        if 'profile_form' not in context:
            context['profile_form'] = UserProfileForm(user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        profile_form = UserProfileForm(request.POST, request.FILES, user=request.user)

        if form.is_valid() and profile_form.is_valid():
            return self.form_valid(form, profile_form)
        else:
            return self.form_invalid(form, profile_form)

    def form_valid(self, form, profile_form):
        try:
            with transaction.atomic():
                user = form.save()
                profile_form_rebound = UserProfileForm(
                    self.request.POST,
                    self.request.FILES,
                    instance=user.profile,
                    user=self.request.user
                )
                if profile_form_rebound.is_valid():
                    profile_form_rebound.save()
                    messages.success(self.request, f"Пользователь {user.get_full_name() or user.username} успешно создан.")
                    return redirect(self.success_url)
                else:
                    transaction.set_rollback(True)
                    return self.form_invalid(form, profile_form_rebound)
        except Exception as e:
            messages.error(self.request, f"Ошибка: {e}")
            return self.form_invalid(form, profile_form)

    def form_invalid(self, form, profile_form):
        context = self.get_context_data()
        context['form'] = form
        context['profile_form'] = profile_form
        return self.render_to_response(context)

class UserUpdateView(UserManagementPermissionMixin, UpdateView):
    model = User
    template_name = 'accounts/user_form.html'
    form_class = CustomUserEditForm
    success_url = reverse_lazy('core:user_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Редактирование: {self.object.get_full_name() or self.object.username}'
        if 'profile_form' not in context:
            context['profile_form'] = UserProfileForm(instance=self.object.profile, user=self.request.user)
        return context

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = self.get_form()
        profile_form = UserProfileForm(
            request.POST,
            request.FILES,
            instance=self.object.profile,
            user=request.user
        )

        if form.is_valid() and profile_form.is_valid():
            return self.form_valid(form, profile_form)
        else:
            return self.form_invalid(form, profile_form)

    def form_valid(self, form, profile_form):
        user = form.save()
        profile_form.save()
        messages.success(self.request, f"Данные пользователя {user.get_full_name() or user.username} успешно обновлены.")
        return redirect(self.success_url)

    def form_invalid(self, form, profile_form):
        context = self.get_context_data()
        context['form'] = form
        context['profile_form'] = profile_form
        return self.render_to_response(context)

class UserDeleteView(UserManagementPermissionMixin, DeleteView):
    model = User
    template_name = 'accounts/user_confirm_delete.html'
    success_url = reverse_lazy('core:user_list')

    def form_valid(self, form):
        messages.error(self.request, f"Пользователь {self.object.get_full_name() or self.object.username} был удален.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Удалить: {self.object.get_full_name() or self.object.username}'
        return context

    def dispatch(self, request, *args, **kwargs):
        if self.get_object() == request.user:
            messages.error(request, "Вы не можете удалить свой собственный аккаунт.")
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)

# =============================================================================
# --- Вспомогательные функции ---
# =============================================================================

def is_staff_check(user):
    return user.is_staff or user.is_superuser

@user_passes_test(is_staff_check)
def toggle_user_active(request, pk):
    user_to_toggle = get_object_or_404(User, pk=pk)
    if user_to_toggle == request.user:
        messages.error(request, "Вы не можете изменить свой собственный статус.")
    elif user_to_toggle.is_superuser:
        messages.warning(request, "Статус суперпользователя нельзя изменить.")
    else:
        user_to_toggle.is_active = not user_to_toggle.is_active
        user_to_toggle.save()
        status = "активирован" if user_to_toggle.is_active else "деактивирован"
        messages.info(request, f"Пользователь {user_to_toggle.get_full_name() or user_to_toggle.username} был {status}.")
    return redirect('core:user_list')

@user_passes_test(is_staff_check)
def manage_permissions(request):
    return render(request, 'accounts/manage_permissions.html', {'title': 'Настройка прав доступа'})