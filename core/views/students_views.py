# D:\GAT\core\views\students_views.py (НОВЫЙ ФАЙЛ)

import logging
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render

from .. import utils
from ..models import (
    QuestionCount,
    School,
    SchoolClass,
    Student,
    StudentResult,
    Subject,
)
from .permissions import get_accessible_schools

logger = logging.getLogger('cleanup_logger')

# =============================================================================
# --- ИЕРАРХИЧЕСКИЙ СПИСОК УЧЕНИКОВ ---
# =============================================================================

@login_required
def student_school_list_view(request):
    """Шаг 1: Отображает список школ, доступных пользователю."""
    accessible_schools = get_accessible_schools(request.user)
    
    schools_with_counts = accessible_schools.annotate(
        student_count=Count('classes__students')
    ).order_by('name')

    context = {
        'title': 'Ученики: Выберите школу',
        'schools': schools_with_counts,
    }
    return render(request, 'students/student_school_list.html', context)

@login_required
def student_parallel_list_view(request, school_id):
    """Шаг 2: Отображает список параллелей для выбранной школы."""
    school = get_object_or_404(School, id=school_id)
    
    if school not in get_accessible_schools(request.user):
        messages.error(request, "У вас нет доступа к этой школе.")
        return redirect('core:student_school_list')

    parallels = SchoolClass.objects.filter(school=school, parent__isnull=True)\
                                   .annotate(student_count=Count('subclasses__students'))\
                                   .order_by('name')

    return render(request, 'students/student_parallel_list.html', {
        'title': f'Выберите параллель в "{school.name}"',
        'school': school,
        'parallels': parallels
    })

@login_required
def student_class_list_view(request, parent_id):
    """Шаг 3: Отображает список классов внутри выбранной параллели."""
    parent_class = get_object_or_404(SchoolClass, id=parent_id)
    school = parent_class.school

    if school not in get_accessible_schools(request.user):
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('core:student_school_list')

    classes_queryset = SchoolClass.objects.filter(parent=parent_class)\
                                          .annotate(student_count=Count('students'))\
                                          .order_by('name')
    
    search_query = request.GET.get('q', '')
    if search_query:
        classes_queryset = classes_queryset.filter(name__icontains=search_query)

    context = {
        'title': f'Классы параллели «{parent_class.name}»',
        'school': school,
        'parent_class': parent_class, 
        'classes': classes_queryset,
        'search_query': search_query,
    }

    if request.htmx:
        return render(request, 'students/partials/_class_list.html', context)
        
    return render(request, 'students/student_class_list.html', context)

@login_required
def student_list_view(request, class_id):
    """Шаг 4: Отображает список учеников в конкретном классе."""
    school_class = get_object_or_404(SchoolClass.objects.select_related('school', 'parent'), id=class_id)
    
    if school_class.school not in get_accessible_schools(request.user):
        messages.error(request, "У вас нет доступа к этому классу.")
        return redirect('core:student_school_list')

    student_list = Student.objects.filter(school_class=school_class)\
                                 .select_related('user_profile__user')\
                                 .order_by('last_name_ru', 'first_name_ru')

    context = {
        'title': f'Ученики класса {school_class.name}',
        'school_class': school_class,
        'students': student_list,
    }
    return render(request, 'students/student_list_final.html', context)

@login_required
def student_list_combined_view(request, parallel_id):
    """Отображает ВСЕХ учеников в параллели."""
    parallel = get_object_or_404(SchoolClass.objects.select_related('school'), id=parallel_id, parent__isnull=True)
    
    if parallel.school not in get_accessible_schools(request.user):
        messages.error(request, "У вас нет доступа к этому разделу.")
        return redirect('core:student_school_list')

    student_list = Student.objects.filter(school_class__parent=parallel)\
                                 .select_related('user_profile__user', 'school_class')\
                                 .order_by('school_class__name', 'last_name_ru', 'first_name_ru')

    context = {
        'title': f'Все ученики параллели «{parallel.name}»',
        'school_class': parallel,
        'students': student_list,
        'is_combined_view': True,
    }
    return render(request, 'students/student_list_final.html', context)

# =============================================================================
# --- АНАЛИТИКА ПРОГРЕССА СТУДЕНТА ---
# =============================================================================

