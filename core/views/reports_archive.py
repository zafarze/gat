# D:\GAT\core\views\reports_archive.py (НОВЫЙ ФАЙЛ)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q

from core.models import (
    AcademicYear, Quarter, School, SchoolClass
)
from core.views.permissions import get_accessible_schools
from core.models import StudentResult

# --- ARCHIVE AND COMPARISON ---

@login_required
def archive_years_view(request):
    """Архив по годам с улучшенной и исправленной статистикой"""
    user = request.user
    accessible_schools = get_accessible_schools(user)

    results_qs = StudentResult.objects.filter(
        student__school_class__school__in=accessible_schools
    )
    year_ids_with_results = results_qs.values_list('gat_test__quarter__year_id', flat=True).distinct()

    years = AcademicYear.objects.filter(
        id__in=year_ids_with_results
    ).annotate(
        test_count=Count(
            'quarters__gat_tests',
            filter=Q(
                quarters__gat_tests__results__isnull=False,
                quarters__gat_tests__school__in=accessible_schools
            ),
            distinct=True
        ),
        student_count=Count(
            'quarters__gat_tests__results__student',
            filter=Q(
                quarters__gat_tests__school__in=accessible_schools
            ),
            distinct=True
        )
    ).order_by('-start_date')

    context = {
        'years': years,
        'title': 'Архив результатов по годам'
    }
    return render(request, 'results/archive_years.html', context)

@login_required
def archive_quarters_view(request, year_id):
    """Архив по четвертям с исправленной статистикой"""
    year = get_object_or_404(AcademicYear, id=year_id)
    user = request.user
    accessible_schools = get_accessible_schools(user)

    quarters = Quarter.objects.filter(
        year=year,
        gat_tests__results__isnull=False,
        gat_tests__school__in=accessible_schools
    ).annotate(
        test_count=Count(
            'gat_tests',
            filter=Q(gat_tests__school__in=accessible_schools),
            distinct=True
        ),
        school_count=Count(
            'gat_tests__school',
            filter=Q(gat_tests__school__in=accessible_schools),
            distinct=True
        )
    ).distinct().order_by('start_date')

    context = {
        'year': year,
        'quarters': quarters,
        'title': f'Архив: {year.name}'
    }
    return render(request, 'results/archive_quarters.html', context)

@login_required
def archive_schools_view(request, quarter_id):
    """Архив по школам с исправленной статистикой"""
    quarter = get_object_or_404(Quarter, id=quarter_id)
    user = request.user
    accessible_schools = get_accessible_schools(user)

    schools = School.objects.filter(
        classes__gat_tests__quarter=quarter,
        classes__gat_tests__results__isnull=False,
        id__in=accessible_schools.values_list('id', flat=True)
    ).annotate(
        class_count=Count(
            'classes',
            filter=Q(classes__gat_tests__quarter=quarter),
            distinct=True
        ),
        student_count=Count(
            'classes__students__results',
            filter=Q(classes__students__results__gat_test__quarter=quarter),
            distinct=True
        )
    ).distinct().order_by('name')

    context = {
        'quarter': quarter,
        'schools': schools,
        'title': f'Архив: {quarter}'
    }
    return render(request, 'results/archive_schools.html', context)

@login_required
def archive_classes_view(request, quarter_id, school_id):
    """
    Отображает родительские классы (параллели),
    в которых есть результаты за выбранную четверть.
    """
    quarter = get_object_or_404(Quarter, id=quarter_id)
    school = get_object_or_404(School, id=school_id)

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if school not in accessible_schools:
            messages.error(request, "У вас нет доступа к архиву этой школы.")
            return redirect('core:results_archive')

    parent_class_ids = SchoolClass.objects.filter(
        school=school,
        students__results__gat_test__quarter=quarter,
        parent__isnull=False
    ).values_list('parent_id', flat=True).distinct()

    parent_classes = SchoolClass.objects.filter(id__in=parent_class_ids).order_by('name')

    context = {
        'quarter': quarter,
        'school': school,
        'parent_classes': parent_classes,
        'title': f'Архив: {school.name} (Выберите параллель)'
    }
    return render(request, 'results/archive_classes.html', context)

@login_required
def archive_subclasses_view(request, quarter_pk, school_pk, class_pk):
    """
    Отображает подклассы (5А, 5Б) для выбранной параллели
    и карточку для общего отчета.
    """
    quarter = get_object_or_404(Quarter, id=quarter_pk)
    school = get_object_or_404(School, id=school_pk)
    parent_class = get_object_or_404(SchoolClass, id=class_pk)

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if school not in accessible_schools:
            messages.error(request, "У вас нет доступа к этой школе.")
            return redirect('core:results_archive')

    subclasses = SchoolClass.objects.filter(
        parent=parent_class,
        school=school,
        students__results__gat_test__quarter=quarter
    ).distinct().order_by('name')

    context = {
        'quarter': quarter,
        'school': school,
        'parent_class': parent_class,
        'subclasses': subclasses,
        'title': f'Архив: {school.name} - {parent_class.name} классы'
    }
    return render(request, 'results/archive_subclasses.html', context)