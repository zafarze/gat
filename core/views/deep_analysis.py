# /core/views/deep_analysis_view.py

import json
from collections import defaultdict
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from ..models import SchoolClass, Subject, StudentResult
from ..forms import DeepAnalysisForm

# =================================================================================
# ======================== DEEP_ANALYSIS_VIEW LOGIC ===============================
# =================================================================================

@login_required
def deep_analysis_view(request):
    """
    Отображает страницу углубленного анализа с множеством визуализаций и инсайтов.
    """
    # --- ИЗМЕНЕНИЕ ЗДЕСЬ: передаем request.user в форму ---
    form = DeepAnalysisForm(request.GET or None, user=request.user)
    if request.GET:
        school_ids = request.GET.getlist('schools')
        if school_ids:
            form.fields['school_classes'].queryset = SchoolClass.objects.filter(school_id__in=school_ids)
            form.fields['subjects'].queryset = Subject.objects.filter(classsubject__school_class__school_id__in=school_ids).distinct()

    context = {'title': 'Углубленный анализ', 'form': form, 'has_results': False}

    if form.is_valid():
        selected_quarters = form.cleaned_data['quarters']
        selected_schools = form.cleaned_data['schools']
        selected_classes = form.cleaned_data['school_classes']
        selected_subjects_qs = form.cleaned_data['subjects']
        selected_test_numbers = form.cleaned_data['test_numbers']
        subject_ids_to_fetch = [str(s.id) for s in selected_subjects_qs]

        results_qs = StudentResult.objects.filter(
            gat_test__quarter__in=selected_quarters,
            student__school_class__school__in=selected_schools,
            gat_test__test_number__in=selected_test_numbers,
            scores__has_any_keys=subject_ids_to_fetch
        ).select_related('student__school_class__school', 'gat_test__quarter')

        if selected_classes.exists():
            results_qs = results_qs.filter(student__school_class__in=selected_classes)

        if results_qs.exists():
            unique_subject_names = sorted(list(set(selected_subjects_qs.values_list('name', flat=True))))
            subject_id_to_name_map = {s.id: s.name for s in selected_subjects_qs}
            
            analysis_data, student_performance = _process_results_for_deep_analysis(results_qs, unique_subject_names, subject_id_to_name_map)
            
            summary_chart_data, radar_chart_data = _prepare_summary_and_radar_charts(analysis_data, selected_schools, unique_subject_names)
            heatmap_data, heatmap_summary = _prepare_heatmap_data_and_summary(analysis_data)
            trend_chart_data = _prepare_trend_chart_data(results_qs, subject_id_to_name_map)

            problematic_questions = _find_problematic_questions(analysis_data)
            at_risk_students = _find_at_risk_students(student_performance)

            context.update({
                'has_results': True,
                'summary_chart_data': json.dumps(summary_chart_data, ensure_ascii=False),
                'radar_chart_data': json.dumps(radar_chart_data, ensure_ascii=False),
                'heatmap_data': heatmap_data,
                'heatmap_summary': heatmap_summary,
                'trend_chart_data': json.dumps(trend_chart_data, ensure_ascii=False) if trend_chart_data else None,
                'problematic_questions': problematic_questions,
                'at_risk_students': at_risk_students,
            })

    return render(request, 'deep_analysis.html', context)


# --- Helper Functions for deep_analysis_view ---

