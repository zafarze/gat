# D:\New_GAT\core\views\reports.py (ПОЛНАЯ ФИНАЛЬНАЯ ВЕРСИЯ)

import json
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.db.models import Count
from openpyxl import Workbook
from weasyprint import HTML
from django.core.cache import cache

from .. import services
from .. import utils
from ..models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    ClassSubject, GatTest, Student, StudentResult
)
from ..forms import UploadFileForm, StatisticsFilterForm, DeepAnalysisForm # Убедимся, что все формы импортированы

# --- UPLOAD AND DETAILED RESULTS ---

@login_required
def upload_results_view(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            gat_test = form.cleaned_data['gat_test']
            excel_file = request.FILES['file']
            try:
                report = services.process_excel_results(excel_file, gat_test)
                messages.success(request, f"Успешно обработано {report['processed_count']} результатов.")
                if report['skipped_count'] > 0:
                    messages.warning(request, f"Пропущено {report['skipped_count']} студентов.")
                return redirect('detailed_results_list', test_number=gat_test.test_number)
            except ValueError as e:
                messages.error(request, f'Ошибка в данных файла: {e}')
            except Exception as e:
                messages.error(request, f'Произошла непредвиденная ошибка: {e}')
    else:
        form = UploadFileForm()
    return render(request, 'results/upload_form.html', {'form': form, 'title': 'Загрузка результатов'})

def get_detailed_results_data(test_number, request_get, request_user):
    year_id, quarter_id, school_id, class_id = request_get.get('year'), request_get.get('quarter'), request_get.get('school'), request_get.get('class')
    tests_qs = GatTest.objects.filter(test_number=test_number).select_related('quarter__year', 'school_class__school')
    
    if not request_user.is_superuser and hasattr(request_user, 'profile') and request_user.profile.role == 'SCHOOL_DIRECTOR':
        if request_user.profile.school:
            tests_qs = tests_qs.filter(school_class__school=request_user.profile.school)
    
    if year_id: tests_qs = tests_qs.filter(quarter__year_id=year_id)
    if quarter_id: tests_qs = tests_qs.filter(quarter_id=quarter_id)
    if school_id: tests_qs = tests_qs.filter(school_class__school_id=school_id)
    if class_id: tests_qs = tests_qs.filter(school_class_id=class_id)
    
    student_results = StudentResult.objects.filter(gat_test__in=tests_qs).select_related('student__school_class', 'gat_test')
    
    table_header, first_test = [], tests_qs.first()
    if first_test:
        class_subjects = ClassSubject.objects.filter(school_class=first_test.school_class, subject__in=first_test.subjects.all()).select_related('subject').order_by('subject__name')
        for cs in class_subjects:
            table_header.append({'subject': cs.subject, 'questions': range(1, cs.number_of_questions + 1)})
            
    results_map = {res.student_id: res for res in student_results}
    students = Student.objects.filter(id__in=results_map.keys()).select_related('school_class')

    students_data = []
    for student in students:
        result = results_map.get(student.id)
        total_score = sum(sum(answers) for answers in result.scores.values()) if result and isinstance(result.scores, dict) else 0
        students_data.append({'student': student, 'result': result, 'total_score': total_score})
        
    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    return students_data, table_header

@login_required
def detailed_results_list_view(request, test_number):
    students_data, table_header = get_detailed_results_data(test_number, request.GET, request.user)
    context = {
        'title': f'Детальный рейтинг GAT-{test_number}', 'students_data': students_data, 'table_header': table_header,
        'years': AcademicYear.objects.all(), 'schools': School.objects.all(), 'selected_year': request.GET.get('year'),
        'selected_quarter': request.GET.get('quarter'), 'selected_school': request.GET.get('school'),
        'selected_class': request.GET.get('class'), 'test_number': test_number
    }
    return render(request, 'results/detailed_results_list.html', context)

@login_required
def student_result_detail_view(request, pk):
    result = get_object_or_404(StudentResult, pk=pk)
    subject_map = {s.id: s for s in Subject.objects.all()}
    processed_scores = {}
    if isinstance(result.scores, dict):
        for subject_id_str, answers in result.scores.items():
            subject = subject_map.get(int(subject_id_str))
            if subject:
                total, correct = len(answers), sum(answers)
                processed_scores[subject.name] = {'answers': answers, 'total': total, 'correct': correct, 'incorrect': total - correct, 'percentage': round((correct / total) * 100) if total > 0 else 0}
    context = {'result': result, 'processed_scores': processed_scores, 'title': f'Детальный отчет: {result.student}'}
    return render(request, 'results/student_result_detail.html', context)

@login_required
def student_result_delete_view(request, pk):
    result = get_object_or_404(StudentResult, pk=pk)
    test_number = result.gat_test.test_number
    if request.method == 'POST':
        result.delete()
        messages.success(request, f'Результат для "{result.student}" был успешно удален.')
        return redirect('detailed_results_list', test_number=test_number)
    context = {'item': result, 'title': f'Удалить результат: {result.student}', 'cancel_url': reverse('student_result_detail', kwargs={'pk': pk})}
    return render(request, 'results/confirm_delete_result.html', context)

# --- ARCHIVE AND COMPARISON ---

@login_required
def archive_years_view(request):
    results_qs = StudentResult.objects.all()
    user = request.user
    
    if not user.is_superuser and hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
        if user.profile.school:
            results_qs = results_qs.filter(student__school_class__school=user.profile.school)
            
    year_ids_with_results = results_qs.values_list('gat_test__quarter__year_id', flat=True).distinct()
    years = AcademicYear.objects.filter(id__in=year_ids_with_results)
    
    context = {'years': years, 'title': 'Архив: Выберите Год'}
    return render(request, 'results/archive_years.html', context)

@login_required
def archive_quarters_view(request, year_id):
    year = get_object_or_404(AcademicYear, id=year_id)
    quarters_qs = Quarter.objects.filter(year=year, gattests__student_results__isnull=False)
    user = request.user

    if not user.is_superuser and hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
        if user.profile.school:
            quarters_qs = quarters_qs.filter(gattests__school_class__school=user.profile.school)

    quarters = quarters_qs.distinct().order_by('start_date')
    context = {'year': year, 'quarters': quarters, 'title': f'Архив: {year.name}'}
    return render(request, 'results/archive_quarters.html', context)

@login_required
def archive_schools_view(request, quarter_id):
    quarter = get_object_or_404(Quarter, id=quarter_id)
    schools_qs = School.objects.filter(classes__gattests__quarter=quarter, classes__gattests__student_results__isnull=False)
    user = request.user
    
    if not user.is_superuser and hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
        if user.profile.school:
            schools_qs = schools_qs.filter(id=user.profile.school.id)

    schools = schools_qs.distinct().order_by('name')
    context = {'quarter': quarter, 'schools': schools, 'title': f'Архив: {quarter}'}
    return render(request, 'results/archive_schools.html', context)

@login_required
def archive_classes_view(request, quarter_id, school_id):
    quarter = get_object_or_404(Quarter, id=quarter_id)
    school = get_object_or_404(School, id=school_id)
    classes = SchoolClass.objects.filter(school=school, gattests__quarter=quarter, gattests__student_results__isnull=False).distinct().order_by('name')
    context = {'quarter': quarter, 'school': school, 'classes': classes, 'title': f'Архив: {school.name}'}
    return render(request, 'results/archive_classes.html', context)

def _get_data_for_test(gat_test):
    if not gat_test: return [], []
    table_header = []
    class_subjects = ClassSubject.objects.filter(school_class=gat_test.school_class, subject__in=gat_test.subjects.all()).select_related('subject').order_by('subject__name')
    for cs in class_subjects:
        table_header.append({'subject': cs.subject, 'questions': range(1, cs.number_of_questions + 1)})
    student_results = StudentResult.objects.filter(gat_test=gat_test).select_related('student__school_class')
    students_data = []
    for result in student_results:
        total_score = sum(sum(answers) for answers in result.scores.values() if isinstance(answers, list)) if isinstance(result.scores, dict) else 0
        students_data.append({'student': result.student, 'result': result, 'total_score': total_score})
    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    return students_data, table_header

@login_required
def class_results_dashboard_view(request, quarter_id, class_id):
    school_class, quarter = get_object_or_404(SchoolClass, id=class_id), get_object_or_404(Quarter, id=quarter_id)
    test_gat1, test_gat2 = GatTest.objects.filter(school_class=school_class, quarter=quarter, test_number=1).first(), GatTest.objects.filter(school_class=school_class, quarter=quarter, test_number=2).first()
    students_data_gat1, table_header_gat1 = _get_data_for_test(test_gat1)
    students_data_gat2, table_header_gat2 = _get_data_for_test(test_gat2)
    all_students_map = {}
    for data in students_data_gat1:
        student = data['student']
        if student.id not in all_students_map: all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score1'] = data['total_score']
    for data in students_data_gat2:
        student = data['student']
        if student.id not in all_students_map: all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score2'] = data['total_score']
    students_data_total = []
    for student_id, data in all_students_map.items():
        score1, score2 = data.get('score1'), data.get('score2')
        total_score = (score1 or 0) + (score2 or 0) if score1 is not None or score2 is not None else None
        students_data_total.append({'student': data['student'], 'score1': score1, 'score2': score2, 'total_score': total_score})
    students_data_total.sort(key=lambda x: (x['total_score'] is None, -x.get('total_score', 0) if x.get('total_score') is not None else 0))
    context = {
        'title': f'Отчет: {school_class.name}', 'school_class': school_class, 'quarter': quarter, 'students_data_total': students_data_total,
        'students_data_gat1': students_data_gat1, 'table_header_gat1': table_header_gat1,
        'students_data_gat2': students_data_gat2, 'table_header_gat2': table_header_gat2,
        'test_gat1': test_gat1, 'test_gat2': test_gat2,
    }
    return render(request, 'results/class_results_dashboard.html', context)

@login_required
def compare_class_tests_view(request, test1_id, test2_id):
    test1, test2 = get_object_or_404(GatTest, id=test1_id), get_object_or_404(GatTest, id=test2_id)
    all_student_ids = set(StudentResult.objects.filter(gat_test=test1).values_list('student_id', flat=True)) | set(StudentResult.objects.filter(gat_test=test2).values_list('student_id', flat=True))
    all_students, results1_map, results2_map = Student.objects.filter(id__in=all_student_ids), {res.student_id: res for res in StudentResult.objects.filter(gat_test=test1)}, {res.student_id: res for res in StudentResult.objects.filter(gat_test=test2)}
    full_scores1 = [{'student': s, 'score': sum(sum(ans) for ans in results1_map[s.id].scores.values()) if s.id in results1_map else 0, 'present': s.id in results1_map} for s in all_students]
    full_scores2 = [{'student': s, 'score': sum(sum(ans) for ans in results2_map[s.id].scores.values()) if s.id in results2_map else 0, 'present': s.id in results2_map} for s in all_students]
    rank_map1, rank_map2 = {item['student'].id: i + 1 for i, item in enumerate(sorted(full_scores1, key=lambda x: x['score'], reverse=True))}, {item['student'].id: i + 1 for i, item in enumerate(sorted(full_scores2, key=lambda x: x['score'], reverse=True))}
    comparison_results = []
    for student in all_students:
        is_present1, is_present2 = student.id in results1_map, student.id in results2_map
        rank1, rank2 = rank_map1.get(student.id), rank_map2.get(student.id)
        comparison_results.append({'student': student, 'rank1': rank1 if is_present1 else '—', 'rank2': rank2 if is_present2 else '—', 'avg_rank': (rank1 + rank2) / 2 if is_present1 and is_present2 else float('inf')})
    comparison_results.sort(key=lambda x: x['avg_rank'])
    students_data_1, table_header_1 = _get_data_for_test(test1)
    students_data_2, table_header_2 = _get_data_for_test(test2)
    context = {
        'results': comparison_results, 'test1': test1, 'test2': test2, 'title': f'Итоговый рейтинг для {test1.school_class.name}',
        'students_data_1': students_data_1, 'table_header_1': table_header_1, 'students_data_2': students_data_2, 'table_header_2': table_header_2,
    }
    return render(request, 'results/comparison_detail.html', context)

# --- MAIN REPORTING VIEWS ---

@login_required
def analysis_view(request):
    """
    Отображает страницу 'Анализ успеваемости', сравнивая классы внутри одной школы.
    """
    user = request.user
    
    # --- Подготовка данных для фильтров ---
    schools_qs = School.objects.all()
    quarters_qs = Quarter.objects.annotate(test_count=Count('gattests')).filter(test_count__gt=0)
    
    # Если пользователь - директор, ограничиваем выбор школ
    if not user.is_superuser and hasattr(user, 'profile') and user.profile.role == 'SCHOOL_DIRECTOR':
        if user.profile.school:
            schools_qs = schools_qs.filter(id=user.profile.school.id)
            quarters_qs = quarters_qs.filter(gattests__school_class__school=user.profile.school).distinct()

    # Получаем выбранные значения из GET-запроса
    try:
        selected_quarter_id = int(request.GET.get('quarter', 0))
    except (ValueError, TypeError):
        selected_quarter_id = 0
    
    try:
        selected_school_id = int(request.GET.get('school', 0))
    except (ValueError, TypeError):
        selected_school_id = 0

    try:
        selected_test_number = int(request.GET.get('test_number', 0))
    except (ValueError, TypeError):
        selected_test_number = 0

    context = {
        'title': 'Анализ успеваемости',
        'quarters': quarters_qs,
        'schools': schools_qs,
        'selected_quarter_id': selected_quarter_id,
        'selected_school_id': selected_school_id,
        'selected_test_number': selected_test_number,
        'has_results': False,
    }

    # --- Основная логика, если все фильтры выбраны ---
    if selected_quarter_id and selected_school_id and selected_test_number:
        results_qs = StudentResult.objects.filter(
            gat_test__quarter_id=selected_quarter_id,
            student__school_class__school_id=selected_school_id,
            gat_test__test_number=selected_test_number
        ).select_related('student__school_class', 'gat_test')

        if results_qs.exists():
            subject_map = {s.id: s.name for s in Subject.objects.all()}
            
            # Структура для сбора данных: {class_name: {subject_name: {'correct': X, 'total': Y}}}
            agg_data = defaultdict(lambda: defaultdict(lambda: {'correct': 0, 'total': 0}))
            
            # Собираем сырые данные
            for result in results_qs:
                class_name = result.student.school_class.name
                for sid_str, answers in result.scores.items():
                    subject_name = subject_map.get(int(sid_str))
                    if subject_name:
                        agg_data[class_name][subject_name]['correct'] += sum(answers)
                        agg_data[class_name][subject_name]['total'] += len(answers)
            
            # Рассчитываем проценты и готовим данные для таблицы и графика
            table_data = defaultdict(dict)
            all_subjects = set()
            all_classes = sorted(agg_data.keys())

            for class_name, subjects_data in agg_data.items():
                for subject_name, scores in subjects_data.items():
                    all_subjects.add(subject_name)
                    if scores['total'] > 0:
                        percentage = round((scores['correct'] / scores['total']) * 100, 1)
                        table_data[subject_name][class_name] = percentage
            
            sorted_subjects = sorted(list(all_subjects))

            # Формируем датасеты для графика
            chart_datasets = []
            for class_name in all_classes:
                dataset = {
                    'label': class_name,
                    'data': [table_data[subj_name].get(class_name, 0) for subj_name in sorted_subjects]
                }
                chart_datasets.append(dataset)

            context.update({
                'has_results': True,
                'table_headers': all_classes,
                'table_data': dict(sorted(table_data.items())),
                'chart_labels': json.dumps(sorted_subjects, ensure_ascii=False),
                'chart_datasets': json.dumps(chart_datasets, ensure_ascii=False)
            })

    return render(request, 'analysis.html', context)


@login_required
def statistics_view(request):
    """Отображает страницу статистики с новым дизайном фильтров."""
    form = StatisticsFilterForm(request.GET or None, user=request.user)
    context = {'title': 'Статистика', 'form': form}
    selected_school_ids = request.GET.getlist('schools')
    if selected_school_ids:
        form.fields['school_classes'].queryset = SchoolClass.objects.filter(school_id__in=selected_school_ids).order_by('name')
    if form.is_valid():
        selected_quarters = form.cleaned_data.get('quarters')
        selected_schools = form.cleaned_data.get('schools')
        selected_classes = form.cleaned_data.get('school_classes')
        selected_test_numbers = form.cleaned_data.get('test_numbers')
        results_qs = StudentResult.objects.select_related(
            'student__school_class__school', 'student__school_class__parent', 'gat_test__quarter'
        ).all()

        if not request.user.is_superuser and hasattr(request.user, 'profile') and request.user.profile.role == 'SCHOOL_DIRECTOR':
            if request.user.profile.school:
                results_qs = results_qs.filter(student__school_class__school=request.user.profile.school)

        if selected_schools: results_qs = results_qs.filter(student__school_class__school__in=selected_schools)
        if selected_quarters: results_qs = results_qs.filter(gat_test__quarter__in=selected_quarters)
        if selected_classes: results_qs = results_qs.filter(student__school_class__in=selected_classes)
        if selected_test_numbers: results_qs = results_qs.filter(gat_test__test_number__in=selected_test_numbers)

        student_scores_list, subject_scores = [], defaultdict(lambda: {'total': 0, 'correct': 0})
        subject_map = {s.id: s.name for s in Subject.objects.all()}
        for r in results_qs:
            total_student_score = 0
            if r.student and isinstance(r.scores, dict):
                for sid, ans in r.scores.items():
                    if isinstance(ans, list):
                        correct = sum(i for i in ans if isinstance(i, (int, float)))
                        total_student_score += correct
                        s_name = subject_map.get(int(sid))
                        if s_name:
                            subject_scores[s_name]['correct'] += correct
                            subject_scores[s_name]['total'] += len(ans)
            student_scores_list.append({'student': r.student, 'score': total_student_score})
        total_tests_taken, total_students = len(student_scores_list), results_qs.values('student').distinct().count()
        average_score = round(sum(s['score'] for s in student_scores_list) / total_tests_taken, 1) if total_tests_taken > 0 else 0
        pass_rate = round(sum(1 for s in student_scores_list if s['score'] > 50) / total_tests_taken * 100, 1) if total_tests_taken > 0 else 0
        subject_perf = [{'name': name, 'percentage': round(data['correct'] / data['total'] * 100, 1) if data['total'] > 0 else 0} for name, data in subject_scores.items()]
        top_subject = max(subject_perf, key=lambda x: x['percentage']) if subject_perf else {'name': '—', 'percentage': 0}
        bottom_subject = min(subject_perf, key=lambda x: x['percentage']) if subject_perf else {'name': '—', 'percentage': 0}
        subject_perf_labels = json.dumps([s['name'] for s in subject_perf], ensure_ascii=False)
        subject_perf_data = json.dumps([s['percentage'] for s in subject_perf])
        score_bins = defaultdict(int);
        for s in student_scores_list:
            bin = int(s['score'] // 10) * 10; score_bins[bin] += 1
        distribution_labels, distribution_data = json.dumps(sorted(score_bins.keys())), json.dumps([score_bins[key] for key in sorted(score_bins.keys())])
        
        student_class_ids = {r.student.school_class_id for r in results_qs if r.student}
        parent_class_ids = {r.student.school_class.parent_id for r in results_qs if r.student and r.student.school_class.parent_id}
        all_relevant_class_ids = student_class_ids.union(parent_class_ids)
        class_subjects_qs = ClassSubject.objects.filter(school_class_id__in=all_relevant_class_ids)
        max_scores_map = {(cs.school_class_id, cs.subject_id): cs.number_of_questions for cs in class_subjects_qs}
        per_subject_report, school_summary_report = defaultdict(lambda: defaultdict(lambda: {'scores_for_avg': [], 'grades': defaultdict(int)})), {'scores_for_avg': [], 'grades': defaultdict(int)}
        for result in results_qs:
            if not (result.student and result.student.school_class and isinstance(result.scores, dict)): continue
            student_class = result.student.school_class
            for subject_id_str, answers in result.scores.items():
                if not isinstance(answers, list): continue
                subject_id, subject_name = int(subject_id_str), subject_map.get(int(subject_id_str))
                max_score = max_scores_map.get((student_class.id, subject_id))
                if not max_score and student_class.parent_id: max_score = max_scores_map.get((student_class.parent_id, subject_id))
                if subject_name and max_score:
                    percentage = (sum(answers) / max_score) * 100; grade = utils.calculate_grade_from_percentage(percentage)
                    per_subject_report[subject_name][student_class.name]['scores_for_avg'].append(percentage)
                    per_subject_report[subject_name][student_class.name]['grades'][grade] += 1
                    school_summary_report['scores_for_avg'].append(percentage)
                    school_summary_report['grades'][grade] += 1
        
        final_grade_report = {}
        for subject, classes_data in sorted(per_subject_report.items()):
            final_grade_report[subject], subject_total_grades, subject_total_scores = {}, defaultdict(int), []
            for class_name, data in sorted(classes_data.items()):
                scores = data['scores_for_avg']
                avg_score = round(sum(scores) / len(scores), 1) if scores else 0
                final_grade_report[subject][class_name] = {'average_score': avg_score, 'grades': dict(data['grades'])}
                subject_total_scores.extend(scores)
                for grade, count in data['grades'].items(): subject_total_grades[grade] += count
            total_avg = round(sum(subject_total_scores) / len(subject_total_scores), 1) if subject_total_scores else 0
            final_grade_report[subject]['Итог'] = {'average_score': total_avg, 'grades': dict(subject_total_grades)}
        
        final_school_summary = {}
        summary_scores = school_summary_report['scores_for_avg']
        final_school_summary['average_score'] = round(sum(summary_scores) / len(summary_scores), 1) if summary_scores else 0
        final_school_summary['grades'] = dict(school_summary_report['grades'])
        
        context.update({
            'has_results': True, 'average_score': average_score, 'pass_rate': pass_rate, 'total_students': total_students,
            'total_tests_taken': total_tests_taken, 'top_subject': top_subject, 'bottom_subject': bottom_subject,
            'subject_perf_labels': subject_perf_labels, 'subject_perf_data': subject_perf_data,
            'distribution_labels': distribution_labels, 'distribution_data': distribution_data,
            'grade_distribution_report': final_grade_report, 'school_summary_report': final_school_summary,
            'grade_range': range(10, 0, -1),
        })
    return render(request, 'statistics.html', context)


# --- EXPORT FUNCTIONS ---

@login_required
def export_detailed_results_excel(request, test_number):
    students_data, table_header = get_detailed_results_data(test_number, request.GET, request.user)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheet.sheet')
    response['Content-Disposition'] = f'attachment; filename="GAT-{test_number}_results.xlsx"'
    workbook, sheet = Workbook(), workbook.active
    sheet.title = f'GAT-{test_number} Результаты'
    headers = ["№", "ID", "ФИО Студента", "Класс"]
    for header in table_header:
        for i in range(1, header['questions'][-1] + 1): headers.append(f"{header['subject'].abbreviation}_{i}")
    headers.append("Общий балл")
    sheet.append(headers)
    for idx, data in enumerate(students_data, 1):
        row = [idx, data['student'].student_id, str(data['student']), data['student'].school_class.name]
        result = data.get('result')
        if result:
            for header in table_header:
                answers = result.scores.get(str(header['subject'].id), [])
                row.extend(answers)
                row.extend([''] * (len(header['questions']) - len(answers)))
        row.append(data['total_score'])
        sheet.append(row)
    workbook.save(response)
    return response

@login_required
def export_detailed_results_pdf(request, test_number):
    students_data, table_header = get_detailed_results_data(test_number, request.GET, request.user)
    context = {'title': f'Детальный рейтинг GAT-{test_number}', 'students_data': students_data, 'table_header': table_header}
    html_string = render_to_string('results/detailed_results_pdf.html', context)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="GAT-{test_number}_results.pdf"'
    HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf(response)
    return response