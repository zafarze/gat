# D:\New_GAT\core\views\student_dashboard.py (ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

import json
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from collections import defaultdict

from ..models import StudentResult, Subject
from .. import utils

@login_required
def student_dashboard_view(request):
    """
    Отображает личный кабинет ученика с расширенной аналитикой и графиками.
    """
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'STUDENT':
        return redirect('core:dashboard')

    student = request.user.profile.student
    
    # ✨ ИСПРАВЛЕНИЕ: Убрана некорректная часть 'gat_test__school_class__school' из select_related,
    # так как она вызывала ошибку FieldError.
    student_results_qs = student.results.select_related(
        'gat_test__quarter__year'
    ).order_by('-gat_test__test_date')

    if not student_results_qs:
        return render(request, 'student_dashboard/students_dashboard.html', {
            'student': student,
            'has_results': False,
        })
    
    test_ids = [r.gat_test_id for r in student_results_qs]
    
    # Загружаем все результаты по нужным тестам для расчёта рангов
    all_results_for_tests = StudentResult.objects.filter(gat_test_id__in=test_ids).select_related('student__school_class__school')
    
    # Группируем баллы по тесту, классу и школе для эффективности
    scores_by_test = defaultdict(list)
    scores_by_class = defaultdict(lambda: defaultdict(list))
    scores_by_school = defaultdict(lambda: defaultdict(list))

    for res in all_results_for_tests:
        test_id = res.gat_test_id
        class_id = res.student.school_class_id
        school_id = res.student.school_class.school_id
        score = res.total_score
        
        scores_by_test[test_id].append(score)
        scores_by_class[test_id][class_id].append(score)
        scores_by_school[test_id][school_id].append(score)
    
    # Сортируем все списки один раз для быстрого нахождения ранга
    for test_id in scores_by_test:
        scores_by_test[test_id].sort(reverse=True)
        for class_id in scores_by_class[test_id]:
            scores_by_class[test_id][class_id].sort(reverse=True)
        for school_id in scores_by_school[test_id]:
            scores_by_school[test_id][school_id].sort(reverse=True)

    detailed_results_data = []
    subject_map = {s.id: s.name for s in Subject.objects.all()}

    for result in student_results_qs:
        gat_test = result.gat_test
        student_score = result.total_score
        
        # Получаем нужные списки для этого теста
        class_scores = scores_by_class.get(gat_test.id, {}).get(student.school_class_id, [])
        school_scores = scores_by_school.get(gat_test.id, {}).get(student.school_class.school_id, [])
        parallel_scores = scores_by_test.get(gat_test.id, [])
        
        # Находим ранг по каждому списку с помощью index()
        try: class_rank = class_scores.index(student_score) + 1
        except ValueError: class_rank = None
        try: school_rank = school_scores.index(student_score) + 1
        except ValueError: school_rank = None
        try: parallel_rank = parallel_scores.index(student_score) + 1
        except ValueError: parallel_rank = None
            
        best_subject, worst_subject = None, None
        subject_performance, processed_scores = [], []

        if isinstance(result.scores_by_subject, dict):
            for subj_id_str, answers in result.scores_by_subject.items():
                if not answers: continue
                total_q, correct_q = len(answers), sum(answers)
                
                try:
                    subject_name = subject_map.get(int(subj_id_str))
                    if total_q > 0 and subject_name:
                        perf = (correct_q / total_q) * 100
                        subject_performance.append({'name': subject_name, 'perf': perf})
                        processed_scores.append({
                            'subject': subject_name, 'answers': answers, 'correct': correct_q,
                            'total': total_q, 'incorrect': total_q - correct_q, 'percentage': round(perf, 1),
                        })
                except (ValueError, TypeError):
                    continue
        
        if subject_performance:
            best_subject = max(subject_performance, key=lambda x: x['perf'])
            worst_subject = min(subject_performance, key=lambda x: x['perf'])

        # Добавляем все новые ранги в словарь
        detailed_results_data.append({
            'result': result,
            'class_rank': class_rank, 'class_total': len(class_scores),
            'school_rank': school_rank, 'school_total': len(school_scores),
            'parallel_rank': parallel_rank, 'parallel_total': len(parallel_scores),
            'best_subject': best_subject, 'worst_subject': worst_subject,
            'processed_scores': sorted(processed_scores, key=lambda x: x['percentage'], reverse=True),
        })
        
    chart_labels = [res['result'].gat_test.name for res in reversed(detailed_results_data)]
    chart_data = [res['result'].total_score for res in reversed(detailed_results_data)]
    
    latest_result_details = detailed_results_data[0] if detailed_results_data else None

    context = {
        'student': student, 'has_results': True, 'latest_result': latest_result_details,
        'history': detailed_results_data, 'chart_labels': json.dumps(chart_labels, ensure_ascii=False),
        'chart_data': json.dumps(chart_data),
    }
    
    return render(request, 'student_dashboard/students_dashboard.html', context)