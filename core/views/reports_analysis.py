# D:\GAT\core\views\reports_analysis.py (НОВЫЙ ФАЙЛ)

import json
from collections import defaultdict
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.models import UserProfile

from core.models import (
    SchoolClass, StudentResult, Subject
)
from core.forms import StatisticsFilterForm
from core.views.permissions import get_accessible_schools, get_accessible_subjects

@login_required
def analysis_view(request):
    """
    Анализ успеваемости с использованием фильтров как в 'Статистике'
    и учетом прав доступа Эксперта.
    """
    user = request.user
    profile = getattr(user, 'profile', None)
    form = StatisticsFilterForm(request.GET or None, user=user)

    selected_quarter_ids_str = request.GET.getlist('quarters')
    selected_school_ids_str = request.GET.getlist('schools')
    selected_class_ids_str = request.GET.getlist('school_classes')
    selected_subject_ids_str = request.GET.getlist('subjects')
    final_grouped_classes = {}

    if request.GET:
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

    context = {
        'title': 'Анализ успеваемости',
        'form': form,
        'has_results': False,
        'grouped_classes': final_grouped_classes,
        'selected_quarter_ids': selected_quarter_ids_str,
        'selected_school_ids': selected_school_ids_str,
        'selected_class_ids': selected_class_ids_str,
        'selected_subject_ids': selected_subject_ids_str,
        'table_headers': [],
        'table_data': {},
        'subject_averages': {},
        'subject_ranks': {},
        'chart_labels': '[]',
        'chart_datasets': '[]',
        'selected_class_ids_json': json.dumps(selected_class_ids_str),
        'selected_subject_ids_json': json.dumps(selected_subject_ids_str),
    }

    if form.is_valid():
        selected_quarters = form.cleaned_data['quarters']
        selected_schools = form.cleaned_data['schools']
        selected_classes_qs = form.cleaned_data['school_classes']
        selected_test_numbers = form.cleaned_data['test_numbers']
        selected_days = form.cleaned_data['days']
        selected_subjects_qs = form.cleaned_data['subjects']

        selected_class_ids_list_int = list(selected_classes_qs.values_list('id', flat=True))
        parent_class_ids_int = selected_classes_qs.filter(parent__isnull=True).values_list('id', flat=True)
        if parent_class_ids_int:
            child_class_ids_int = list(SchoolClass.objects.filter(parent_id__in=parent_class_ids_int).values_list('id', flat=True))
            selected_class_ids_list_int.extend(child_class_ids_int)
        final_class_ids_int = set(selected_class_ids_list_int)

        accessible_schools = get_accessible_schools(user)
        results_qs = StudentResult.objects.filter(
            student__school_class__school__in=accessible_schools
        ).select_related('student__school_class', 'gat_test__quarter__year')

        if selected_quarters: results_qs = results_qs.filter(gat_test__quarter__in=selected_quarters)
        if selected_schools: results_qs = results_qs.filter(student__school_class__school__in=selected_schools)
        if final_class_ids_int: results_qs = results_qs.filter(student__school_class_id__in=final_class_ids_int)
        if selected_test_numbers: results_qs = results_qs.filter(gat_test__test_number__in=selected_test_numbers)
        if selected_days: results_qs = results_qs.filter(gat_test__day__in=selected_days)

        accessible_subjects_qs = Subject.objects.none()
        is_expert = profile and profile.role == UserProfile.Role.EXPERT
        expert_subject_ids_int = set()

        if is_expert:
            expert_subjects = profile.subjects.all()
            expert_subject_ids_int = set(expert_subjects.values_list('id', flat=True))

            if selected_subjects_qs.exists():
                accessible_subjects_qs = selected_subjects_qs.filter(id__in=expert_subject_ids_int)
            elif expert_subjects.exists():
                accessible_subjects_qs = expert_subjects
            elif not accessible_subjects_qs.exists():
                 results_qs = results_qs.none()
        else:
            accessible_subjects_qs = selected_subjects_qs

        if results_qs.exists():
            if accessible_subjects_qs.exists():
                subject_id_keys_to_filter = [str(s.id) for s in accessible_subjects_qs]
                results_qs = results_qs.filter(scores_by_subject__has_any_keys=subject_id_keys_to_filter)
            elif is_expert:
                 results_qs = results_qs.none()

        if not accessible_subjects_qs.exists() and not is_expert and results_qs.exists():
             all_subject_ids_in_results = set()
             for r in results_qs:
                 if isinstance(r.scores_by_subject, dict):
                     all_subject_ids_in_results.update(int(sid) for sid in r.scores_by_subject.keys())
             accessible_subjects_qs = Subject.objects.filter(id__in=all_subject_ids_in_results)

        if results_qs.exists() and accessible_subjects_qs.exists():
            subject_map = {s.id: s.name for s in accessible_subjects_qs}
            allowed_subject_ids_int = set(subject_map.keys())
            agg_data = defaultdict(lambda: defaultdict(lambda: {'correct': 0, 'total': 0}))

            results_qs = results_qs.prefetch_related('student__school_class')

            for result in results_qs:
                class_name = result.student.school_class.name
                if isinstance(result.scores_by_subject, dict):
                    for subject_id_str, answers in result.scores_by_subject.items():
                        try:
                            subject_id = int(subject_id_str)
                            if subject_id in allowed_subject_ids_int:
                                subject_name = subject_map.get(subject_id)
                                
                                # ИСПРАВЛЕНИЕ: Обрабатываем словарь ответов
                                if subject_name and isinstance(answers, dict):
                                    correct_answers = sum(1 for answer in answers.values() if answer is True)
                                    total_questions = len(answers)
                                    agg_data[class_name][subject_name]['correct'] += correct_answers
                                    agg_data[class_name][subject_name]['total'] += total_questions
                        except (ValueError, TypeError):
                            continue

            table_data = defaultdict(dict)
            all_subjects = set(accessible_subjects_qs.values_list('name', flat=True))
            all_classes = sorted(agg_data.keys())

            for class_name, subjects_data in agg_data.items():
                for subject_name, scores in subjects_data.items():
                    if scores['total'] > 0:
                        percentage = round((scores['correct'] / scores['total']) * 100, 1)
                        table_data[subject_name][class_name] = percentage

            subject_averages = {}
            for subject_name in all_subjects:
                scores = [score for class_name in all_classes if (score := table_data.get(subject_name, {}).get(class_name)) is not None]
                if scores:
                    subject_averages[subject_name] = round(sum(scores) / len(scores), 1)

            sorted_subjects_by_avg = sorted(subject_averages.items(), key=lambda item: item[1], reverse=True)
            subject_ranks = { name: rank + 1 for rank, (name, avg) in enumerate(sorted_subjects_by_avg) }
            sorted_subjects_list = sorted(list(all_subjects))

            chart_datasets = [{
                'label': class_name,
                'data': [table_data.get(subject_name, {}).get(class_name, 0) for subject_name in sorted_subjects_list]
            } for class_name in all_classes]

            sorted_table_data = {subject: table_data.get(subject, {}) for subject in sorted_subjects_list}

            context.update({
                'has_results': True,
                'table_headers': all_classes,
                'table_data': sorted_table_data,
                'subject_averages': subject_averages,
                'subject_ranks': subject_ranks,
                'chart_labels': json.dumps(sorted_subjects_list, ensure_ascii=False),
                'chart_datasets': json.dumps(chart_datasets, ensure_ascii=False),
            })

    context['selected_class_ids_json'] = json.dumps(selected_class_ids_str)
    context['selected_subject_ids_json'] = json.dumps(selected_subject_ids_str)

    return render(request, 'analysis.html', context)