# D:\New_GAT\core\views\reports.py (ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

import json
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db.models import Count, Q
from openpyxl import Workbook
from weasyprint import HTML
from django.core.cache import cache
from .permissions import get_accessible_schools
from accounts.models import UserProfile

from core.models import (
    AcademicYear, GatTest, Quarter, QuestionCount, School,
    SchoolClass, Student, StudentResult, Subject
)
from core.forms import UploadFileForm, StatisticsFilterForm
from core.views.permissions import get_accessible_schools, get_accessible_subjects
from core import services
from core import utils

# --- UPLOAD AND DETAILED RESULTS ---

@login_required
def upload_results_view(request):
    """Загрузка результатов тестов с фильтрацией по дате из файла"""
    if request.method == 'POST':
        # Сначала создаем форму без фильтрации
        form = UploadFileForm(request.POST, request.FILES)

        # Если есть файл, пытаемся извлечь дату
        test_date = None
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            test_date = services.extract_test_date_from_excel(uploaded_file)

            # Пересоздаем форму с фильтрацией по дате
            form = UploadFileForm(request.POST, request.FILES, test_date=test_date)

        if form.is_valid():
            gat_test = form.cleaned_data['gat_test']
            excel_file = request.FILES['file']

            try:
                success, report_data = services.process_student_results_upload(gat_test, excel_file)
                print(f"--- GAT UPLOAD REPORT: {report_data}")

                if success:
                    total = report_data.get('total_unique_students', 0)
                    errors = report_data.get('errors', [])

                    messages.success(
                        request,
                        f"Файл успешно обработан. Загружено результатов для {total} учеников."
                    )

                    for error in errors:
                        messages.error(request, error)

                    # --- ИСПРАВЛЕННЫЙ БЛОК ---
                    # Создаем базовый URL (например, /dashboard/results/gat/1/)
                    base_url = reverse(
                        'core:detailed_results_list',
                        kwargs={'test_number': gat_test.test_number}
                    )

                    # Добавляем ID теста как query-параметр
                    # (например, /dashboard/results/gat/1/?test_id=42)
                    redirect_url = f"{base_url}?test_id={gat_test.id}"

                    return redirect(redirect_url)
                    # --- КОНЕЦ ИСПРАВЛЕННОГО БЛОКА ---

                else:
                    messages.error(request, f"Ошибка обработки файла: {report_data}")

            except Exception as e:
                messages.error(
                    request,
                    f"Произошла критическая ошибка при обработке файла: {str(e)}"
                )
        else:
            messages.error(request, "Форма содержит ошибки. Проверьте введенные данные.")
    else:
        # GET запрос - создаем форму без фильтрации
        form = UploadFileForm()

    context = {
        'form': form,
        'title': 'Загрузка результатов GAT тестов'
    }
    return render(request, 'results/upload_form.html', context)

