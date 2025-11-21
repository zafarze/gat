# D:\GAT\core\views\reports_comparison.py (НОВЫЙ ФАЙЛ)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from core.models import (
    GatTest, Quarter, QuestionCount, SchoolClass, StudentResult
)
from core.views.permissions import get_accessible_schools

# --- Вспомогательная функция (перенесена из reports.py) ---

def _get_data_for_test(gat_test):
    """
    Вспомогательная функция для class_results_dashboard_view и compare_class_tests_view.
    Получает данные по ОДНОМУ тесту.
    """
    if not gat_test:
        return [], []

    table_header = []

    # ИСПРАВЛЕНИЕ: Логика получения заголовков должна использовать
    # предметы из BankQuestion, связанных с тестом, а не все QuestionCount
    
    # 1. Получаем предметы ТОЛЬКО из этого теста
    subjects_in_test = gat_test.subjects.all().order_by('name')
    
    # 2. Получаем родительский класс (параллель)
    parent_class = gat_test.school_class
    if parent_class and parent_class.parent:
        parent_class = parent_class.parent
        
    if parent_class:
        # 3. Получаем QuestionCounts для этой параллели
        q_counts_map = {
            qc.subject_id: qc.number_of_questions
            for qc in QuestionCount.objects.filter(school_class=parent_class)
        }
        
        # 4. Создаем заголовки, используя только предметы из теста
        for subject in subjects_in_test:
            q_count = q_counts_map.get(subject.id, 0)
            table_header.append({
                'subject': subject,
                'questions': range(1, q_count + 1),
                'questions_count': q_count,
                'school_class': parent_class
            })

    student_results = StudentResult.objects.filter(
        gat_test=gat_test
    ).select_related('student__school_class__school')

    students_data = []
    for result in student_results:
        # ИСПРАВЛЕНИЕ: Обрабатываем словарь ответов, а не список
        subject_scores = {}
        if isinstance(result.scores_by_subject, dict):
            for subject_id_str, answers_dict in result.scores_by_subject.items():
                try:
                    subject_id = int(subject_id_str)
                    correct = sum(1 for v in answers_dict.values() if v is True)
                    subject_scores[subject_id] = {
                        'score': correct
                        # (Остальные данные можно добавить при необходимости)
                    }
                except (ValueError, TypeError):
                    continue

        students_data.append({
            'student': result.student,
            'result': result,
            'total_score': result.total_score,
            'subject_scores': subject_scores,
            'position': 0
        })

    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    for idx, student_data in enumerate(students_data, 1):
        student_data['position'] = idx

    return students_data, table_header

# --- Основные Views ---

