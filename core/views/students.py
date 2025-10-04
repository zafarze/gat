# D:\New_GAT\core\views\students.py (ФИНАЛЬНАЯ ВЕРСИЯ С ПРАВАМИ ДОСТУПА И БЕЗОПАСНОСТЬЮ)

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from collections import defaultdict
from .. import utils

from ..models import Student, School, SchoolClass, StudentResult, ClassSubject, Subject
from ..forms import StudentForm, StudentUploadForm
from ..services import process_student_excel
from .permissions import get_accessible_schools # <--- Подключаем нашу "умную" функцию

# --- СПИСОК УЧЕНИКОВ С УЧЕТОМ ПРАВ ---
class StudentListView(LoginRequiredMixin, ListView):
    model = Student
    template_name = 'students/student_list.html'
    context_object_name = 'students'
    paginate_by = 50

    def get_queryset(self):
        queryset = super().get_queryset().select_related('school_class__school')
        user = self.request.user

        # --- ОБНОВЛЕННЫЙ ФИЛЬТР ДЛЯ ДИРЕКТОРА ---
        if not user.is_superuser:
            accessible_schools = get_accessible_schools(user)
            queryset = queryset.filter(school_class__school__in=accessible_schools)
        # --- КОНЕЦ ФИЛЬТРА ---

        school_id = self.request.GET.get('school')
        class_id = self.request.GET.get('class')
        if school_id: queryset = queryset.filter(school_class__school_id=school_id)
        if class_id: queryset = queryset.filter(school_class_id=class_id)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Список учеников'
        
        # --- ОБНОВЛЕНИЕ ФИЛЬТРА ШКОЛ ДЛЯ ДИРЕКТОРА ---
        if not self.request.user.is_superuser:
            context['schools'] = get_accessible_schools(self.request.user)
        else:
            context['schools'] = School.objects.all()
        # --- КОНЕЦ ОБНОВЛЕНИЯ ---
            
        context['selected_school'] = self.request.GET.get('school')
        context['selected_class'] = self.request.GET.get('class')
        return context

# --- ОПЕРАЦИИ СО СТУДЕНТАМИ (ТОЛЬКО ДЛЯ АДМИНА) ---
class StudentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Student; form_class = StudentForm; template_name = 'students/student_form.html'; success_url = reverse_lazy('student_list')
    extra_context = {'title': 'Добавить ученика', 'cancel_url': 'student_list'}
    
    def test_func(self): return self.request.user.is_superuser

class StudentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Student; form_class = StudentForm; template_name = 'students/student_form.html'; success_url = reverse_lazy('student_list')
    extra_context = {'title': 'Редактировать ученика', 'cancel_url': 'student_list'}
    
    def test_func(self): return self.request.user.is_superuser

class StudentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Student; template_name = 'students/student_confirm_delete.html'; success_url = reverse_lazy('student_list')
    extra_context = {'title': 'Удалить ученика'}

    def test_func(self): return self.request.user.is_superuser

# --- ЗАГРУЗКА ИЗ EXCEL (ТОЛЬКО ДЛЯ АДМИНА) ---
@login_required
def student_upload_view(request):
    # --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ ---
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect('student_list')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---

    if request.method == 'POST':
        form = StudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            report = process_student_excel(request.FILES['file'])
            if 'error' in report: messages.error(request, report['error'])
            else:
                messages.success(request, f"Обработано: {report['processed_count']}. Создано: {report['created_count']}. Обновлено: {report['updated_count']}.")
                if report['errors']:
                    for error in report['errors']: messages.warning(request, error)
            return redirect('student_upload')
    else:
        form = StudentUploadForm()
    return render(request, 'students/student_upload_form.html', {'title': 'Загрузить учеников из Excel', 'form': form})

# --- СТРАНИЦА ПРОГРЕССА СТУДЕНТА С ПРОВЕРКОЙ ДОСТУПА ---
def _get_grade_and_subjects_performance(result, subject_map):
    # Эта вспомогательная функция не требует изменений
    class_subjects = ClassSubject.objects.filter(school_class__in=[result.gat_test.school_class, result.gat_test.school_class.parent], subject_id__in=result.scores.keys()).distinct('subject_id')
    max_score = sum(cs.number_of_questions for cs in class_subjects)
    if max_score == 0: return 0, None, None
    student_score = sum(sum(ans) for ans in result.scores.values())
    percentage = (student_score / max_score) * 100 if max_score > 0 else 0
    grade = utils.calculate_grade_from_percentage(percentage)
    subject_performance = []
    for subj_id_str, answers in result.scores.items():
        subj_id = int(subj_id_str)
        total_q, correct_q = len(answers), sum(answers)
        if total_q > 0:
            perf = (correct_q / total_q) * 100
            subject_performance.append({'name': subject_map.get(subj_id), 'perf': perf})
    if not subject_performance: return grade, None, None
    best_subject = max(subject_performance, key=lambda x: x['perf'])
    worst_subject = min(subject_performance, key=lambda x: x['perf'])
    return grade, best_subject, worst_subject

