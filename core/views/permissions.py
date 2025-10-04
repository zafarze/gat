# D:\New_GAT\core\views\permissions.py (ФИНАЛЬНАЯ ВЕРСИЯ С УЛУЧШЕНИЕМ БЕЗОПАСНОСТИ)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib.auth.models import User
from ..models import School

@login_required
def manage_permissions_view(request):
    """
    Отображает страницу для управления доступом директоров к школам.
    Доступно только администраторам.
    """
    # --- УЛУЧШЕНИЕ: Добавлена проверка на суперпользователя ---
    if not request.user.is_superuser:
        # Если пользователь не администратор, отправляем его на главную
        return redirect('dashboard')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---
    
    directors = User.objects.filter(profile__role='SCHOOL_DIRECTOR').select_related('profile__school').prefetch_related('profile__additional_schools').order_by('last_name')
    all_schools = School.objects.all().order_by('name')

    context = {
        'title': 'Управление правами доступа',
        'directors': directors,
        'all_schools': all_schools
    }
    return render(request, 'permissions/manage.html', context)

@login_required
def toggle_school_access_api(request):
    """
    API для переключения доступа (ON/OFF). Вызывается через JavaScript.
    Доступно только администраторам.
    """
    if request.method == 'POST' and request.user.is_superuser:
        director_id = request.POST.get('director_id')
        school_id = request.POST.get('school_id')
        
        try:
            director = get_object_or_404(User, id=director_id, profile__role='SCHOOL_DIRECTOR')
            school_to_toggle = get_object_or_404(School, id=school_id)
            
            if school_to_toggle in director.profile.additional_schools.all():
                director.profile.additional_schools.remove(school_to_toggle)
                return JsonResponse({'status': 'success', 'action': 'revoked'})
            else:
                director.profile.additional_schools.add(school_to_toggle)
                return JsonResponse({'status': 'success', 'action': 'granted'})
                
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
            
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

def get_accessible_schools(user):
    """
    Возвращает QuerySet школ, доступных пользователю.
    - Для администратора - все школы.
    - Для директора - его основная школа + все дополнительные.
    """
    if user.is_superuser:
        return School.objects.all()

    if hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
        school_ids = []
        if user.profile.school:
            school_ids.append(user.profile.school.id)
        
        additional_ids = list(user.profile.additional_schools.values_list('id', flat=True))
        school_ids.extend(additional_ids)
        
        return School.objects.filter(id__in=list(set(school_ids)))
        
    return School.objects.none()