@login_required
def class_results_dashboard_view(request, quarter_id, class_id):
    """
    Отчет по классу с фильтром GAT-номера
    и правильной фильтрацией заголовков.
    """
    school_class = get_object_or_404(SchoolClass, id=class_id)
    quarter = get_object_or_404(Quarter, id=quarter_id)

    try:
        gat_number = int(request.GET.get('gat_number', 1))
    except ValueError:
        gat_number = 1

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if not accessible_schools.filter(id=school_class.school.id).exists():
            messages.error(request, "У вас нет доступа к отчетам этого класса.")
            return redirect('core:results_archive')

    parent_class = school_class.parent if school_class.parent else school_class

    # Ищем тесты по ДНЯМ (day=1, day=2)
    test_day1 = GatTest.objects.filter(
        school_class=parent_class,
        quarter=quarter,
        test_number=gat_number,
        day=1
    ).prefetch_related('questions__subject').first() # Используем prefetch для subjects

    test_day2 = GatTest.objects.filter(
        school_class=parent_class,
        quarter=quarter,
        test_number=gat_number,
        day=2
    ).prefetch_related('questions__subject').first()

    # Получаем данные, используя _get_data_for_test, которая ТЕПЕРЬ
    # правильно фильтрует заголовки таблицы.
    all_students_data_day1, table_header_day1 = _get_data_for_test(test_day1)
    all_students_data_day2, table_header_day2 = _get_data_for_test(test_day2)

    # (Фильтруем данные по студентам текущего класса)
    students_data_day1 = [
        data for data in all_students_data_day1
        if data['student'].school_class == school_class
    ]
    students_data_day2 = [
        data for data in all_students_data_day2
        if data['student'].school_class == school_class
    ]

    # (Собираем карту для итогового рейтинга)
    all_students_map = {}
    for data in students_data_day1:
        student = data['student']
        if student.id not in all_students_map:
            all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score1'] = data['total_score']
        all_students_map[student.id]['result1'] = data.get('result')
    for data in students_data_day2:
        student = data['student']
        if student.id not in all_students_map:
            all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score2'] = data['total_score']
        all_students_map[student.id]['result2'] = data.get('result')

    # (Собираем итоговые данные)
    students_data_total = []
    for data in all_students_map.values():
        score1, score2 = data.get('score1'), data.get('score2')
        total_score = (score1 or 0) + (score2 or 0) if score1 is not None or score2 is not None else None
        progress = score2 - score1 if score1 is not None and score2 is not None else None

        students_data_total.append({
            'student': data['student'], 'score1': score1, 'score2': score2,
            'total_score': total_score, 'progress': progress, 'result1': data.get('result1'),
            'result2': data.get('result2'), 'display_class': data['student'].school_class.name
        })
    students_data_total.sort(key=lambda x: (x['total_score'] is None, -x['total_score'] if x['total_score'] is not None else 0))

    # (Статистика)
    total_students = len(students_data_total)
    participated_both = len([s for s in students_data_total if s['score1'] is not None and s['score2'] is not None])
    avg_score1_list = [s['score1'] for s in students_data_total if s['score1'] is not None]
    avg_score2_list = [s['score2'] for s in students_data_total if s['score2'] is not None]
    avg_score1 = sum(avg_score1_list) / len(avg_score1_list) if avg_score1_list else 0
    avg_score2 = sum(avg_score2_list) / len(avg_score2_list) if avg_score2_list else 0

    context = {
        'title': f'Отчет класса: {school_class.name}',
        'school_class': school_class,
        'quarter': quarter,
        'students_data_total': students_data_total,
        'students_data_gat1': students_data_day1,
        'table_header_gat1': table_header_day1,
        'students_data_gat2': students_data_day2,
        'table_header_gat2': table_header_day2,
        'test_day1': test_day1,
        'test_day2': test_day2,
        'gat_number_choices': GatTest.TEST_NUMBER_CHOICES,
        'selected_gat_number': gat_number,
        'stats': {
            'total_students': total_students, 'participated_both': participated_both,
            'avg_score1': round(avg_score1, 1), 'avg_score2': round(avg_score2, 1),
            'avg_progress': round(avg_score2 - avg_score1, 1)
        }
    }
    return render(request, 'results/class_results_dashboard.html', context)


@login_required
def compare_class_tests_view(request, test1_id, test2_id):
    """Сравнение двух тестов с улучшенной логикой ранжирования"""
    test1 = get_object_or_404(GatTest, id=test1_id)
    test2 = get_object_or_404(GatTest, id=test2_id)

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if (test1.school not in accessible_schools or
            test2.school not in accessible_schools):
            messages.error(request, "У вас нет доступа для сравнения этих тестов.")
            return redirect('core:dashboard')

    student_ids_test1 = StudentResult.objects.filter(gat_test=test1).values_list('student_id', flat=True)
    student_ids_test2 = StudentResult.objects.filter(gat_test=test2).values_list('student_id', flat=True)
    all_student_ids = set(student_ids_test1) | set(student_ids_test2)

    all_students = Student.objects.filter(id__in=all_student_ids).select_related('school_class__school').order_by('last_name_ru', 'first_name_ru')

    results1_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test1)}
    results2_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test2)}

    # Используем total_score, который уже посчитан
    full_scores1 = [{'student': student, 'score': results1_map[student.id].total_score, 'present': True} for student in all_students if student.id in results1_map]
    full_scores2 = [{'student': student, 'score': results2_map[student.id].total_score, 'present': True} for student in all_students if student.id in results2_map]
    
    sorted_scores1 = sorted(full_scores1, key=lambda x: x['score'], reverse=True)
    sorted_scores2 = sorted(full_scores2, key=lambda x: x['score'], reverse=True)

    rank_map1 = {item['student'].id: rank + 1 for rank, item in enumerate(sorted_scores1)}
    rank_map2 = {item['student'].id: rank + 1 for rank, item in enumerate(sorted_scores2)}

    comparison_results = []
    for student in all_students:
        is_present1 = student.id in results1_map
        is_present2 = student.id in results2_map

        rank1 = rank_map1.get(student.id)
        rank2 = rank_map2.get(student.id)
        score1 = results1_map[student.id].total_score if is_present1 else None
        score2 = results2_map[student.id].total_score if is_present2 else None

        avg_rank = (rank1 + rank2) / 2 if is_present1 and is_present2 else float('inf')
        progress = score2 - score1 if is_present1 and is_present2 else None

        comparison_results.append({
            'student': student,
            'score1': score1 if is_present1 else '—',
            'score2': score2 if is_present2 else '—',
            'rank1': rank1 if is_present1 else '—',
            'rank2': rank2 if is_present2 else '—',
            'avg_rank': round(avg_rank, 1) if avg_rank != float('inf') else '—',
            'progress': progress,
            'participation': get_participation_type(is_present1, is_present2)
        })

    comparison_results.sort(key=lambda x: (
        x['avg_rank'] == '—',
        x['avg_rank'] if x['avg_rank'] != '—' else float('inf')
    ))

    students_data_1, table_header_1 = _get_data_for_test(test1)
    students_data_2, table_header_2 = _get_data_for_test(test2)

    context = {
        'results': comparison_results,
        'test1': test1,
        'test2': test2,
        'title': f'Сравнение тестов: {test1.school_class.name if test1.school_class else "класса"}',
        'students_data_1': students_data_1,
        'table_header_1': table_header_1,
        'students_data_2': students_data_2,
        'table_header_2': table_header_2,
    }
    return render(request, 'results/comparison_detail.html', context)