def get_detailed_results_data(test_number, request_get, request_user):
    """
    Готовит данные для детального рейтинга с улучшенной логикой фильтрации
    """
    year_id = request_get.get('year')
    quarter_id = request_get.get('quarter')
    school_id = request_get.get('school')
    class_id = request_get.get('class')

    test_id_from_upload = request_get.get('test_id')
    latest_test = None

    # --- (Весь этот блок поиска 'latest_test' У ВАС ПРАВИЛЬНЫЙ) ---
    if test_id_from_upload:
        try:
            specific_test = GatTest.objects.filter(
                pk=test_id_from_upload,
                test_number=test_number
            ).select_related('quarter__year', 'school_class').first()

            if specific_test:
                if not request_user.is_superuser:
                    accessible_schools = get_accessible_schools(request_user)
                    if specific_test.school not in accessible_schools:
                        return [], [], None
                latest_test = specific_test
        except (ValueError, GatTest.DoesNotExist):
            pass

    if not latest_test:
        tests_qs = GatTest.objects.filter(test_number=test_number).select_related(
            'quarter__year', 'school_class', 'school'
        )

        if not request_user.is_superuser:
            accessible_schools = get_accessible_schools(request_user)
            tests_qs = tests_qs.filter(school__in=accessible_schools)

        filters = Q()
        if year_id and year_id != '0':
            filters &= Q(quarter__year_id=year_id)
        if quarter_id and quarter_id != '0':
            filters &= Q(quarter_id=quarter_id)
        if school_id and school_id != '0':
            filters &= Q(school_id=school_id)
        if class_id and class_id != '0':
            filters &= Q(school_class_id=class_id)

        if filters:
            tests_qs = tests_qs.filter(filters)

        latest_test = tests_qs.order_by('-test_date').first()
    # --- (Конец блока поиска 'latest_test') ---

    if not latest_test:
        return [], [], None

    student_results = StudentResult.objects.filter(
        gat_test=latest_test
    ).select_related('student__school_class', 'gat_test')


    # --- ✨✨✨ НАЧАЛО ИСПРАВЛЕНИЯ ✨✨✨ ---
    table_header = []

    # 1. Проверяем, что тест существует и у него есть параллель
    if latest_test and latest_test.school_class:

        # 2. Получаем родительский класс (параллель), e.g., '5'
        parent_class = latest_test.school_class

        # 3. Получаем предметы ТОЛЬКО ИЗ САМОГО ТЕСТА (e.g., только 'ENGLISH')
        #    Это была главная ошибка.
        subjects_for_this_test = latest_test.subjects.all().order_by('name')

        # 4. Получаем ВСЕ QuestionCounts для этой параллели ОДНИМ запросом
        #    e.g., {'ENGLISH': 19, 'COMPUTER': 10}
        question_counts_map = {
            qc.subject_id: qc.number_of_questions
            for qc in QuestionCount.objects.filter(school_class=parent_class)
        }

        # 5. Cоздаем 'table_header' ТОЛЬКО для предметов из шага 3
        for subject in subjects_for_this_test:

            # 6. Берем кол-во вопросов из карты (map)
            q_count = question_counts_map.get(subject.id, 0) # 0, если не найдено

            table_header.append({
                'subject': subject,
                'questions': range(1, q_count + 1),
                'questions_count': q_count,
                'school_class': parent_class
            })
    # --- ✨✨✨ КОНЕЦ ИСПРАВЛЕНИЯ ✨✨✨ ---

    results_map = {res.student_id: res for res in student_results}

    # --- ИСПРАВЛЕНИЕ: Нужно брать ID студентов из `results_map`, а не делать новый запрос ---
    students = Student.objects.filter(
        id__in=results_map.keys()
    ).select_related('school_class', 'school_class__school')
    # (Сортировка убрана, т.к. мы будем сортировать students_data)

    students_data = []
    for student in students:
        result = results_map.get(student.id)
        # (Этот блок был у вас правильный)
        total_score = result.total_score if result else 0
        subject_scores = {}

        if result and isinstance(result.scores_by_subject, dict):
            for subject_id_str, answers in result.scores_by_subject.items():
                try:
                    subject_id = int(subject_id_str)
                    if isinstance(answers, list):
                        subject_scores[subject_id] = {
                            'score': sum(answers),
                            'total_questions': len(answers),
                            'correct_answers': sum(answers)
                        }
                except (ValueError, TypeError):
                    continue

        students_data.append({
            'student': student,
            'result': result,
            'total_score': total_score,
            'subject_scores': subject_scores,
            'position': 0
        })

    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    for idx, student_data in enumerate(students_data, 1):
        student_data['position'] = idx

    return students_data, table_header, latest_test

@login_required
def detailed_results_list_view(request, test_number):

    # 1. Получаем данные, как и раньше.
    # Мы "переименовали" old_header, чтобы показать, что мы его не используем.
    students_data, _ignored_header, latest_test = get_detailed_results_data(
        test_number, request.GET, request.user
    )

    # --- НАЧАЛО ИСПРАВЛЕНИЯ ---
    # 2. Создаем НОВЫЙ, правильный table_header
    table_header = []

    # 3. Убедимся, что у нас есть тест, с которым можно работать
    if latest_test:
        # 4. Получаем предметы ТОЛЬКО из этого конкретного теста
        subjects_for_this_test = latest_test.subjects.all().order_by('name')

        # 5. Находим родительский класс (параллель), к которому привязан тест
        parent_class = latest_test.school_class
        if parent_class and parent_class.parent:
            parent_class = parent_class.parent # e.g., get '10' from '10A'

        # 6. Создаем заголовки только для этих предметов
        for subject in subjects_for_this_test:
            q_count = 0
            if parent_class:
                try:
                    # Ищем кол-во вопросов для этой ПАРАЛЛЕЛИ и предмета
                    q_count = QuestionCount.objects.get(
                        school_class=parent_class,
                        subject=subject
                    ).number_of_questions
                except QuestionCount.DoesNotExist:
                    q_count = 0 # (Безопасность) Если не найдено, будет 0

            table_header.append({
                'subject': subject,
                'questions': range(1, q_count + 1) # e.g., [1, 2, 3... 10]
            })
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    accessible_schools = get_accessible_schools(request.user) if not request.user.is_superuser else School.objects.all()

    context = {
        'title': f'Детальный рейтинг GAT-{test_number}',
        'students_data': students_data,
        'table_header': table_header, # <-- 7. Используем наш НОВЫЙ 'table_header'
        'years': AcademicYear.objects.all().order_by('-start_date'),
        'schools': accessible_schools,
        'classes': SchoolClass.objects.filter(parent__isnull=True).order_by('name'), # Показываем только параллели
        'selected_year': request.GET.get('year'),
        'selected_quarter': request.GET.get('quarter'),
        'selected_school': request.GET.get('school'),
        'selected_class': request.GET.get('class'),
        'test_number': test_number,
        'test': latest_test,
        'total_students': len(students_data),
        'max_score': max([s['total_score'] for s in students_data]) if students_data else 0
    }
    return render(request, 'results/detailed_results_list.html', context)

