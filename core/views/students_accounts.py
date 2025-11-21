# D:\GAT\core\views\students_accounts.py (НОВЫЙ ФАЙЛ)

import json
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.template.loader import render_to_string
from django.urls import reverse_lazy
from django.utils.crypto import get_random_string
from weasyprint import HTML

from accounts.models import UserProfile
from ..models import SchoolClass, Student
from .permissions import get_accessible_schools

# =============================================================================
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ПРОВЕРКИ ПРАВ ---
# =============================================================================

def _check_student_account_permission(user, student):
    """Вспомогательная функция для проверки прав на управление аккаунтом ученика."""
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role == UserProfile.Role.DIRECTOR:
        if student.school_class.school in get_accessible_schools(user):
            return True
    return False

def _check_class_or_parallel_permission(user, class_or_parallel):
    """Вспомогательная функция для проверки прав на класс/параллель."""
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    if profile and profile.role == UserProfile.Role.DIRECTOR:
        if class_or_parallel.school in get_accessible_schools(user):
            return True
    return False

# =============================================================================
# --- УПРАВЛЕНИЕ АККАУНТАМИ ---
# =============================================================================

@login_required
@transaction.atomic
def create_student_user_account(request, student_id):
    """Создает аккаунт для отдельного ученика"""
    student = get_object_or_404(Student.objects.select_related('school_class__school'), id=student_id)
    redirect_url = reverse_lazy('core:student_list', kwargs={'class_id': student.school_class_id})

    if not _check_student_account_permission(request.user, student):
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect(redirect_url)

    if request.method == 'POST':
        if hasattr(student, 'user_profile') and student.user_profile:
            messages.warning(request, f"У ученика {student} уже есть аккаунт.")
            return redirect(redirect_url)

        try:
            first_name = student.first_name_en or ''
            last_name = student.last_name_en or ''
            base_username = f"{first_name}{last_name}" if first_name or last_name else student.student_id
            base_username = ''.join(e for e in base_username if e.isalnum()).lower()
            
            username = base_username or 'student'
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            password = get_random_string(length=8)
            
            user = User.objects.create_user(
                username=username, 
                password=password, 
                first_name=student.first_name_ru, 
                last_name=student.last_name_ru
            )
            
            # Сигнал должен был создать профиль, просто получаем его
            profile = user.profile
            profile.role = UserProfile.Role.STUDENT
            profile.student = student
            profile.save()

            messages.success(
                request, 
                f"Аккаунт для {student} успешно создан. Логин: {username}, Пароль: {password}"
            )
            
        except Exception as e:
            messages.error(request, f"Ошибка при создании аккаунта: {e}")
            
        return redirect(redirect_url)
    
    return redirect(redirect_url)