def _process_results_for_deep_analysis(results_qs, unique_subject_names, subject_id_to_name_map):
    temp_analysis_data = {}
    student_performance = defaultdict(lambda: {'scores': [], 'count': 0})

    for result in results_qs:
        school = result.student.school_class.school
        if school.id not in temp_analysis_data:
            temp_analysis_data[school.id] = {
                'school_name': school.name,
                'subjects': {name: {'question_details': defaultdict(lambda: {'correct': 0, 'total': 0})} for name in unique_subject_names}
            }
        
        total_correct_for_student, total_questions_for_student = 0, 0
        for subject_id_str, answers in result.scores.items():
            subject_name = subject_id_to_name_map.get(int(subject_id_str))
            if subject_name in temp_analysis_data[school.id]['subjects']:
                data_ref = temp_analysis_data[school.id]['subjects'][subject_name]
                for i, answer in enumerate(answers):
                    q_num = str(i + 1)
                    data_ref['question_details'][q_num]['correct'] += answer
                    data_ref['question_details'][q_num]['total'] += 1
                total_correct_for_student += sum(answers)
                total_questions_for_student += len(answers)
        
        if total_questions_for_student > 0:
            avg_percent = (total_correct_for_student / total_questions_for_student) * 100
            student_id = result.student.id
            student_performance[student_id]['scores'].append(avg_percent)
            student_performance[student_id]['count'] += 1
            student_performance[student_id]['name'] = str(result.student)
            student_performance[student_id]['class_name'] = result.student.school_class.name

    for school_data in temp_analysis_data.values():
        for subject_data in school_data['subjects'].values():
            total_correct = 0
            total_q = 0
            for q_data in subject_data['question_details'].values():
                if q_data['total'] > 0:
                    q_data['percentage'] = round((q_data['correct'] / q_data['total']) * 100, 1)
                    total_correct += q_data['correct']
                    total_q += q_data['total']
            subject_data['overall_percentage'] = round((total_correct / total_q) * 100, 1) if total_q > 0 else 0

    return temp_analysis_data, student_performance


def _prepare_summary_and_radar_charts(analysis_data, selected_schools, unique_subject_names):
    bar_datasets, radar_datasets = [], []
    
    # Calculate average performance for the "average line" in the bar chart
    overall_subject_averages = []
    for name in unique_subject_names:
        all_schools_correct, all_schools_total = 0, 0
        for school in selected_schools:
            if school.id in analysis_data:
                q_details = analysis_data[school.id]['subjects'][name].get('question_details', {})
                for q_data in q_details.values():
                    all_schools_correct += q_data['correct']
                    all_schools_total += q_data['total']
        avg = round((all_schools_correct / all_schools_total) * 100, 1) if all_schools_total > 0 else 0
        overall_subject_averages.append(avg)

    # Prepare datasets for each school
    for school in selected_schools:
        if school.id in analysis_data:
            bar_data = [analysis_data[school.id]['subjects'][name]['overall_percentage'] for name in unique_subject_names]
            bar_datasets.append({'label': school.name, 'data': bar_data})
            radar_datasets.append({'label': school.name, 'data': bar_data, 'fill': True, 'borderWidth': 2})

    # Add the average line dataset to the bar chart
    bar_datasets.append({
        'label': 'Среднее по всем', 'data': overall_subject_averages,
        'type': 'line', 'borderDash': [5, 5], 'borderWidth': 2, 'pointRadius': 0,
        'datalabels': {'display': False}
    })

    summary_chart = {'labels': unique_subject_names, 'datasets': bar_datasets}
    radar_chart = {'labels': unique_subject_names, 'datasets': radar_datasets}
    return summary_chart, radar_chart