def _get_grade_and_subjects_performance(result, subject_map):
    """
    Вспомогательная функция для student_progress_view.
    Рассчитывает оценку и успеваемость по предметам на основе QuestionCount.
    """
    student_class = result.student.school_class
    parent_class = student_class.parent if student_class.parent else student_class

    # 1. Получаем карту макс. баллов для параллели этого ученика
    q_counts_parallel = {
        qc.subject_id: qc.number_of_questions
        for qc in QuestionCount.objects.filter(school_class=parent_class)
    }

    total_student_score = 0
    total_max_score = 0
    subject_performance = []
    processed_scores = [] # (Эта переменная не используется в student_progress_view, можно убрать)

    if isinstance(result.scores_by_subject, dict):
        for subj_id_str, answers_dict in result.scores_by_subject.items():
            try:
                subj_id = int(subj_id_str)
                subject_name = subject_map.get(subj_id)
                q_count_for_subject = q_counts_parallel.get(subj_id, 0) # Макс. балл

                if subject_name and isinstance(answers_dict, dict):
                    correct_q = sum(1 for answer in answers_dict.values() if answer is True)
                    
                    total_student_score += correct_q
                    total_max_score += q_count_for_subject # Суммируем макс. балл

                    if q_count_for_subject > 0:
                        perf = (correct_q / q_count_for_subject) * 100
                        subject_performance.append({'name': subject_name, 'perf': perf})
            except (ValueError, TypeError):
                continue

    overall_percentage = (total_student_score / total_max_score) * 100 if total_max_score > 0 else 0
    grade = utils.calculate_grade_from_percentage(overall_percentage)
    
    best_subject = max(subject_performance, key=lambda x: x['perf']) if subject_performance else None
    worst_subject = min(subject_performance, key=lambda x: x['perf']) if subject_performance else None
    
    # Возвращаем только то, что нужно
    return grade, best_subject, worst_subject, [] # processed_scores не нужен


@login_required
def student_progress_view(request, student_id):
    """Детальная аналитика прогресса ученика"""
    student = get_object_or_404(
        Student.objects.select_related('school_class__school').prefetch_related('notes__author'), 
        id=student_id
    )
    
    if not request.user.is_superuser and student.school_class.school not in get_accessible_schools(request.user):
        messages.error(request, "У вас нет доступа к данным этого ученика.")
        return redirect('core:student_school_list')
    
    student_results_qs = student.results.select_related('gat_test__quarter__year').order_by('-gat_test__test_date')

    if not student_results_qs.exists():
        return render(request, 'students/student_progress.html', {
            'title': f'Аналитика: {student}', 
            'student': student, 
            'notes': student.notes.all(), 
            'has_results': False
        })

    test_ids = student_results_qs.values_list('gat_test_id', flat=True)
    all_results_for_tests = StudentResult.objects.filter(
        gat_test_id__in=test_ids
    ).select_related('student__school_class__school')
    
    scores_by_test, scores_by_class, scores_by_school = defaultdict(list), defaultdict(lambda: defaultdict(list)), defaultdict(lambda: defaultdict(list))
    
    for res in all_results_for_tests:
        scores_by_test[res.gat_test_id].append(res.total_score)
        scores_by_class[res.gat_test_id][res.student.school_class_id].append(res.total_score)
        scores_by_school[res.gat_test_id][res.student.school_class.school_id].append(res.total_score)
    
    for test_id in scores_by_test:
        scores_by_test[test_id].sort(reverse=True)
        for class_id in scores_by_class[test_id]: 
            scores_by_class[test_id][class_id].sort(reverse=True)
        for school_id in scores_by_school[test_id]: 
            scores_by_school[test_id][school_id].sort(reverse=True)
    
    subject_map = {s.id: s.name for s in Subject.objects.all()}
    detailed_results_data = []
    
    for result in student_results_qs:
        student_score = result.total_score
        class_scores = scores_by_class.get(result.gat_test_id, {}).get(student.school_class_id, [])
        school_scores = scores_by_school.get(result.gat_test_id, {}).get(student.school_class.school_id, [])
        parallel_scores = scores_by_test.get(result.gat_test_id, [])

        try: class_rank = class_scores.index(student_score) + 1
        except ValueError: class_rank = None
        try: school_rank = school_scores.index(student_score) + 1
        except ValueError: school_rank = None
        try: parallel_rank = parallel_scores.index(student_score) + 1
        except ValueError: parallel_rank = None

        grade, best_s, worst_s, processed_scores = _get_grade_and_subjects_performance(result, subject_map)
        
        detailed_results_data.append({
            'result': result, 
            'class_rank': class_rank, 'class_total': len(class_scores),
            'parallel_rank': parallel_rank, 'parallel_total': len(parallel_scores),
            'school_rank': school_rank, 'school_total': len(school_scores),
            'grade': grade, 'best_subject': best_s, 'worst_subject': worst_s, 
            'processed_scores': processed_scores
        })
        
    comparison_data = None
    if len(detailed_results_data) >= 2:
        latest, previous = detailed_results_data[0], detailed_results_data[1]
        grade_diff = (latest.get('grade') - previous.get('grade')) if latest.get('grade') is not None and previous.get('grade') is not None else None
        rank_diff = (previous.get('class_rank') - latest.get('class_rank')) if all([previous.get('class_rank'), latest.get('class_rank')]) else None
        comparison_data = {
            'latest': latest, 'previous': previous, 
            'grade_diff': grade_diff, 'rank_diff': rank_diff
        }
    
    context = {
        'title': f'Аналитика: {student}', 
        'student': student, 
        'detailed_results_data': detailed_results_data, 
        'comparison_data': comparison_data, 
        'notes': student.notes.all(), 
        'has_results': True
    }
    return render(request, 'students/student_progress.html', context)