@login_required
def student_result_detail_view(request, pk):
    result = get_object_or_404(
        StudentResult.objects.select_related(
            'student__school_class__school',
            'gat_test__quarter__year'
        ),
        pk=pk
    )

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if result.student.school_class.school not in accessible_schools:
            messages.error(request, "У вас нет доступа к этому результату.")
            return redirect('core:dashboard')

    subject_map = {s.id: s for s in Subject.objects.all()}
    processed_scores = {}
    total_correct = 0
    total_questions = 0

    if isinstance(result.scores_by_subject, dict):
        for subject_id_str, answers in result.scores_by_subject.items():
            try:
                subject_id = int(subject_id_str)
                subject = subject_map.get(subject_id)
                if subject and isinstance(answers, list):
                    total = len(answers)
                    correct = sum(answers)
                    processed_scores[subject.name] = {
                        'answers': answers, 'total': total, 'correct': correct,
                        'incorrect': total - correct, 'percentage': round((correct / total) * 100, 1) if total > 0 else 0,
                        'subject': subject
                    }
                    total_correct += correct
                    total_questions += total
            except (ValueError, TypeError):
                continue

    overall_percentage = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0

    context = {
        'result': result, 'processed_scores': processed_scores, 'title': f'Детальный отчет: {result.student}',
        'total_correct': total_correct, 'total_questions': total_questions, 'overall_percentage': overall_percentage
    }
    return render(request, 'results/student_result_detail.html', context)

@login_required
def student_result_delete_view(request, pk):
    result = get_object_or_404(StudentResult, pk=pk)
    test_number = result.gat_test.test_number

    if request.method == 'POST':
        student_name = str(result.student)
        test_info = f"GAT-{test_number}"
        try:
            result.delete()
            messages.success(request, f'Результат для "{student_name}" (тест {test_info}) был успешно удален.')
            return redirect('core:detailed_results_list', test_number=test_number)
        except Exception as e:
            messages.error(request, f'Ошибка при удалении результата: {str(e)}')
            return redirect('core:student_result_detail', pk=pk)

    context = {
        'item': result, 'title': f'Удалить результат: {result.student}',
        'cancel_url': reverse('core:student_result_detail', kwargs={'pk': pk}),
        'test_number': test_number
    }
    return render(request, 'results/confirm_delete_result.html', context)

# --- ARCHIVE AND COMPARISON ---

@login_required
def archive_years_view(request):
    """Архив по годам с улучшенной и исправленной статистикой"""
    user = request.user
    accessible_schools = get_accessible_schools(user)

    # Находим только те учебные годы, в которых есть результаты тестов,
    # к которым у пользователя есть доступ.
    results_qs = StudentResult.objects.filter(
        student__school_class__school__in=accessible_schools
    )
    year_ids_with_results = results_qs.values_list('gat_test__quarter__year_id', flat=True).distinct()

    # С помощью annotate() подсчитываем статистику прямо в базе данных.
    # Это быстро и надежно.
    years = AcademicYear.objects.filter(
        id__in=year_ids_with_results
    ).annotate(
        # Считаем количество уникальных тестов, у которых есть результаты
        test_count=Count(
            'quarters__gat_tests',
            filter=Q(
                quarters__gat_tests__results__isnull=False,
                quarters__gat_tests__school__in=accessible_schools
            ),
            distinct=True
        ),
        # Считаем количество уникальных студентов, у которых есть результаты
        student_count=Count(
            'quarters__gat_tests__results__student',
            filter=Q(
                quarters__gat_tests__school__in=accessible_schools
            ),
            distinct=True
        )
    ).order_by('-start_date')

    context = {
        'years': years,  # Теперь передаем сразу queryset years
        'title': 'Архив результатов по годам'
    }
    return render(request, 'results/archive_years.html', context)

@login_required
def archive_quarters_view(request, year_id):
    """Архив по четвертям с исправленной статистикой"""
    year = get_object_or_404(AcademicYear, id=year_id)
    user = request.user
    accessible_schools = get_accessible_schools(user)

    # Используем annotate для эффективного подсчета статистики
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
        'quarters': quarters, # Передаем сразу queryset quarters
        'title': f'Архив: {year.name}'
    }
    return render(request, 'results/archive_quarters.html', context)

