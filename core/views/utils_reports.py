# D:\New_GAT\core\views\utils_reports.py

from collections import defaultdict
from accounts.models import UserProfile
from core.forms import MonitoringFilterForm
from core.models import StudentResult, SchoolClass, Subject, QuestionCount
from core.views.permissions import get_accessible_schools
from core import utils as grade_utils

def get_report_context(get_params, request_user, mode='monitoring'):
    """
    Единая функция для получения данных для Мониторинга и Таблицы Оценок.
    Учитывает права доступа и предоставляет полные данные по баллам (балл/всего).
    """
    user = request_user
    profile = getattr(user, 'profile', None)
    form = MonitoringFilterForm(get_params or None, user=user)

    table_headers = []
    table_rows = []
    title_details = {}
    accessible_subjects_for_user = None

    accessible_schools = get_accessible_schools(user)
    results_qs = StudentResult.objects.filter(
        student__school_class__school__in=accessible_schools
    ).select_related('student__school_class__school', 'gat_test')

    is_expert = profile and profile.role == UserProfile.Role.EXPERT
    is_teacher_or_homeroom = profile and profile.role in [UserProfile.Role.TEACHER, UserProfile.Role.HOMEROOM_TEACHER]

    # Ограничение по предметам в зависимости от роли
    if is_expert:
        accessible_subjects_for_user = profile.subjects.all()
        expert_subject_ids_int = list(accessible_subjects_for_user.values_list('id', flat=True))
        expert_subject_id_keys = [str(sid) for sid in expert_subject_ids_int]
        if expert_subject_id_keys:
            results_qs = results_qs.filter(scores_by_subject__has_any_keys=expert_subject_id_keys)
        else:
            results_qs = results_qs.none()
    elif is_teacher_or_homeroom:
        accessible_subjects_for_user = profile.subjects.all()
        teacher_subject_ids_int = list(accessible_subjects_for_user.values_list('id', flat=True))
        teacher_subject_id_keys = [str(sid) for sid in teacher_subject_ids_int]
        if teacher_subject_id_keys:
            results_qs = results_qs.filter(scores_by_subject__has_any_keys=teacher_subject_id_keys)
        else:
            results_qs = results_qs.none()

    if form.is_valid():
        subjects_filter_from_form = form.cleaned_data.get('subjects')
        subjects_filter_for_query = Subject.objects.none()

        # Определяем предметы для фильтрации с учетом прав пользователя
        if accessible_subjects_for_user is not None:
            if subjects_filter_from_form.exists():
                subjects_filter_for_query = subjects_filter_from_form.filter(
                    id__in=accessible_subjects_for_user.values_list('id', flat=True)
                )
            else:
                subjects_filter_for_query = accessible_subjects_for_user
        elif subjects_filter_from_form.exists():
            subjects_filter_for_query = subjects_filter_from_form

        # Применяем фильтры из формы
        if quarters := form.cleaned_data.get('quarters'):
            results_qs = results_qs.filter(gat_test__quarter__in=quarters)
            title_details['period'] = ", ".join([str(q) for q in quarters])
        if schools := form.cleaned_data.get('schools'):
            results_qs = results_qs.filter(student__school_class__school__in=schools)
            title_details['schools'] = ", ".join([s.name for s in schools])
        if school_classes := form.cleaned_data.get('school_classes'):
            selected_class_ids = list(school_classes.values_list('id', flat=True))
            subclass_ids = list(SchoolClass.objects.filter(parent__in=selected_class_ids).values_list('id', flat=True))
            all_relevant_class_ids = set(selected_class_ids + subclass_ids)
            results_qs = results_qs.filter(student__school_class_id__in=all_relevant_class_ids)
            title_details['classes'] = ", ".join([c.name for c in school_classes])
        if test_numbers := form.cleaned_data.get('test_numbers'):
            results_qs = results_qs.filter(gat_test__test_number__in=test_numbers)
            title_details['test_type'] = ", ".join([f"GAT-{num}" for num in test_numbers])
        if days := form.cleaned_data.get('days'):
            results_qs = results_qs.filter(gat_test__day__in=days)

        # Финальная фильтрация по предметам
        if subjects_filter_for_query.exists():
            subject_keys = [str(s.id) for s in subjects_filter_for_query]
            results_qs = results_qs.filter(scores_by_subject__has_any_keys=subject_keys)
        elif not subjects_filter_for_query.exists() and accessible_subjects_for_user is not None:
            results_qs = results_qs.none()

        # Определение предметов для заголовков таблицы
        subject_map = {s.id: s for s in Subject.objects.all()}
        header_subjects = []
        if accessible_subjects_for_user is not None:
            header_subjects = sorted(list(subjects_filter_for_query), key=lambda s: s.name)
        elif subjects_filter_from_form.exists():
            header_subjects = sorted(list(subjects_filter_from_form), key=lambda s: s.name)
        else:
            all_subject_ids_in_results = set()
            for r in results_qs:
                if isinstance(r.scores_by_subject, dict):
                    all_subject_ids_in_results.update(int(sid) for sid in r.scores_by_subject.keys())
            header_subjects = sorted([subject_map[sid] for sid in all_subject_ids_in_results if sid in subject_map], 
                                   key=lambda s: s.name)

        # Расчет количества вопросов
        q_counts = {}
        if results_qs.exists() and header_subjects:
            ref_classes_qs = SchoolClass.objects.filter(
                id__in=results_qs.values_list('student__school_class_id', flat=True).distinct()
            ).select_related('parent')
            
            all_class_ids_for_qc = set(ref_classes_qs.values_list('id', flat=True)) | set(
                ref_classes_qs.exclude(parent__isnull=True).values_list('parent_id', flat=True)
            )

            question_counts_qs = QuestionCount.objects.filter(
                school_class_id__in=all_class_ids_for_qc,
                subject__in=header_subjects
            )
            
            q_counts_map = defaultdict(dict)
            for qc in question_counts_qs:
                q_counts_map[qc.subject_id][qc.school_class_id] = qc.number_of_questions

            for subj in header_subjects:
                for cls in ref_classes_qs:
                    if cls.id in q_counts_map.get(subj.id, {}):
                        q_counts[(subj.id, cls.id)] = q_counts_map[subj.id][cls.id]
                    elif cls.parent_id and cls.parent_id in q_counts_map.get(subj.id, {}):
                        q_counts[(subj.id, cls.id)] = q_counts_map[subj.id][cls.parent_id]

        # Формирование заголовков таблицы
        for subj in header_subjects:
            representative_q_count = q_counts.get(
                (subj.id, ref_classes_qs.first().id if ref_classes_qs.exists() else 0), 0
            )
            table_headers.append({'subject': subj, 'q_count': representative_q_count})

        # Формирование строк таблицы
        for result in results_qs.distinct():
            if not (result.student and isinstance(result.scores_by_subject, dict)): 
                continue
                
            row_data = {
                'student': result.student,
                'result_obj': result,
                'scores_by_subject': {},
                'grades_by_subject': {},
                'total_score': 0
            }
            total_grade_points, subjects_in_row = 0, 0

            for header in table_headers:
                header_subject = header['subject']
                subject_id, subject_id_str = header_subject.id, str(header_subject.id)
                answers = result.scores_by_subject.get(subject_id_str)
                q_count = q_counts.get((subject_id, result.student.school_class_id), 0)

                if answers is not None and isinstance(answers, dict):
                    score = sum(1 for v in answers.values() if v is True)
                    row_data['total_score'] += score
                    subjects_in_row += 1
                    
                    if mode == 'grading':
                        percentage = (score / q_count) * 100 if q_count > 0 else 0
                        grade = grade_utils.calculate_grade_from_percentage(percentage)
                        row_data['grades_by_subject'][subject_id] = grade
                        total_grade_points += grade
                    else:
                        row_data['scores_by_subject'][subject_id] = {'score': score, 'total': q_count}
                else:
                    if mode == 'grading':
                         row_data['grades_by_subject'][subject_id] = "—"
                    else:
                         row_data['scores_by_subject'][subject_id] = {'score': '—', 'total': q_count}

            if mode == 'grading':
                 row_data['total_score'] = total_grade_points if subjects_in_row > 0 else 0
            table_rows.append(row_data)

        # Сортировка результатов
        table_rows.sort(
            key=lambda x: (
                isinstance(x.get('total_score'), str),
                -x.get('total_score', 0) if not isinstance(x.get('total_score'), str) else 0
            ), 
            reverse=False
        )

    return {
        'form': form,
        'table_headers': table_headers,
        'table_rows': table_rows,
        'has_results': bool(get_params) and form.is_valid(),
        'title_details': title_details,
        'accessible_subjects_for_user': accessible_subjects_for_user,
    }