@login_required
def student_progress_view(request, student_id):
    student = get_object_or_404(Student.objects.select_related('school_class__school').prefetch_related('notes__author'), id=student_id)
    user = request.user

    # --- УЛУЧШЕНИЕ БЕЗОПАСНОСТИ: ПРОВЕРКА ДОСТУПА ДЛЯ ДИРЕКТОРА ---
    if not user.is_superuser:
        accessible_schools = get_accessible_schools(user)
        if student.school_class.school not in accessible_schools:
            messages.error(request, "У вас нет доступа к данным этого ученика.")
            return redirect('student_list')
    # --- КОНЕЦ УЛУЧШЕНИЯ ---
    
    # ... (остальная часть функции остается без изменений) ...
    student_results_qs = student.results.select_related('gat_test__quarter__year', 'gat_test__school_class__parent', 'gat_test__school_class__school').order_by('-gat_test__test_date')
    if not student_results_qs:
        return render(request, 'students/student_progress.html', {'title': f'Аналитика: {student}', 'student': student, 'detailed_results_data': [], 'notes': student.notes.all()})
    
    test_ids = [r.gat_test_id for r in student_results_qs]
    all_results_for_tests = StudentResult.objects.filter(gat_test_id__in=test_ids)
    scores_by_test = defaultdict(list)
    scores_by_class = defaultdict(lambda: defaultdict(list))
    scores_by_school = defaultdict(lambda: defaultdict(list))
    for res in all_results_for_tests.select_related('student__school_class__school'):
        score = sum(sum(a) for a in res.scores.values() if isinstance(a, list))
        scores_by_test[res.gat_test_id].append(score)
        scores_by_class[res.gat_test_id][res.student.school_class_id].append(score)
        scores_by_school[res.gat_test_id][res.student.school_class.school_id].append(score)
    for test_id in scores_by_test:
        scores_by_test[test_id].sort(reverse=True)
        for class_id in scores_by_class[test_id]: scores_by_class[test_id][class_id].sort(reverse=True)
        for school_id in scores_by_school[test_id]: scores_by_school[test_id][school_id].sort(reverse=True)
    
    subject_map = {s.id: s.name for s in Subject.objects.all()}
    detailed_results_data = []
    for result in student_results_qs:
        gat_test = result.gat_test
        student_score = sum(sum(a) for a in result.scores.values())
        class_scores = scores_by_class.get(gat_test.id, {}).get(student.school_class_id, [])
        parallel_scores = scores_by_test.get(gat_test.id, [])
        school_scores = scores_by_school.get(gat_test.id, {}).get(gat_test.school_class.school_id, [])
        try: class_rank = class_scores.index(student_score) + 1
        except ValueError: class_rank = None
        try: parallel_rank = parallel_scores.index(student_score) + 1
        except ValueError: parallel_rank = None
        try: school_rank = school_scores.index(student_score) + 1
        except ValueError: school_rank = None
        grade, best_s, worst_s = _get_grade_and_subjects_performance(result, subject_map)
        processed_scores = []
        if isinstance(result.scores, dict):
            for sid_str, ans in result.scores.items():
                subject_name = subject_map.get(int(sid_str))
                if subject_name:
                    total_q, correct_q = len(ans), sum(ans)
                    percentage = round((correct_q / total_q) * 100, 1) if total_q > 0 else 0
                    processed_scores.append({'subject': subject_name, 'answers': ans, 'correct': correct_q, 'incorrect': total_q - correct_q, 'percentage': percentage, 'grade': utils.calculate_grade_from_percentage(percentage)})
        detailed_results_data.append({'result': result, 'class_rank': class_rank, 'class_total': len(class_scores), 'parallel_rank': parallel_rank, 'parallel_total': len(parallel_scores), 'school_rank': school_rank, 'school_total': len(school_scores), 'grade': grade, 'best_subject': best_s, 'worst_subject': worst_s, 'processed_scores': processed_scores})
        
    comparison_data = None
    if len(detailed_results_data) >= 2:
        latest, previous = detailed_results_data[0], detailed_results_data[1]
        comparison_data = {'latest': latest, 'previous': previous, 'grade_diff': latest['grade'] - previous['grade'], 'rank_diff': (previous.get('class_rank') - latest.get('class_rank')) if previous.get('class_rank') and latest.get('class_rank') else None}
    
    context = {'title': f'Аналитика: {student}', 'student': student, 'detailed_results_data': detailed_results_data, 'comparison_data': comparison_data, 'notes': student.notes.all()}
    return render(request, 'students/student_progress.html', context)