@login_required
def archive_schools_view(request, quarter_id):
    """Архив по школам с исправленной статистикой"""
    quarter = get_object_or_404(Quarter, id=quarter_id)
    user = request.user
    accessible_schools = get_accessible_schools(user)

    # Используем annotate для подсчета классов и учеников
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
        'schools': schools, # Передаем сразу queryset schools
        'title': f'Архив: {quarter}'
    }
    return render(request, 'results/archive_schools.html', context)

@login_required
def archive_classes_view(request, quarter_id, school_id):
    """
    ИЗМЕНЕННАЯ ВЕРСИЯ: Отображает родительские классы (параллели),
    в которых есть результаты за выбранную четверть.
    """
    quarter = get_object_or_404(Quarter, id=quarter_id)
    school = get_object_or_404(School, id=school_id)

    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if school not in accessible_schools:
            messages.error(request, "У вас нет доступа к архиву этой школы.")
            return redirect('core:results_archive')

    # Находим ID родительских классов, у которых есть дочерние классы с результатами
    parent_class_ids = SchoolClass.objects.filter(
        school=school,
        students__results__gat_test__quarter=quarter,
        parent__isnull=False
    ).values_list('parent_id', flat=True).distinct()

    # Получаем сами объекты родительских классов
    parent_classes = SchoolClass.objects.filter(id__in=parent_class_ids).order_by('name')

    context = {
        'quarter': quarter,
        'school': school,
        'parent_classes': parent_classes, # Передаем родительские классы
        'title': f'Архив: {school.name} (Выберите параллель)'
    }
    return render(request, 'results/archive_classes.html', context)

def _get_data_for_test(gat_test):
    if not gat_test:
        return [], []

    table_header = []

    if gat_test.school_class:
        school_class = gat_test.school_class
        question_counts = QuestionCount.objects.filter(
            school_class=school_class
        ).select_related('subject').order_by('subject__name')

        for qc in question_counts:
            table_header.append({
                'subject': qc.subject,
                'questions': range(1, qc.number_of_questions + 1),
                'questions_count': qc.number_of_questions,
                'school_class': school_class
            })

    student_results = StudentResult.objects.filter(
        gat_test=gat_test
    ).select_related('student__school_class__school')

    students_data = []
    for result in student_results:
        students_data.append({
            'student': result.student,
            'result': result,
            'total_score': result.total_score,
            'subject_scores': {}, # Заполняется по необходимости
            'position': 0
        })

    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    for idx, student_data in enumerate(students_data, 1):
        student_data['position'] = idx

    return students_data, table_header

