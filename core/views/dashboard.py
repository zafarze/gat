# D:\New_GAT\core\views\dashboard.py (ФИНАЛЬНАЯ ВЕРСИЯ С ПРАВАМИ ДОСТУПА)

import json
from collections import defaultdict
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.utils import timezone

from ..models import School, Student, GatTest, StudentResult, Quarter, AcademicYear
from .permissions import get_accessible_schools # <--- Подключаем нашу "умную" функцию

@login_required
def dashboard_view(request):
    """
    Отображает главную панель управления с фильтрацией по правам доступа.
    """
    user = request.user
    today = timezone.now().date()
    period = request.GET.get('period', 'year')
    start_date, end_date = None, None
    
    if period == 'quarter':
        current_quarter = Quarter.objects.filter(start_date__lte=today, end_date__gte=today).first()
        if current_quarter:
            start_date, end_date = current_quarter.start_date, current_quarter.end_date
    elif period == 'year':
        current_year = AcademicYear.objects.filter(start_date__lte=today, end_date__gte=today).first()
        if current_year:
            start_date, end_date = current_year.start_date, current_year.end_date

    # --- НОВАЯ ЛОГИКА ФИЛЬТРАЦИИ ПО ПРАВАМ ДОСТУПА ---
    accessible_schools = get_accessible_schools(user)
    
    # Базовый QuerySet для всех дальнейших вычислений
    base_results_qs = StudentResult.objects.select_related('student__school_class__school', 'gat_test')
    if start_date and end_date:
        base_results_qs = base_results_qs.filter(gat_test__test_date__range=(start_date, end_date))
    
    # Применяем фильтр по всем доступным школам
    base_results_qs = base_results_qs.filter(student__school_class__school__in=accessible_schools)

    # --- РАСЧЕТ KPI КАРТОЧЕК ---
    kpi_results_qs = base_results_qs # Используем уже отфильтрованные данные
    school_count = accessible_schools.filter(classes__students__results__in=kpi_results_qs).distinct().count()
    student_count = Student.objects.filter(results__in=kpi_results_qs).distinct().count()
    test_count = GatTest.objects.filter(student_results__in=kpi_results_qs).distinct().count()
    result_count = kpi_results_qs.count()

    # --- ПОДГОТОВКА ДАННЫХ ДЛЯ ГРАФИКОВ И ВИДЖЕТОВ ---
    school_chart_labels, school_chart_data = '[]', '[]'
    director_chart_labels, director_chart_data = '[]', '[]'

    # Условие изменено на более надежное: не суперпользователь
    if not user.is_superuser:
        # График для директора (успеваемость классов)
        class_performance = defaultdict(lambda: {'total_score': 0, 'count': 0})
        for result in base_results_qs:
            # Для наглядности группируем по "Школа - Класс"
            class_key = f"{result.student.school_class.school.name} - {result.student.school_class.name}"
            score = sum(sum(a) for a in result.scores.values())
            class_performance[class_key]['total_score'] += score
            class_performance[class_key]['count'] += 1
        
        sorted_classes = sorted(class_performance.items(), key=lambda item: (item[1]['total_score'] / item[1]['count']) if item[1]['count'] > 0 else 0, reverse=True)
        director_chart_labels = json.dumps([name for name, data in sorted_classes], ensure_ascii=False)
        director_chart_data = json.dumps([round((data['total_score'] / data['count']), 1) if data['count'] > 0 else 0 for name, data in sorted_classes])

    else:
        # Логика для администратора (Топ-10 школ)
        school_scores = defaultdict(lambda: {'total_score': 0, 'count': 0})
        for result in base_results_qs:
            school_name = result.student.school_class.school.name
            score = sum(sum(a) for a in result.scores.values())
            school_scores[school_name]['total_score'] += score
            school_scores[school_name]['count'] += 1

        school_performance = [{'name': name, 'avg_score': round(data['total_score'] / data['count'], 1) if data['count'] > 0 else 0} for name, data in school_scores.items()]
        school_performance.sort(key=lambda x: x['avg_score'], reverse=True)
        top_schools = school_performance[:10]
        school_chart_labels = json.dumps([s['name'] for s in top_schools], ensure_ascii=False)
        school_chart_data = json.dumps([s['avg_score'] for s in top_schools])

    # Виджеты "Лидеры" и "В зоне внимания"
    student_avg_scores = defaultdict(lambda: {'total_score': 0, 'count': 0})
    for r in base_results_qs:
        score = sum(sum(a) for a in r.scores.values())
        student_avg_scores[r.student_id]['total_score'] += score
        student_avg_scores[r.student_id]['count'] += 1
    
    student_performance = []
    students_map = {s.id: s for s in Student.objects.filter(id__in=student_avg_scores.keys()).select_related('school_class')}
    for student_id, data in student_avg_scores.items():
        if data['count'] > 0:
            avg_score = round(data['total_score'] / data['count'], 1)
            student_obj = students_map.get(student_id)
            if student_obj:
                student_performance.append({'student': student_obj, 'avg_score': avg_score})
    
    sorted_students = sorted(student_performance, key=lambda x: x['avg_score'], reverse=True)
    top_students = sorted_students[:5]
    worst_students = sorted_students[-5:][::-1]

    # Тесты без результатов (теперь тоже фильтруются по доступным школам)
    tests_qs_for_widget = GatTest.objects.filter(school_class__school__in=accessible_schools)
    if start_date and end_date:
        tests_qs_for_widget = tests_qs_for_widget.filter(test_date__range=(start_date, end_date))
    tests_without_results = tests_qs_for_widget.annotate(num_results=Count('student_results')).filter(num_results=0).select_related('school_class').order_by('-test_date')[:5]

    context = {
        'title': 'Панель управления', 'selected_period': period, 'school_count': school_count,
        'student_count': student_count, 'test_count': test_count, 'result_count': result_count,
        'school_chart_labels': school_chart_labels, 'school_chart_data': school_chart_data,
        'director_chart_labels': director_chart_labels, 'director_chart_data': director_chart_data,
        'top_students': top_students, 'worst_students': worst_students, 'tests_without_results': tests_without_results,
    }
    return render(request, 'dashboard.html', context)

@login_required
def management_view(request):
    """Отображает страницу со ссылками на разделы управления."""
    return render(request, 'management.html', {'title': 'Управление'})