# =============================================================================
# --- ОЧИСТКА ДАННЫХ (ТОЛЬКО ДЛЯ СУПЕРПОЛЬЗОВАТЕЛЯ) ---
# =============================================================================

@login_required
def data_cleanup_view(request):
    """Страница для массового удаления данных"""
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect('core:student_school_list')

    if request.method == 'POST':
        user = request.user
        if 'delete_students_parallel' in request.POST:
            parallel_id = request.POST.get('parallel_id')
            if parallel_id:
                parallel = get_object_or_404(SchoolClass, pk=parallel_id)
                students_to_delete = Student.objects.filter(school_class__parent_id=parallel_id)
                deleted_count, _ = students_to_delete.delete()
                logger.critical(f"USER: '{user.username}' удалил {deleted_count} УЧЕНИКОВ из параллели '{parallel.name}'.")
                messages.warning(request, f'ВНИМАНИЕ: Удалено {deleted_count} учеников из параллели "{parallel.name}".')
            else:
                messages.error(request, 'Вы не выбрали параллель для удаления учеников.')

        elif 'clear_results_class' in request.POST:
            class_id = request.POST.get('class_id')
            if class_id:
                school_class = SchoolClass.objects.get(pk=class_id)
                class_name = school_class.name
                deleted_count, _ = StudentResult.objects.filter(student__school_class_id=class_id).delete()
                logger.warning(f"USER: '{user.username}' удалил {deleted_count} РЕЗУЛЬТАТОВ ТЕСТОВ для класса '{class_name}'.")
                messages.success(request, f'Успешно удалено {deleted_count} записей для класса "{class_name}".')
            else:
                messages.error(request, 'Вы не выбрали класс для очистки результатов.')

        elif 'clear_results_all' in request.POST:
            deleted_count, _ = StudentResult.objects.all().delete()
            logger.warning(f"USER: '{user.username}' удалил ВСЕ ({deleted_count}) РЕЗУЛЬТАТЫ ТЕСТОВ в системе.")
            messages.success(request, f'ПОЛНАЯ ОЧИСТКА РЕЗУЛЬТАТОВ ЗАВЕРШЕНА. Удалено {deleted_count} записей.')

        elif 'delete_students_class' in request.POST:
            class_id = request.POST.get('class_id')
            if class_id:
                school_class = SchoolClass.objects.get(pk=class_id)
                class_name = school_class.name
                deleted_count, _ = Student.objects.filter(school_class_id=class_id).delete()
                logger.critical(f"USER: '{user.username}' удалил {deleted_count} УЧЕНИКОВ из класса '{class_name}'.")
                messages.warning(request, f'ВНИМАНИЕ: Удалено {deleted_count} учеников из класса "{class_name}".')
            else:
                messages.error(request, 'Вы не выбрали класс для удаления учеников.')

        elif 'delete_students_all' in request.POST:
            deleted_count, _ = Student.objects.all().delete()
            logger.critical(f"USER: '{user.username}' удалил ВСЕХ ({deleted_count}) УЧЕНИКОВ в системе.")
            messages.warning(request, f'ВНИМАНИЕ: ВСЕ УЧЕНИКИ В СИСТЕМЕ ({deleted_count}) БЫЛИ УДАЛЕНЫ.')

        return redirect('core:data_cleanup')

    classes = SchoolClass.objects.select_related('school').order_by('school__name', 'name')
    parallels = SchoolClass.objects.filter(parent__isnull=True).select_related('school').order_by('school__name', 'name')
    
    context = {
        'title': 'Очистка и управление данными',
        'classes': classes,
        'parallels': parallels,
    }
    return render(request, 'students/data_cleanup.html', context)