@login_required
def class_results_dashboard_view(request, quarter_id, class_id):
    """
    ИСПРАВЛЕННАЯ ВЕРСИЯ: Добавлен фильтр GAT-номера (gat_number)
    и фильтрация заголовков таблицы по предметам теста.
    """
    school_class = get_object_or_404(SchoolClass, id=class_id)
    quarter = get_object_or_404(Quarter, id=quarter_id)

    # --- Получаем номер GAT из GET-параметра, по умолчанию 1 ---
    try:
        gat_number = int(request.GET.get('gat_number', 1))
    except ValueError:
        gat_number = 1

    # --- Проверка доступа ---
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if not accessible_schools.filter(id=school_class.school.id).exists():
            messages.error(request, "У вас нет доступа к отчетам этого класса.")
            return redirect('core:results_archive')

    # --- Ищем тест по родительскому классу (параллели) ---
    parent_class = school_class.parent if school_class.parent else school_class

    # --- Ищем тесты по ДНЯМ (day=1, day=2) ---
    # Добавляем prefetch_related('subjects') для оптимизации
    test_day1 = GatTest.objects.filter(
        school_class=parent_class,
        quarter=quarter,
        test_number=gat_number,
        day=1
    ).prefetch_related('subjects').first()

    test_day2 = GatTest.objects.filter(
        school_class=parent_class,
        quarter=quarter,
        test_number=gat_number,
        day=2
    ).prefetch_related('subjects').first()

    # (Получаем общие данные по тестам)
    # Переименовываем исходные заголовки, чтобы не перезаписать их
    all_students_data_day1, initial_table_header_day1 = _get_data_for_test(test_day1)
    all_students_data_day2, initial_table_header_day2 = _get_data_for_test(test_day2)

    # --- ✨ БЛОК ФИЛЬТРАЦИИ ЗАГОЛОВКОВ ✨ ---
    table_header_day1 = []
    if test_day1:
        # Получаем ID предметов ТОЛЬКО из теста Дня 1
        day1_subject_ids = set(test_day1.subjects.values_list('id', flat=True))
        # Оставляем в заголовке только те предметы, которые есть в day1_subject_ids
        table_header_day1 = [
            header_item for header_item in initial_table_header_day1 # Используем initial_...
            if header_item['subject'].id in day1_subject_ids
        ]

    table_header_day2 = []
    if test_day2:
        # Аналогично для Дня 2
        day2_subject_ids = set(test_day2.subjects.values_list('id', flat=True))
        table_header_day2 = [
            header_item for header_item in initial_table_header_day2 # Используем initial_...
            if header_item['subject'].id in day2_subject_ids
        ]
    # --- ✨ КОНЕЦ БЛОКА ---

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
        'table_header_gat1': table_header_day1, # <-- Передаем отфильтрованный заголовок
        'students_data_gat2': students_data_day2,
        'table_header_gat2': table_header_day2, # <-- Передаем отфильтрованный заголовок
        'test_day1': test_day1,
        'test_day2': test_day2,

        # --- Передаем данные для фильтра в шаблон ---
        'gat_number_choices': GatTest.TEST_NUMBER_CHOICES, # [(1, 'GAT-1'), (2, 'GAT-2'), ...]
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

    # Проверка прав доступа
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        if (test1.school not in accessible_schools or
            test2.school not in accessible_schools):
            messages.error(request, "У вас нет доступа для сравнения этих тестов.")
            return redirect('core:dashboard')

    # Получение всех студентов, участвовавших в тестах
    student_ids_test1 = StudentResult.objects.filter(
        gat_test=test1
    ).values_list('student_id', flat=True)

    student_ids_test2 = StudentResult.objects.filter(
        gat_test=test2
    ).values_list('student_id', flat=True)

    all_student_ids = set(student_ids_test1) | set(student_ids_test2)

    all_students = Student.objects.filter(
        id__in=all_student_ids
    ).select_related('school_class__school').order_by('last_name_ru', 'first_name_ru')

    results1_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test1)}
    results2_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test2)}

    # Подсчет баллов и ранжирование для GAT-1
    full_scores1 = []
    for student in all_students:
        score = 0
        if student.id in results1_map:
            result = results1_map[student.id]
            if isinstance(result.scores_by_subject, dict):
                for answers in result.scores_by_subject.values():
                    if isinstance(answers, list):
                        score += sum(answers)
        full_scores1.append({
            'student': student,
            'score': score,
            'present': student.id in results1_map
        })

    # Подсчет баллов и ранжирование для GAT-2
    full_scores2 = []
    for student in all_students:
        score = 0
        if student.id in results2_map:
            result = results2_map[student.id]
            if isinstance(result.scores_by_subject, dict):
                for answers in result.scores_by_subject.values():
                    if isinstance(answers, list):
                        score += sum(answers)
        full_scores2.append({
            'student': student,
            'score': score,
            'present': student.id in results2_map
        })

    # Ранжирование студентов по каждому тесту
    sorted_scores1 = sorted(
        [s for s in full_scores1 if s['present']],
        key=lambda x: x['score'],
        reverse=True
    )
    sorted_scores2 = sorted(
        [s for s in full_scores2 if s['present']],
        key=lambda x: x['score'],
        reverse=True
    )

    # Создание карт рангов
    rank_map1 = {item['student'].id: rank + 1 for rank, item in enumerate(sorted_scores1)}
    rank_map2 = {item['student'].id: rank + 1 for rank, item in enumerate(sorted_scores2)}

    # Сравнение результатов
    comparison_results = []
    for student in all_students:
        is_present1 = student.id in results1_map
        is_present2 = student.id in results2_map

        rank1 = rank_map1.get(student.id)
        rank2 = rank_map2.get(student.id)
        score1 = next((s['score'] for s in full_scores1 if s['student'].id == student.id), None)
        score2 = next((s['score'] for s in full_scores2 if s['student'].id == student.id), None)

        # Расчет среднего ранга и прогресса
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

    # Сортировка по среднему рангу
    comparison_results.sort(key=lambda x: (
        x['avg_rank'] == '—',
        x['avg_rank'] if x['avg_rank'] != '—' else float('inf')
    ))

    # Получение детальных данных для вкладок
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

# --- MAIN REPORTING VIEWS ---