def _prepare_heatmap_data_and_summary(analysis_data):
    """
    Готовит данные для тепловой карты и подробной сводки по каждому предмету,
    включая рейтинг школ.
    """
    heatmap_data = {}
    heatmap_summary = {}

    # Сначала собираем все данные в heatmap_data
    for school_data in analysis_data.values():
        school_name = school_data['school_name']
        for subject_name, subject_data in school_data['subjects'].items():
            if not subject_data['question_details']:
                continue

            if subject_name not in heatmap_data:
                heatmap_data[subject_name] = {'questions': set(), 'schools': {}}

            heatmap_data[subject_name]['schools'][school_name] = {}
            for q_num, q_stats in subject_data['question_details'].items():
                heatmap_data[subject_name]['questions'].add(q_num)
                heatmap_data[subject_name]['schools'][school_name][q_num] = {
                    'percentage': q_stats.get('percentage', 0),
                    'correct': q_stats.get('correct', 0),
                    'total': q_stats.get('total', 0),
                }

    # Теперь на основе собранных данных генерируем сводку
    for subject_name, data in heatmap_data.items():
        data['questions'] = sorted(list(data['questions']), key=int)
        
        # Расчет сводки по вопросам (самые легкие/сложные)
        question_avg_perf = []
        for q_num in data['questions']:
            total_correct, total_answers = 0, 0
            for school_q_data in data['schools'].values():
                if q_num in school_q_data:
                    total_correct += school_q_data[q_num]['correct']
                    total_answers += school_q_data[q_num]['total']
            avg_p = round((total_correct / total_answers) * 100, 1) if total_answers > 0 else 0
            question_avg_perf.append({'q_num': q_num, 'percentage': avg_p})

        sorted_by_perf = sorted(question_avg_perf, key=lambda x: x['percentage'], reverse=True)
        
        # Расчет рейтинга школ и общего среднего балла
        school_perf_list = []
        total_correct_all_schools, total_q_all_schools = 0, 0
        for school_name, school_q_data in data['schools'].items():
            s_total_correct, s_total_q = 0, 0
            for q in school_q_data.values():
                s_total_correct += q['correct']
                s_total_q += q['total']
            
            s_avg = round((s_total_correct / s_total_q) * 100, 1) if s_total_q > 0 else 0
            school_perf_list.append({'school': school_name, 'avg': s_avg})
            total_correct_all_schools += s_total_correct
            total_q_all_schools += s_total_q

        sorted_schools = sorted(school_perf_list, key=lambda x: x['avg'], reverse=True)
        overall_avg = round((total_correct_all_schools / total_q_all_schools) * 100, 1) if total_q_all_schools > 0 else 0

        # --- ИЗМЕНЕНИЕ: Заранее вычисляем разницу ---
        difference = 0
        if len(sorted_schools) > 1:
            leader_avg = sorted_schools[0]['avg']
            outsider_avg = sorted_schools[-1]['avg']
            difference = round(leader_avg - outsider_avg, 1)

        # Собираем все в один объект
        heatmap_summary[subject_name] = {
            'easiest': sorted_by_perf[:3] if sorted_by_perf else [],
            'hardest': sorted_by_perf[-3:][::-1] if sorted_by_perf else [],
            'ranking': sorted_schools,
            'overall_avg': overall_avg,
            'difference': difference, # <-- Добавляем готовую разницу в контекст
        }

    return heatmap_data, heatmap_summary


def _prepare_trend_chart_data(results_qs, subject_id_to_name_map):
    quarters_with_results = results_qs.values('gat_test__quarter').distinct()
    if quarters_with_results.count() < 2: return None

    trend_data = defaultdict(lambda: defaultdict(lambda: {'correct': 0, 'total': 0}))
    all_quarters = set()
    for r in results_qs.select_related('gat_test__quarter'):
        quarter_name = r.gat_test.quarter.name
        all_quarters.add((r.gat_test.quarter.start_date, quarter_name))
        for sid, answers in r.scores.items():
            s_name = subject_id_to_name_map.get(int(sid))
            if s_name:
                trend_data[s_name][quarter_name]['correct'] += sum(answers)
                trend_data[s_name][quarter_name]['total'] += len(answers)
    
    sorted_quarters = [name for date, name in sorted(list(all_quarters))]
    
    trend_datasets = []
    for subject, quarters_data in trend_data.items():
        data_points = []
        for q_name in sorted_quarters:
            data = quarters_data.get(q_name)
            if data and data['total'] > 0:
                data_points.append(round((data['correct'] / data['total']) * 100, 1))
            else:
                data_points.append(None)
        trend_datasets.append({'label': subject, 'data': data_points, 'tension': 0.4, 'fill': True})
        
    return {'labels': sorted_quarters, 'datasets': trend_datasets}


def _find_problematic_questions(analysis_data, top_n=3):
    problems = defaultdict(list)
    for school_data in analysis_data.values():
        for s_name, s_data in school_data['subjects'].items():
            for q_num, q_stats in s_data['question_details'].items():
                if q_stats['total'] > 0:
                    problems[s_name].append({'q': q_num, 'p': q_stats.get('percentage', 0), 'school': school_data['school_name']})
    
    top_problems = {}
    for s_name, q_list in problems.items():
        sorted_q = sorted(q_list, key=lambda x: x['p'])
        top_problems[s_name] = sorted_q[:top_n]
    return top_problems


def _find_at_risk_students(student_performance, threshold=40, min_tests=1):
    at_risk = []
    for student_id, data in student_performance.items():
        if data['count'] >= min_tests:
            avg_score = sum(data['scores']) / data['count']
            if avg_score < threshold:
                at_risk.append({'name': data['name'], 'class': data['class_name'], 'score': round(avg_score, 1)})
    return sorted(at_risk, key=lambda x: x['score'])