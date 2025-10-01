# D:\New_GAT\core\views\api.py (ФИНАЛЬНАЯ, ПОЛНАЯ И РАБОЧАЯ ВЕРСИЯ)

from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from ..models import Quarter, SchoolClass, GatTest, Subject, Student

# --- ФУНКЦИИ ДЛЯ СТРАНИЦЫ "МОНИТОРИНГ" ---

@login_required
def load_quarters(request):
    """ API: Загружает <option> с четвертями для выбранного года, учитывая роль пользователя. """
    year_id = request.GET.get('year_id')
    user = request.user
    
    context = {'placeholder': 'Сначала выберите год'}

    if year_id:
        quarters_qs = Quarter.objects.filter(year_id=year_id)

        # --- ДОБАВЛЕН ФИЛЬТР ДЛЯ ДИРЕКТОРА ---
        # Показываем только те четверти, в которых были тесты для школы этого директора
        if not user.is_superuser and hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
            if user.profile.school:
                quarters_qs = quarters_qs.filter(
                    gattests__school_class__school=user.profile.school
                ).distinct()
        # --- КОНЕЦ ФИЛЬТРА ---

        context = {
            'items': quarters_qs.order_by('name'), 
            'placeholder': 'Выберите четверть...'
        }

    return render(request, 'partials/options.html', context)

@login_required
def load_classes(request):
    """ API: Загружает <option> с классами для выбранных школ. """
    school_ids = request.GET.getlist('school_ids[]')
    context = {'placeholder': 'Сначала выберите школу'}
    if school_ids:
        # Ищем классы, у которых есть родитель (т.е. "5А", "6Б"), а не просто параллели ("5", "6")
        classes = SchoolClass.objects.filter(school_id__in=school_ids).order_by('name')
        context = {'items': classes, 'placeholder': 'Выберите класс...'}
    return render(request, 'partials/options.html', context)

@login_required
def load_subjects(request):
    """ API: Загружает <option> с предметами для выбранных школ. """
    school_ids = request.GET.getlist('school_ids[]')
    context = {'placeholder': 'Сначала выберите школу'}
    if school_ids:
        subjects = Subject.objects.filter(school_id__in=school_ids).order_by('name')
        context = {'items': subjects, 'placeholder': 'Выберите предмет...'}
    return render(request, 'partials/options.html', context)


# --- ОСТАЛЬНЫЕ API ФУНКЦИИ (ДЛЯ ДРУГИХ ЧАСТЕЙ САЙТА) ---

@login_required
def get_previous_subjects_view(request):
    """ API: Получает предметы из предыдущего GAT-теста в той же четверти. """
    class_id = request.GET.get('class_id')
    quarter_id = request.GET.get('quarter_id')
    test_number = request.GET.get('test_number')
    
    if not all([class_id, quarter_id, test_number]): 
        return JsonResponse({'subject_ids': []})
    
    try:
        previous_test = GatTest.objects.filter(
            school_class_id=class_id, 
            quarter_id=quarter_id, 
            test_number__lt=int(test_number)
        ).order_by('-test_number').first()
        
        if previous_test:
            return JsonResponse({'subject_ids': list(previous_test.subjects.values_list('id', flat=True))})
            
    except (ValueError, TypeError):
        pass
        
    return JsonResponse({'subject_ids': []})


@login_required
def header_search_api(request):
    """ API: для поиска по студентам и тестам в шапке сайта. """
    query = request.GET.get('q', '')
    results = []
    if query:
        # --- ИЗМЕНЕНИЕ НАЧАЛО: Ищем по всем мультиязычным полям ---
        students = Student.objects.filter(
            Q(first_name_ru__icontains=query) | Q(last_name_ru__icontains=query) |
            Q(first_name_en__icontains=query) | Q(last_name_en__icontains=query) |
            Q(first_name_tj__icontains=query) | Q(last_name_tj__icontains=query) |
            Q(student_id__icontains=query)
        ).distinct()[:5]

        for s in students:
            results.append({
                'type': 'Студент',
                # Используем first_name_ru и last_name_ru для отображения
                'name': f"{s.first_name_ru} {s.last_name_ru} ({s.student_id})",
                'url': reverse('student_progress', args=[s.id])
            })
        # --- ИЗМЕНЕНИЕ КОНЕЦ ---
        
        tests = GatTest.objects.filter(name__icontains=query)[:5]
        for t in tests:
            results.append({
                'type': 'Тест',
                'name': t.name,
                'url': reverse('class_results_dashboard', args=[t.quarter_id, t.school_class_id])
            })
            
    return JsonResponse({'results': results})


@login_required
def load_subjects_and_classes_for_schools(request):
    """ 
    API (JSON): Загружает предметы и классы для нескольких выбранных школ.
    Эта функция нужна для страницы "Углубленный анализ", оставляем её.
    """
    school_ids = request.GET.getlist('school_ids[]')
    if not school_ids:
        return JsonResponse({'subjects': [], 'classes': []})
    
    subjects = Subject.objects.filter(school_id__in=school_ids).order_by('name').values('id', 'name')
    classes = SchoolClass.objects.filter(school_id__in=school_ids).order_by('name').values('id', 'name')
    
    return JsonResponse({'subjects': list(subjects), 'classes': list(classes)})