@login_required
def student_reset_password(request, user_id):
    """Сброс пароля ученика с поддержкой HTMX."""
    user_to_reset = get_object_or_404(User, id=user_id)
    student = get_object_or_404(Student.objects.select_related('school_class__school'), user_profile__user=user_to_reset)
    redirect_url = reverse_lazy('core:student_list', kwargs={'class_id': student.school_class_id})

    if not _check_student_account_permission(request.user, student):
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect(redirect_url)

    if request.method == 'POST':
        new_password = get_random_string(length=8)
        user_to_reset.set_password(new_password)
        user_to_reset.save()

        if request.htmx:
            context = {
                'student': student,
                'new_password': new_password
            }
            html = render_to_string('students/partials/_reset_password_result.html', context, request=request)
            
            trigger = {
                "show-message": {
                    "text": f"Пароль для {user_to_reset.username} сброшен.",
                    "type": "success"
                }
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            
            return HttpResponse(html, headers=headers)
        else:
            messages.success(
                request,
                f"Пароль для {user_to_reset.username} сброшен. Новый пароль: {new_password}"
            )
            return redirect(redirect_url)
    
    return redirect(redirect_url)

@login_required
@transaction.atomic
def delete_student_user_account(request, user_id):
    """Удаляет объект User, связанный с учеником"""
    user_to_delete = get_object_or_404(User, id=user_id)
    student = get_object_or_404(Student.objects.select_related('school_class__school'), user_profile__user=user_to_delete)
    redirect_url = reverse_lazy('core:student_list', kwargs={'class_id': student.school_class_id})

    if not _check_student_account_permission(request.user, student):
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect(redirect_url)

    if request.method == 'POST':
        username = user_to_delete.username
        user_to_delete.delete()
        messages.success(request, f"Аккаунт пользователя '{username}' был успешно удален.")
        return redirect(redirect_url)

    return redirect(redirect_url)

# =============================================================================
# --- МАССОВЫЕ ОПЕРАЦИИ С АККАУНТАМИ ---
# =============================================================================

@login_required
@transaction.atomic
def class_create_export_accounts(request, class_id):
    """Массовое создание/сброс и экспорт аккаунтов для КЛАССА."""
    school_class = get_object_or_404(SchoolClass.objects.select_related('school'), id=class_id)
    redirect_url = reverse_lazy('core:student_list', kwargs={'class_id': class_id})

    if not _check_class_or_parallel_permission(request.user, school_class):
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect(redirect_url)
    
    action = request.POST.get('action')
    credentials_list = []
    
    students_with_accounts = Student.objects.filter(
        school_class=school_class, 
        user_profile__isnull=False
    ).select_related('user_profile__user')

    reset_count = 0
    for student in students_with_accounts:
        user = student.user_profile.user
        password_to_show = '(пароль установлен)'
        if action == 'reset_and_export':
            new_password = get_random_string(length=8)
            user.set_password(new_password)
            user.save()
            password_to_show = new_password
            reset_count += 1
        credentials_list.append({
            'full_name': student.full_name_ru, 
            'username': user.username, 
            'password': password_to_show
        })

    students_to_create = Student.objects.filter(
        school_class=school_class, 
        user_profile__isnull=True
    )
    
    created_count = 0
    for student in students_to_create:
        first_name = student.first_name_en or ''
        last_name = student.last_name_en or ''
        base_username = f"{first_name}{last_name}" if first_name or last_name else student.student_id
        base_username = ''.join(e for e in base_username if e.isalnum()).lower()
        username = base_username or 'student'
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        password = get_random_string(length=8)
        user = User.objects.create_user(
            username=username, password=password, 
            first_name=student.first_name_ru, last_name=student.last_name_ru
        )
        profile = user.profile
        profile.role = UserProfile.Role.STUDENT
        profile.student = student
        profile.save()
        credentials_list.append({
            'full_name': student.full_name_ru, 
            'username': username, 
            'password': password
        })
        created_count += 1

    if not credentials_list:
        messages.warning(request, "В этом классе нет учеников для экспорта.")
        return redirect(redirect_url)
        
    credentials_list.sort(key=lambda x: x['full_name'])
    
    context = {'credentials': credentials_list, 'school_class': school_class}
    html_string = render_to_string('students/logins_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="logins_{school_class.name}.pdf"'
    HTML(string=html_string).write_pdf(response)
    
    message_parts = []
    if created_count > 0: message_parts.append(f"Создано {created_count} новых аккаунтов")
    if reset_count > 0: message_parts.append(f"сброшен пароль для {reset_count} существующих")
    
    final_message = ", ".join(message_parts).capitalize() + ". PDF-файл с актуальными данными сгенерирован."
    messages.success(request, final_message)
        
    return response

@login_required
@transaction.atomic
def parallel_create_export_accounts(request, parallel_id):
    """Массовое создание/сброс и экспорт аккаунтов для ВСЕЙ ПАРАЛЛЕЛИ."""
    parallel = get_object_or_404(SchoolClass.objects.select_related('school'), id=parallel_id, parent__isnull=True)
    redirect_url = reverse_lazy('core:student_list_combined', kwargs={'parallel_id': parallel_id})

    if not _check_class_or_parallel_permission(request.user, parallel):
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect(redirect_url)
    
    action = request.POST.get('action')
    students_in_parallel = Student.objects.filter(school_class__parent=parallel)
    
    credentials_list = []
    reset_count = 0
    created_count = 0

    students_with_accounts = students_in_parallel.filter(
        user_profile__isnull=False
    ).select_related('user_profile__user')

    for student in students_with_accounts:
        user = student.user_profile.user
        password_to_show = '(пароль установлен)'
        if action == 'reset_and_export':
            new_password = get_random_string(length=8)
            user.set_password(new_password)
            user.save()
            password_to_show = new_password
            reset_count += 1
        credentials_list.append({
            'full_name': student.full_name_ru, 
            'username': user.username, 
            'password': password_to_show
        })

    students_to_create = students_in_parallel.filter(user_profile__isnull=True)
    
    for student in students_to_create:
        first_name = student.first_name_en or ''
        last_name = student.last_name_en or ''
        base_username = f"{first_name}{last_name}" if first_name or last_name else student.student_id
        base_username = ''.join(e for e in base_username if e.isalnum()).lower()
        username = base_username or 'student'
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        password = get_random_string(length=8)
        user = User.objects.create_user(
            username=username, password=password, 
            first_name=student.first_name_ru, last_name=student.last_name_ru
        )
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = UserProfile.Role.STUDENT
        profile.student = student
        profile.save()
        credentials_list.append({
            'full_name': student.full_name_ru, 
            'username': username, 
            'password': password
        })
        created_count += 1

    if not credentials_list:
        messages.warning(request, "В этой параллели нет учеников для экспорта.")
        return redirect(redirect_url)
        
    credentials_list.sort(key=lambda x: x['full_name'])
    
    context = {'credentials': credentials_list, 'school_class': parallel}
    html_string = render_to_string('students/logins_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="logins_parallel_{parallel.name}.pdf"'
    HTML(string=html_string).write_pdf(response)
    
    message_parts = []
    if created_count > 0: message_parts.append(f"Создано {created_count} новых аккаунтов")
    if reset_count > 0: message_parts.append(f"сброшен пароль для {reset_count} существующих")
    
    final_message = ", ".join(message_parts).capitalize() + ". PDF-файл с актуальными данными сгенерирован."
    if message_parts:
        messages.success(request, final_message)
        
    return response