@login_required
def analysis_view(request):
    """
    Анализ успеваемости с использованием фильтров как в 'Статистике'
    и учетом прав доступа Эксперта.
    """
    user = request.user
    profile = getattr(user, 'profile', None)
    # Используем форму StatisticsFilterForm, как было в твоем коде
    form = StatisticsFilterForm(request.GET or None, user=user)

    # --- Инициализация строковых ID из GET (для начальной отрисовки и JS) ---
    selected_quarter_ids_str = request.GET.getlist('quarters')
    selected_school_ids_str = request.GET.getlist('schools')
    selected_class_ids_str = request.GET.getlist('school_classes')
    selected_subject_ids_str = request.GET.getlist('subjects')
    final_grouped_classes = {}    # Для отображения групп классов в фильтре

    # --- Получение данных из GET и группировка классов (если форма была отправлена) ---
    if request.GET:
        # --- Логика группировки классов (остается без изменений) ---
        grouped_classes = defaultdict(list)
        if selected_school_ids_str:
            try:
                school_ids_int = [int(sid) for sid in selected_school_ids_str]
                classes_qs = SchoolClass.objects.filter(
                    school_id__in=school_ids_int
                ).select_related('parent', 'school').order_by('school__name', 'name')

                is_multiple_schools = len(school_ids_int) > 1
                for cls in classes_qs:
                    group_name = f"{cls.parent.name} классы" if cls.parent else f"{cls.name} классы (Параллель)"
                    if is_multiple_schools:
                        group_name = f"{cls.school.name} - {group_name}"
                    grouped_classes[group_name].append(cls)

                sorted_group_items = sorted(
                    grouped_classes.items(),
                    key=lambda item: (not item[0].endswith("(Параллель)"), item[0])
                )
                for group_name, classes_in_group in sorted_group_items:
                    classes_in_group.sort(key=lambda x: x.name)
                    final_grouped_classes[group_name] = classes_in_group
            except ValueError:
                messages.error(request, "Некорректный ID школы в параметрах.")
                pass
        # --- Конец группировки ---

    # --- Инициализация контекста ---
    context = {
        'title': 'Анализ успеваемости',
        'form': form,
        'has_results': False, # По умолчанию результатов нет
        'grouped_classes': final_grouped_classes,
        'selected_quarter_ids': selected_quarter_ids_str,
        'selected_school_ids': selected_school_ids_str,
        'selected_class_ids': selected_class_ids_str,
        'selected_subject_ids': selected_subject_ids_str, # Строки для рендера фильтра
        # Инициализация переменных для данных (на случай отсутствия результатов)
        'table_headers': [],
        'table_data': {},
        'subject_averages': {},
        'subject_ranks': {},
        'chart_labels': '[]',
        'chart_datasets': '[]',
        # Передаем JSON ID для JavaScript
        'selected_class_ids_json': json.dumps(selected_class_ids_str),
        'selected_subject_ids_json': json.dumps(selected_subject_ids_str),
    }

    # --- Обработка валидной формы и расчет результатов ---
    if form.is_valid():
        # Получаем QuerySets из cleaned_data формы
        selected_quarters = form.cleaned_data['quarters']
        selected_schools = form.cleaned_data['schools'] # Уже отфильтрованы по доступным
        selected_classes_qs = form.cleaned_data['school_classes']
        selected_test_numbers = form.cleaned_data['test_numbers']
        selected_days = form.cleaned_data['days']
        selected_subjects_qs = form.cleaned_data['subjects'] # Предметы, выбранные в форме

        # --- Логика определения ID классов (включая дочерние для параллелей) ---
        selected_class_ids_list_int = list(selected_classes_qs.values_list('id', flat=True))
        parent_class_ids_int = selected_classes_qs.filter(parent__isnull=True).values_list('id', flat=True)
        if parent_class_ids_int:
            child_class_ids_int = list(SchoolClass.objects.filter(parent_id__in=parent_class_ids_int).values_list('id', flat=True))
            selected_class_ids_list_int.extend(child_class_ids_int)
        final_class_ids_int = set(selected_class_ids_list_int)

        # --- Базовый QuerySet с фильтром по доступным школам ---
        accessible_schools = get_accessible_schools(user)
        results_qs = StudentResult.objects.filter(
            student__school_class__school__in=accessible_schools
        ).select_related('student__school_class', 'gat_test__quarter__year')

        # --- Применение фильтров из формы (кроме предметов) ---
        if selected_quarters: results_qs = results_qs.filter(gat_test__quarter__in=selected_quarters)
        if selected_schools: results_qs = results_qs.filter(student__school_class__school__in=selected_schools)
        if final_class_ids_int: results_qs = results_qs.filter(student__school_class_id__in=final_class_ids_int)
        if selected_test_numbers: results_qs = results_qs.filter(gat_test__test_number__in=selected_test_numbers)
        if selected_days: results_qs = results_qs.filter(gat_test__day__in=selected_days)

        # --- Фильтрация по ПРЕДМЕТАМ с учетом роли ЭКСПЕРТА ---
        accessible_subjects_qs = Subject.objects.none() # Итоговый набор предметов для анализа
        is_expert = profile and profile.role == UserProfile.Role.EXPERT
        expert_subject_ids_int = set()

        if is_expert:
            expert_subjects = profile.subjects.all()
            expert_subject_ids_int = set(expert_subjects.values_list('id', flat=True))

            if selected_subjects_qs.exists():
                accessible_subjects_qs = selected_subjects_qs.filter(id__in=expert_subject_ids_int)
            elif expert_subjects.exists():
                accessible_subjects_qs = expert_subjects
            # Если у Эксперта нет предметов И в форме не выбраны - results_qs нужно обнулить
            elif not accessible_subjects_qs.exists():
                 results_qs = results_qs.none() # Обнуляем

        # Если пользователь НЕ Эксперт, используем предметы, выбранные в форме
        else:
            accessible_subjects_qs = selected_subjects_qs

        # --- Фильтруем основной results_qs по ИТОГОВЫМ предметам ---
        if results_qs.exists(): # Проверяем, не обнулили ли мы queryset выше
            if accessible_subjects_qs.exists():
                subject_id_keys_to_filter = [str(s.id) for s in accessible_subjects_qs]
                results_qs = results_qs.filter(scores_by_subject__has_any_keys=subject_id_keys_to_filter)
            # Если accessible_subjects_qs пуст (для Эксперта), то обнуляем results_qs
            elif is_expert:
                 results_qs = results_qs.none()
            # Если это Директор/Админ и accessible_subjects_qs пуст (в форме не выбраны предметы),
            # то results_qs НЕ обнуляется - показываем все предметы.
            # В этом случае нужно определить предметы по результатам ниже.

        # --- Определение предметов для анализа, если они не были заданы (для Директора/Админа) ---
        if not accessible_subjects_qs.exists() and not is_expert and results_qs.exists():
             all_subject_ids_in_results = set()
             for r in results_qs:
                 if isinstance(r.scores_by_subject, dict):
                     all_subject_ids_in_results.update(int(sid) for sid in r.scores_by_subject.keys())
             accessible_subjects_qs = Subject.objects.filter(id__in=all_subject_ids_in_results)


        # --- Основная логика анализа (агрегация данных) ---
        if results_qs.exists() and accessible_subjects_qs.exists():
            # Используем accessible_subjects_qs для subject_map и дальнейших расчетов
            subject_map = {s.id: s.name for s in accessible_subjects_qs}
            allowed_subject_ids_int = set(subject_map.keys()) # ID разрешенных предметов
            agg_data = defaultdict(lambda: defaultdict(lambda: {'correct': 0, 'total': 0}))

            # Оптимизация: предзагрузка классов
            results_qs = results_qs.prefetch_related('student__school_class')

            for result in results_qs:
                class_name = result.student.school_class.name
                if isinstance(result.scores_by_subject, dict):
                    for subject_id_str, answers in result.scores_by_subject.items():
                        try:
                            subject_id = int(subject_id_str)
                            # Проверяем, входит ли предмет в разрешенные
                            if subject_id in allowed_subject_ids_int:
                                subject_name = subject_map.get(subject_id)

                                # --- ✨ FIX: Correctly process the dictionary of answers ---
                                # The 'answers' variable is a dictionary like {'1': True, '2': False}, not a list.
                                if subject_name and isinstance(answers, dict):
                                    correct_answers = sum(1 for answer in answers.values() if answer is True)
                                    total_questions = len(answers)
                                    agg_data[class_name][subject_name]['correct'] += correct_answers
                                    agg_data[class_name][subject_name]['total'] += total_questions
                                # --- ✨ END FIX ---

                        except (ValueError, TypeError):
                            continue # Пропускаем некорректные данные

            # --- Обработка агрегированных данных для таблицы и графика ---
            table_data = defaultdict(dict)
            # all_subjects теперь берутся из accessible_subjects_qs
            all_subjects = set(accessible_subjects_qs.values_list('name', flat=True))
            all_classes = sorted(agg_data.keys()) # Классы, по которым есть данные

            for class_name, subjects_data in agg_data.items():
                for subject_name, scores in subjects_data.items():
                    if scores['total'] > 0:
                        percentage = round((scores['correct'] / scores['total']) * 100, 1)
                        table_data[subject_name][class_name] = percentage

            subject_averages = {}
            for subject_name in all_subjects: # Итерируемся по разрешенным
                scores = [score for class_name in all_classes if (score := table_data.get(subject_name, {}).get(class_name)) is not None]
                if scores:
                    subject_averages[subject_name] = round(sum(scores) / len(scores), 1)

            # Сортировка и ранжирование предметов (только разрешенных)
            sorted_subjects_by_avg = sorted(subject_averages.items(), key=lambda item: item[1], reverse=True)
            subject_ranks = { name: rank + 1 for rank, (name, avg) in enumerate(sorted_subjects_by_avg) }
            # Сортируем РАЗРЕШЕННЫЕ предметы по названию для осей
            sorted_subjects_list = sorted(list(all_subjects))

            # Данные для графика (только разрешенные предметы)
            chart_datasets = [{
                'label': class_name,
                'data': [table_data.get(subject_name, {}).get(class_name, 0) for subject_name in sorted_subjects_list]
            } for class_name in all_classes]

            # Данные для таблицы (только разрешенные предметы)
            sorted_table_data = {subject: table_data.get(subject, {}) for subject in sorted_subjects_list}

            # --- Обновление контекста результатами ---
            context.update({
                'has_results': True,
                'table_headers': all_classes,          # Заголовки таблицы (классы)
                'table_data': sorted_table_data,       # Данные таблицы {Предмет: {Класс: %}}
                'subject_averages': subject_averages,  # Средние по разрешенным предметам
                'subject_ranks': subject_ranks,        # Ранги разрешенных предметов
                'chart_labels': json.dumps(sorted_subjects_list, ensure_ascii=False), # Разрешенные предметы для графика
                'chart_datasets': json.dumps(chart_datasets, ensure_ascii=False),     # Данные для графика
            })
            # Если results_qs пустой или accessible_subjects_qs пуст, has_results останется False

    # --- Передача JSON-безопасных списков ID в JavaScript ---
    # Эти переменные содержат строки из GET-запроса
    context['selected_class_ids_json'] = json.dumps(selected_class_ids_str)
    context['selected_subject_ids_json'] = json.dumps(selected_subject_ids_str)

    return render(request, 'analysis.html', context)

