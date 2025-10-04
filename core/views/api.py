# D:\New_GAT\core\views\api.py (ФИНАЛЬНАЯ ВЕРСИЯ С ПРАВАМИ ДОСТУПА)

from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse

from ..models import Quarter, SchoolClass, GatTest, Subject, Student
from .permissions import get_accessible_schools # <--- Подключаем нашу "умную" функцию

@login_required
def load_quarters(request):
    """ API: Загружает <option> с четвертями для выбранного года, учитывая права доступа. """
    year_id = request.GET.get('year_id')
    user = request.user
    context = {'placeholder': 'Сначала выберите год'}

    if year_id:
        quarters_qs = Quarter.objects.filter(year_id=year_id)

        # --- ОБНОВЛЕННЫЙ ФИЛЬТР ДЛЯ ДИРЕКТОРА ---
        # Показываем только те четверти, в которых были тесты для доступных директору школ
        if not user.is_superuser:
            accessible_schools = get_accessible_schools(user)
            quarters_qs = quarters_qs.filter(
                gattests__school_class__school__in=accessible_schools
            ).distinct()
        # --- КОНЕЦ ФИЛЬТРА ---

        context = {
            'items': quarters_qs.order_by('name'), 
            'placeholder': 'Выберите четверть...'
        }
    return render(request, 'partials/options.html', context)

@login_required
def load_classes(request):
    """ API: Загружает <option> с классами (в формате "Школа - Класс") для выбранных школ. """
    school_ids = request.GET.getlist('school_ids[]')
    context = {'placeholder': 'Сначала выберите школу'}
    if school_ids:
        # Добавляем .select_related('school') для оптимизации и доступа к названию школы
        classes = SchoolClass.objects.filter(school_id__in=school_ids).select_related('school').order_by('school__name', 'name')
        context = {'items': classes, 'placeholder': 'Выберите класс...'}
    # Указываем новый шаблон для отображения
    return render(request, 'partials/school_item_options.html', context)

@login_required
def load_subjects(request):
    """ API: Загружает <option> с предметами (в формате "Школа - Предмет") для выбранных школ. """
    school_ids = request.GET.getlist('school_ids[]')
    context = {'placeholder': 'Сначала выберите школу'}
    if school_ids:
        # Добавляем .select_related('school')
        subjects = Subject.objects.filter(school_id__in=school_ids).select_related('school').order_by('school__name', 'name')
        context = {'items': subjects, 'placeholder': 'Выберите предмет...'}
    # Указываем новый шаблон для отображения
    return render(request, 'partials/school_item_options.html', context)

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
    """ API: для поиска по студентам и тестам в шапке сайта с учетом прав доступа. """
    query = request.GET.get('q', '').strip()
    results = []
    user = request.user
    
    if query:
        # --- ОБНОВЛЕННЫЙ ФИЛЬТР ДЛЯ ДИРЕКТОРА ---
        students_qs = Student.objects.all()
        tests_qs = GatTest.objects.all()
        
        if not user.is_superuser:
            accessible_schools = get_accessible_schools(user)
            students_qs = students_qs.filter(school_class__school__in=accessible_schools)
            tests_qs = tests_qs.filter(school_class__school__in=accessible_schools)
        # --- КОНЕЦ ФИЛЬТРА ---

        students = students_qs.filter(
            Q(first_name_ru__icontains=query) | Q(last_name_ru__icontains=query) |
            Q(first_name_en__icontains=query) | Q(last_name_en__icontains=query) |
            Q(first_name_tj__icontains=query) | Q(last_name_tj__icontains=query) |
            Q(student_id__icontains=query)
        ).distinct()[:5]

        for s in students:
            results.append({
                'type': 'Студент',
                'name': f"{s.first_name_ru} {s.last_name_ru} ({s.student_id})",
                'url': reverse('student_progress', args=[s.id])
            })
        
        tests = tests_qs.filter(name__icontains=query)[:5]
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
    API (JSON): Загружает предметы и классы для нескольких выбранных школ,
    формируя для них имя в формате "Школа - Название".
    """
    school_ids = request.GET.getlist('school_ids[]')
    user = request.user
    
    if not school_ids:
        return JsonResponse({'subjects': [], 'classes': []})
    
    # --- БЛОК ПРОВЕРКИ БЕЗОПАСНОСТИ ---
    # По умолчанию считаем, что все запрошенные ID валидны
    valid_school_ids = school_ids
    
    # Если пользователь не администратор, мы должны проверить, к каким школам у него есть доступ
    if not user.is_superuser:
        accessible_schools = get_accessible_schools(user)
        # Получаем список ID школ, к которым у пользователя точно есть доступ
        allowed_school_ids = [str(s.id) for s in accessible_schools]
        # Из запрошенных ID оставляем только те, которые есть в списке разрешенных
        valid_school_ids = [sid for sid in school_ids if sid in allowed_school_ids]
    
    # Делаем запросы в базу данных, используя уже безопасный список ID
    subjects_qs = Subject.objects.filter(school_id__in=valid_school_ids)
    classes_qs = SchoolClass.objects.filter(school_id__in=valid_school_ids)
    # --- КОНЕЦ ПРОВЕРКИ БЕЗОПАСНОСТИ ---

    # --- ФОРМИРОВАНИЕ ДАННЫХ ДЛЯ КЛАССОВ ---
    # Используем .select_related('school') для оптимизации (делает 1 запрос вместо множества)
    classes_qs_with_schools = classes_qs.select_related('school').order_by('school__name', 'name')
    classes_data = []
    for cls in classes_qs_with_schools:
        classes_data.append({
            'id': cls.id,
            'name': f"{cls.school.name} - {cls.name}"
        })
    
    # --- ФОРМИРОВАНИЕ ДАННЫХ ДЛЯ ПРЕДМЕТОВ ---
    subjects_qs_with_schools = subjects_qs.select_related('school').order_by('school__name', 'name')
    subjects_data = []
    for subj in subjects_qs_with_schools:
        subjects_data.append({
            'id': subj.id,
            'name': f"{subj.school.name} - {subj.name}"
        })

    # Возвращаем JSON-ответ с обновленными списками
    return JsonResponse({'subjects': subjects_data, 'classes': classes_data})