def get_participation_type(present1, present2):
    """Вспомогательная функция для определения типа участия"""
    if present1 and present2:
        return "Оба теста"
    elif present1:
        return "Только GAT-1"
    elif present2:
        return "Только GAT-2"
    else:
        return "Не участвовал"

@login_required
def combined_class_report_view(request, quarter_id, parent_class_id):
    """
    Формирует сводный отчет с вкладками для GAT-1 и GAT-2.
    """
    quarter = get_object_or_404(Quarter, id=quarter_id)
    parent_class = get_object_or_404(SchoolClass, id=parent_class_id)

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if parent_class.school not in accessible_schools:
            messages.error(request, "У вас нет доступа к этому отчету.")
            return redirect('core:results_archive')

    test_gat1 = GatTest.objects.filter(school_class=parent_class, quarter=quarter, test_number=1).first()
    test_gat2 = GatTest.objects.filter(school_class=parent_class, quarter=quarter, test_number=2).first()

    student_ids_in_parallel = set(Student.objects.filter(
        school_class__parent=parent_class
    ).values_list('id', flat=True))

    all_data_gat1, table_header_gat1 = _get_data_for_test(test_gat1)
    students_data_gat1 = [data for data in all_data_gat1 if data['student'].id in student_ids_in_parallel]

    all_data_gat2, table_header_gat2 = _get_data_for_test(test_gat2)
    students_data_gat2 = [data for data in all_data_gat2 if data['student'].id in student_ids_in_parallel]

    all_students_map = {}
    for data in students_data_gat1:
        student = data['student']
        all_students_map[student.id] = {'student': student, 'score1': data['total_score'], 'score2': None}

    for data in students_data_gat2:
        student = data['student']
        if student.id not in all_students_map:
            all_students_map[student.id] = {'student': student, 'score1': None}
        all_students_map[student.id]['score2'] = data['total_score']

    students_data_total = []
    for data in all_students_map.values():
        score1, score2 = data.get('score1'), data.get('score2')
        total_score = (score1 or 0) + (score2 or 0) if score1 is not None or score2 is not None else None
        progress = score2 - score1 if score1 is not None and score2 is not None else None

        students_data_total.append({
            'student': data['student'], 'score1': score1, 'score2': score2,
            'total_score': total_score, 'progress': progress
        })
    students_data_total.sort(key=lambda x: (x['total_score'] is None, -x['total_score'] if x['total_score'] is not None else 0))

    context = {
        'title': f'Общий рейтинг: {parent_class.name} классы',
        'parent_class': parent_class,
        'quarter': quarter,
        'students_data': students_data_total,
        'students_data_gat1': students_data_gat1,
        'table_header_gat1': table_header_gat1,
        'students_data_gat2': students_data_gat2,
        'table_header_gat2': table_header_gat2,
        'test_gat1': test_gat1,
        'test_gat2': test_gat2,
    }
    return render(request, 'results/combined_class_report.html', context)