# --- EXPORT FUNCTIONS ---

@login_required
def export_detailed_results_excel(request, test_number):
    """Экспорт результатов в Excel с улучшенным форматированием"""
    students_data, table_header, test_info = get_detailed_results_data(
        test_number, request.GET, request.user
    )

    if not students_data:
        messages.warning(request, "Нет данных для экспорта.")
        return redirect('core:detailed_results_list', test_number=test_number)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheet.sheet'
    )
    filename = f"GAT-{test_number}_results_{test_info.test_date if test_info else ''}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f'GAT-{test_number} Результаты'

    # Заголовки таблицы
    headers = ["№", "ID", "ФИО Студента", "Класс", "Школа"]
    for header in table_header:
        subject_name = header['subject'].abbreviation or header['subject'].name[:3].upper()
        for i in range(1, header['questions_count'] + 1):
            headers.append(f"{subject_name}_{i}")
    headers.extend(["Общий балл", "Позиция в рейтинге"])

    sheet.append(headers)

    # Данные студентов
    for idx, data in enumerate(students_data, 1):
        row = [
            idx,
            data['student'].student_id,
            str(data['student']),
            data['student'].school_class.name,
            data['student'].school_class.school.name
        ]

        result = data.get('result')
        if result and isinstance(result.scores_by_subject, dict):
            for header in table_header:
                subject_id = str(header['subject'].id)
                answers = result.scores_by_subject.get(subject_id, [])
                row.extend(answers)
                # Заполняем пустые ячейки, если ответов меньше вопросов
                if len(answers) < header['questions_count']:
                    row.extend([''] * (header['questions_count'] - len(answers)))
        else:
            # Если результатов нет, добавляем пустые ячейки
            for header in table_header:
                row.extend([''] * header['questions_count'])

        row.extend([data['total_score'], data['position']])
        sheet.append(row)

    workbook.save(response)
    return response

