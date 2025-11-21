# D:\GAT\core\views\booklets.py

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.db.models import Count, Q
from core.models import GatTest, School, SchoolClass
from core.views.permissions import get_accessible_schools

@login_required
def booklet_catalog_view(request):
    """
    Иерархический каталог: Школы -> Классы -> Номера GAT -> Буклеты.
    """
    user = request.user
    accessible_schools = get_accessible_schools(user)
    
    # Получаем параметры навигации
    school_id = request.GET.get('school_id')
    class_id = request.GET.get('class_id')
    gat_number = request.GET.get('gat_number')
    
    context = {
        'title': 'Каталог буклетов',
        'school_id': school_id,
        'class_id': class_id,
        'gat_number': gat_number,
    }

    # --- УРОВЕНЬ 4: КОНКРЕТНЫЕ БУКЛЕТЫ (Финал) ---
    if school_id and class_id and gat_number:
        school = get_object_or_404(School, id=school_id)
        school_class = get_object_or_404(SchoolClass, id=class_id)
        
        tests = GatTest.objects.filter(
            school=school,
            school_class=school_class,
            test_number=gat_number
        ).select_related('quarter__year', 'school_class').prefetch_related('questions__subject').order_by('day', 'name')

        context.update({
            'level': 'booklets',
            'school': school,
            'current_class': school_class,
            'current_gat': gat_number,
            'tests': tests,
            'title': f'Буклеты: {school.name} - {school_class.name} (GAT-{gat_number})'
        })
        
        if request.htmx:
            return render(request, 'booklet/partials/_level_booklets.html', context)

    # --- УРОВЕНЬ 3: НОМЕРА GAT ---
    elif school_id and class_id:
        school = get_object_or_404(School, id=school_id)
        school_class = get_object_or_404(SchoolClass, id=class_id)
        
        available_gats = GatTest.objects.filter(
            school=school,
            school_class=school_class
        ).values('test_number').annotate(
            count=Count('id')
        ).order_by('test_number')

        context.update({
            'level': 'gat_numbers',
            'school': school,
            'current_class': school_class,
            'available_gats': available_gats,
            'title': f'Выберите GAT: {school.name} - {school_class.name}'
        })
        
        if request.htmx:
            return render(request, 'booklet/partials/_level_gat_numbers.html', context)

    # --- УРОВЕНЬ 2: КЛАССЫ ---
    elif school_id:
        school = get_object_or_404(School, id=school_id)
        
        classes = SchoolClass.objects.filter(
            school=school, 
            parent__isnull=True
        ).annotate(
            tests_count=Count('gat_tests')
        ).order_by('name')

        context.update({
            'level': 'classes',
            'school': school,
            'classes': classes,
            'title': f'Классы: {school.name}'
        })
        
        if request.htmx:
            return render(request, 'booklet/partials/_level_classes.html', context)

    # --- УРОВЕНЬ 1: ШКОЛЫ ---
    else:
        schools = accessible_schools.annotate(
            tests_count=Count('gat_tests')
        ).order_by('name')

        context.update({
            'level': 'schools',
            'schools': schools,
            'title': 'Каталог буклетов: Выберите школу'
        })
        
        if request.htmx:
            return render(request, 'booklet/partials/_level_schools.html', context)

    return render(request, 'booklet/booklet_catalog.html', context)


# --- 👇 ВОТ ЭТОЙ ФУНКЦИИ НЕ ХВАТАЛО 👇 ---
@login_required
@require_POST
def toggle_publish_status(request, pk):
    """
    Переключает статус 'is_published_for_students' (AJAX/HTMX).
    """
    test = get_object_or_404(GatTest, pk=pk)
    
    if not (request.user.is_superuser or request.user.is_staff):
         pass 

    test.is_published_for_students = not test.is_published_for_students
    test.save()

    return render(request, 'booklet/partials/_publish_toggle.html', {'test': test})