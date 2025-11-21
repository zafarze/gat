# D:\GAT\core\views\reports_detailed.py (НОВЫЙ ФАЙЛ)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db.models import Q
from openpyxl import Workbook
from weasyprint import HTML

from core.models import (
    AcademicYear, GatTest, QuestionCount, School,
    SchoolClass, Student, StudentResult, Subject
)
from core.views.permissions import get_accessible_schools
from core import utils

# --- DETAILED RESULTS ---

def get_detailed_results_data(test_number, request_get, request_user):
    """
    Готовит данные для детального рейтинга с улучшенной логикой фильтрации
    и ИСПРАВЛЕННЫМ расчетом заголовков таблицы.
    """
    year_id = request_get.get('year')
    quarter_id = request_get.get('quarter')
    school_id = request_get.get('school')
    class_id = request_get.get('class')
    test_id_from_upload = request_get.get('test_id')
    latest_test = None

    if test_id_from_upload:
        try:
            specific_test = GatTest.objects.filter(
                pk=test_id_from_upload,
                test_number=test_number
            ).select_related('quarter__year', 'school_class', 'school').first() # Добавлена 'school'

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
        if year_id and year_id != '0': filters &= Q(quarter__year_id=year_id)
        if quarter_id and quarter_id != '0': filters &= Q(quarter_id=quarter_id)
        if school_id and school_id != '0': filters &= Q(school_id=school_id)
        if class_id and class_id != '0': filters &= Q(school_class_id=class_id)

        if filters:
            tests_qs = tests_qs.filter(filters)

        latest_test = tests_qs.order_by('-test_date').first()

    if not latest_test:
        return [], [], None

    student_results = StudentResult.objects.filter(
        gat_test=latest_test
    ).select_related('student__school_class', 'gat_test')

    # --- ✨✨✨ ИСПРАВЛЕНИЕ ЗАГОЛОВКОВ ТАБЛИЦЫ ✨✨✨ ---
    table_header = []
    
    if latest_test and latest_test.school_class:
        # 1. Получаем родительский класс (параллель), e.g., '10'
        parent_class = latest_test.school_class
        if parent_class.parent:
            parent_class = parent_class.parent # Убедимся, что это точно параллель

        # 2. Получаем предметы ТОЛЬКО ИЗ САМОГО ТЕСТА (через M2M к BankQuestion)
        subjects_for_this_test = latest_test.subjects.all().order_by('name')

        # 3. Получаем ВСЕ QuestionCounts для этой параллели ОДНИМ запросом
        question_counts_map = {
            qc.subject_id: qc.number_of_questions
            for qc in QuestionCount.objects.filter(school_class=parent_class)
        }

        # 4. Cоздаем 'table_header' ТОЛЬКО для предметов из шага 2
        for subject in subjects_for_this_test:
            # 5. Берем кол-во вопросов из карты (map)
            q_count = question_counts_map.get(subject.id, 0) # 0, если не найдено

            table_header.append({
                'subject': subject,
                'questions': range(1, q_count + 1),
                'questions_count': q_count,
                'school_class': parent_class
            })
    # --- ✨✨✨ КОНЕЦ ИСПРАВЛЕНИЯ ✨✨✨ ---

    results_map = {res.student_id: res for res in student_results}
    
    students = Student.objects.filter(
        id__in=results_map.keys()
    ).select_related('school_class', 'school_class__school')

    students_data = []
    for student in students:
        result = results_map.get(student.id)
        total_score = result.total_score if result else 0
        subject_scores = {}

        if result and isinstance(result.scores_by_subject, dict):
            for subject_id_str, answers_dict in result.scores_by_subject.items():
                try:
                    subject_id = int(subject_id_str)
                    # ИСПРАВЛЕНИЕ: Обрабатываем словарь, а не список
                    correct_answers = sum(1 for v in answers_dict.values() if v is True)
                    total_questions = len(answers_dict)
                    
                    subject_scores[subject_id] = {
                        'score': correct_answers,
                        'total_questions': total_questions, # Это кол-во ответов (может не совпадать с QuestionCount)
                        'correct_answers': correct_answers
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
    """
    Отображает детальный рейтинг, используя
    исправленную функцию get_detailed_results_data.
    """
    students_data, table_header, latest_test = get_detailed_results_data(
        test_number, request.GET, request.user
    )

    accessible_schools = get_accessible_schools(request.user) if not request.user.is_superuser else School.objects.all()

    context = {
        'title': f'Детальный рейтинг GAT-{test_number}',
        'students_data': students_data,
        'table_header': table_header, # <-- Используем УЖЕ ИСПРАВЛЕННЫЙ table_header
        'years': AcademicYear.objects.all().order_by('-start_date'),
        'schools': accessible_schools,
        'classes': SchoolClass.objects.filter(parent__isnull=True).order_by('name'),
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
        for subject_id_str, answers_dict in result.scores_by_subject.items():
            try:
                subject_id = int(subject_id_str)
                subject = subject_map.get(subject_id)
                
                # ИСПРАВЛЕНИЕ: Обрабатываем словарь
                if subject and isinstance(answers_dict, dict):
                    total = len(answers_dict)
                    correct = sum(1 for v in answers_dict.values() if v is True)
                    
                    processed_scores[subject.name] = {
                        'answers': answers_dict, 'total': total, 'correct': correct,
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
    test_id = result.gat_test_id # Сохраняем ID для редиректа

    if request.method == 'POST':
        student_name = str(result.student)
        test_info = f"GAT-{test_number}"
        try:
            result.delete()
            messages.success(request, f'Результат для "{student_name}" (тест {test_info}) был успешно удален.')
            
            # Редирект обратно на страницу теста
            base_url = reverse('core:detailed_results_list', kwargs={'test_number': test_number})
            redirect_url = f"{base_url}?test_id={test_id}"
            return redirect(redirect_url)
            
        except Exception as e:
            messages.error(request, f'Ошибка при удалении результата: {str(e)}')
            return redirect('core:student_result_detail', pk=pk)

    context = {
        'item': result, 'title': f'Удалить результат: {result.student}',
        'cancel_url': reverse('core:student_result_detail', kwargs={'pk': pk}),
        'test_number': test_number
    }
    return render(request, 'results/confirm_delete_result.html', context)

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
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"GAT-{test_number}_results_{test_info.test_date if test_info else ''}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = f'GAT-{test_number} Результаты'

    headers = ["№", "ID", "ФИО Студента", "Класс", "Школа"]
    for header in table_header:
        subject_name = header['subject'].abbreviation or header['subject'].name[:3].upper()
        # Используем 'questions_count', а не range
        for i in range(1, header['questions_count'] + 1):
            headers.append(f"{subject_name}_{i}")
    headers.extend(["Общий балл", "Позиция в рейтинге"])

    sheet.append(headers)

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
                answers_dict = result.scores_by_subject.get(subject_id, {})
                q_count = header['questions_count']
                
                # Заполняем по номерам вопросов от 1 до q_count
                for i in range(1, q_count + 1):
                    answer = answers_dict.get(str(i)) # Ищем '1', '2' и т.д.
                    if answer is True:
                        row.append(1)
                    elif answer is False:
                        row.append(0)
                    else:
                        row.append('') # Пусто, если ответа нет
        else:
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
        'export_date': utils.get_current_date(), # Предполагая, что у вас есть 'utils'
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