@login_required
def export_detailed_results_pdf(request, test_number):
    """Экспорт результатов в PDF с улучшенным оформлением"""
    students_data, table_header, test_info = get_detailed_results_data(
        test_number, request.GET, request.user
    )

    if not students_data:
        messages.warning(request, "Нет данных для экспорта.")
        return redirect('core:detailed_results_list', test_number=test_number)

    context = {
        'title': f'Детальный рейтинг GAT-{test_number}',
        'students_data': students_data,
        'table_header': table_header,
        'test_info': test_info,
        'export_date': utils.get_current_date(),
        'total_students': len(students_data)
    }

    html_string = render_to_string('results/detailed_results_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    filename = f"GAT-{test_number}_results_{test_info.test_date if test_info else ''}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    try:
        HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
        return response
    except Exception as e:
        messages.error(request, f"Ошибка при создании PDF: {str(e)}")
        return redirect('core:detailed_results_list', test_number=test_number)

@login_required
def archive_subclasses_view(request, quarter_pk, school_pk, class_pk):
    """
    НОВЫЙ VIEW: Отображает подклассы (5А, 5Б) для выбранной параллели
    и карточку для общего отчета.
    """
    # Используем новые имена аргументов
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


@login_required
def combined_class_report_view(request, quarter_id, parent_class_id):
    """
    ОБНОВЛЕННАЯ ВЕРСИЯ: Формирует сводный отчет с вкладками для GAT-1 и GAT-2.
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

    # --- Получаем данные для вкладок GAT-1 и GAT-2 ---
    all_data_gat1, table_header_gat1 = _get_data_for_test(test_gat1)
    students_data_gat1 = [data for data in all_data_gat1 if data['student'].id in student_ids_in_parallel]

    all_data_gat2, table_header_gat2 = _get_data_for_test(test_gat2)
    students_data_gat2 = [data for data in all_data_gat2 if data['student'].id in student_ids_in_parallel]

    # --- Формируем данные для итоговой вкладки на основе уже полученных данных ---
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