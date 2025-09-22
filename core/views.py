# core/views.py (ПОЛНАЯ И УЛУЧШЕННАЯ ВЕРСИЯ)

from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.db.models import Count 
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Count
from django.template.loader import render_to_string
from openpyxl import Workbook
from weasyprint import HTML
from .models import School, Student, GatTest, StudentResult
import json
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from .models import GatTest
from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    ClassSubject, GatTest, Student, StudentResult, UserProfile
)
from django.db.models import Sum
from .forms import ProfileUpdateForm, CustomPasswordChangeForm, EmailChangeForm
from django.contrib.auth import update_session_auth_hash
from django.db.models import Count, Avg
import json
from .forms import (
    AcademicYearForm, QuarterForm, SchoolForm, SchoolClassForm, SubjectForm,
    ClassSubjectForm, GatTestForm, UploadFileForm, GatTestCompareForm
)
from django.db.models import F
from .forms import DeepAnalysisForm
from . import services
from .models import StudentResult, Subject


# --- АУТЕНТИФИКАЦИЯ И ОСНОВНЫЕ СТРАНИЦЫ ---

def login_view(request):
    """Обрабатывает вход пользователя в систему."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, "Неверный email или пароль.")
            return render(request, 'index.html', {'error': "Неверный email или пароль."})
    return render(request, 'index.html')

@login_required
def logout_view(request):
    """Выход пользователя из системы."""
    logout(request)
    messages.info(request, "Вы успешно вышли из системы.")
    return redirect('login')

@login_required
def dashboard_view(request):
    """
    Отображает главную панель управления с расширенной аналитикой.
    (НОВАЯ, ПЕРЕРАБОТАННАЯ ВЕРСИЯ)
    """
    # --- 1. Основные KPI ---
    school_count = School.objects.count()
    student_count = Student.objects.count()
    test_count = GatTest.objects.count()
    result_count = StudentResult.objects.count()

    # --- 2. Данные для графика "Рейтинг школ" ---
    # Считаем средний балл для каждой школы
    school_scores = defaultdict(lambda: {'total_score': 0, 'count': 0})
    all_results = StudentResult.objects.all()
    for result in all_results:
        school_name = result.student.school_class.school.name
        total_score = sum(sum(answers) for answers in result.scores.values())
        school_scores[school_name]['total_score'] += total_score
        school_scores[school_name]['count'] += 1

    school_performance = []
    for name, data in school_scores.items():
        avg = round(data['total_score'] / data['count'], 1) if data['count'] > 0 else 0
        school_performance.append({'name': name, 'avg_score': avg})
    
    # Сортируем и берем топ-10
    school_performance.sort(key=lambda x: x['avg_score'], reverse=True)
    top_schools = school_performance[:10]
    
    school_chart_labels = json.dumps([s['name'] for s in top_schools], ensure_ascii=False)
    school_chart_data = json.dumps([s['avg_score'] for s in top_schools])

    # --- 3. Данные для графика "Активность по четвертям" ---
    quarter_activity = Quarter.objects.annotate(
        num_results=Count('gattests__student_results')
    ).filter(num_results__gt=0).order_by('year__start_date', 'start_date')
    
    quarter_chart_labels = json.dumps([str(q) for q in quarter_activity], ensure_ascii=False)
    quarter_chart_data = json.dumps([q.num_results for q in quarter_activity])

    # --- 4. Динамические списки ---
    # Недавние загрузки (5 последних тестов с результатами)
    recent_test_ids = StudentResult.objects.order_by('-id').values_list('gat_test_id', flat=True).distinct()[:5]
    recent_tests = GatTest.objects.filter(id__in=list(recent_test_ids)).select_related('school_class')

    # Тесты, ожидающие загрузки результатов
    tests_without_results = GatTest.objects.annotate(
        num_results=Count('student_results')
    ).filter(num_results=0).select_related('school_class').order_by('-test_date')[:5]

    context = {
        'title': 'Панель управления',
        # KPI Карточки
        'school_count': school_count,
        'student_count': student_count,
        'test_count': test_count,
        'result_count': result_count,
        # Графики
        'school_chart_labels': school_chart_labels,
        'school_chart_data': school_chart_data,
        'quarter_chart_labels': quarter_chart_labels,
        'quarter_chart_data': quarter_chart_data,
        # Списки
        'recent_tests': recent_tests,
        'tests_without_results': tests_without_results,
    }
    return render(request, 'dashboard.html', context)

@login_required
def management_view(request):
    """Отображает страницу со ссылками на разделы управления."""
    return render(request, 'management.html', {'title': 'Управление'})


# --- УПРАВЛЕНИЕ (CRUD) С ИСПОЛЬЗОВАНИЕМ CLASS-BASED VIEWS ---

class AcademicYearListView(LoginRequiredMixin, ListView):
    model = AcademicYear
    template_name = 'years/list.html'
    context_object_name = 'items'
    extra_context = {'title': 'Учебные Годы', 'add_url': 'year_add', 'edit_url': 'year_edit', 'delete_url': 'year_delete'}

class AcademicYearCreateView(LoginRequiredMixin, CreateView):
    model = AcademicYear; form_class = AcademicYearForm; template_name = 'years/form.html'; success_url = reverse_lazy('year_list')
    extra_context = {'title': 'Добавить Учебный Год', 'cancel_url': 'year_list'}

class AcademicYearUpdateView(LoginRequiredMixin, UpdateView):
    model = AcademicYear; form_class = AcademicYearForm; template_name = 'years/form.html'; success_url = reverse_lazy('year_list')
    extra_context = {'title': 'Редактировать Учебный Год', 'cancel_url': 'year_list'}

class AcademicYearDeleteView(LoginRequiredMixin, DeleteView):
    model = AcademicYear; template_name = 'years/confirm_delete.html'; success_url = reverse_lazy('year_list')
    extra_context = {'title': 'Удалить Учебный Год', 'cancel_url': 'year_list'}

class QuarterListView(LoginRequiredMixin, ListView):
    model = Quarter; template_name = 'quarters/list.html'; context_object_name = 'items'
    extra_context = {'title': 'Четверти', 'add_url': 'quarter_add', 'edit_url': 'quarter_edit', 'delete_url': 'quarter_delete'}

class QuarterCreateView(LoginRequiredMixin, CreateView):
    model = Quarter; form_class = QuarterForm; template_name = 'quarters/form.html'; success_url = reverse_lazy('quarter_list')
    extra_context = {'title': 'Добавить Четверть', 'cancel_url': 'quarter_list'}

class QuarterUpdateView(LoginRequiredMixin, UpdateView):
    model = Quarter; form_class = QuarterForm; template_name = 'quarters/form.html'; success_url = reverse_lazy('quarter_list')
    extra_context = {'title': 'Редактировать Четверть', 'cancel_url': 'quarter_list'}

class QuarterDeleteView(LoginRequiredMixin, DeleteView):
    model = Quarter; template_name = 'quarters/confirm_delete.html'; success_url = reverse_lazy('quarter_list')
    extra_context = {'title': 'Удалить Четверть', 'cancel_url': 'quarter_list'}

class SchoolListView(LoginRequiredMixin, ListView):
    model = School; template_name = 'schools/list.html'; context_object_name = 'items'
    extra_context = {'title': 'Школы', 'add_url': 'school_add', 'edit_url': 'school_edit', 'delete_url': 'school_delete'}

class SchoolCreateView(LoginRequiredMixin, CreateView):
    model = School; form_class = SchoolForm; template_name = 'schools/form.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Добавить Школу', 'cancel_url': 'school_list'}

class SchoolUpdateView(LoginRequiredMixin, UpdateView):
    model = School; form_class = SchoolForm; template_name = 'schools/form.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Редактировать Школу', 'cancel_url': 'school_list'}

class SchoolDeleteView(LoginRequiredMixin, DeleteView):
    model = School; template_name = 'schools/confirm_delete.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Удалить Школу', 'cancel_url': 'school_list'}
    
class SchoolClassListView(LoginRequiredMixin, ListView):
    # Теперь мы будем получать список ШКОЛ, а не классов
    model = School 
    template_name = 'classes/list.html'
    # Переименуем переменную в шаблоне для ясности
    context_object_name = 'schools' 
    extra_context = {
        'title': 'Классы по школам', 
        'add_url': 'class_add', 
        'edit_url': 'class_edit', 
        'delete_url': 'class_delete'
    }

    def get_queryset(self):
        # Получаем школы и сразу "подтягиваем" все связанные с ними классы
        # Это делается для оптимизации, чтобы избежать лишних запросов к базе данных
        return School.objects.prefetch_related('classes').order_by('name')

class SchoolClassCreateView(LoginRequiredMixin, CreateView):
    model = SchoolClass
    form_class = SchoolClassForm
    template_name = 'classes/form.html'
    success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Добавить Класс', 'cancel_url': 'class_list'}

    # Этот метод автоматически подставит нужную школу в форму,
    # когда вы нажмете кнопку "+ Добавить класс" у конкретной школы
    def get_initial(self):
        initial = super().get_initial()
        school_id = self.request.GET.get('school')
        if school_id:
            initial['school'] = school_id
        return initial

class SchoolClassUpdateView(LoginRequiredMixin, UpdateView):
    model = SchoolClass; form_class = SchoolClassForm; template_name = 'classes/form.html'; success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Редактировать Класс', 'cancel_url': 'class_list'}

class SchoolClassDeleteView(LoginRequiredMixin, DeleteView):
    model = SchoolClass; template_name = 'classes/confirm_delete.html'; success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Удалить Класс', 'cancel_url': 'class_list'}

class SubjectListView(LoginRequiredMixin, ListView):
    model = Subject; template_name = 'subjects/list.html'; context_object_name = 'items'
    extra_context = {'title': 'Предметы', 'add_url': 'subject_add', 'edit_url': 'subject_edit', 'delete_url': 'subject_delete'}

class SubjectCreateView(LoginRequiredMixin, CreateView):
    model = Subject; form_class = SubjectForm; template_name = 'subjects/form.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Добавить Предмет', 'cancel_url': 'subject_list'}

class SubjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Subject; form_class = SubjectForm; template_name = 'subjects/form.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Редактировать Предмет', 'cancel_url': 'subject_list'}

class SubjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Subject; template_name = 'subjects/confirm_delete.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Удалить Предмет', 'cancel_url': 'subject_list'}

class ClassSubjectListView(LoginRequiredMixin, ListView):
    model = SchoolClass; template_name = 'class_subjects/list.html'; context_object_name = 'classes'
    extra_context = {'title': 'Учебный план', 'add_url': 'class_subject_add', 'edit_url': 'class_subject_edit', 'delete_url': 'class_subject_delete'}
    def get_queryset(self):
        return SchoolClass.objects.annotate(num_subjects=Count('subjects')).filter(num_subjects__gt=0).prefetch_related('classsubject_set__subject').order_by('school__name', 'name')

class ClassSubjectCreateView(LoginRequiredMixin, CreateView):
    model = ClassSubject; form_class = ClassSubjectForm; template_name = 'class_subjects/form.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Добавить предмет в класс', 'cancel_url': 'class_subject_list'}

class ClassSubjectUpdateView(LoginRequiredMixin, UpdateView):
    model = ClassSubject; form_class = ClassSubjectForm; template_name = 'class_subjects/form.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Редактировать предмет в классе', 'cancel_url': 'class_subject_list'}

class ClassSubjectDeleteView(LoginRequiredMixin, DeleteView):
    model = ClassSubject; template_name = 'class_subjects/confirm_delete.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Удалить предмет из класса', 'cancel_url': 'class_subject_list'}


# --- GAT ТЕСТЫ ---

@login_required
def gat_test_list_view(request):
    """Отображает список GAT тестов, сгруппированных по школам."""
    grouped_tests = defaultdict(list)
    tests = GatTest.objects.select_related('school_class__school', 'quarter').prefetch_related('subjects').order_by('school_class__school__name', 'name')
    for test in tests:
        grouped_tests[test.school_class.school].append(test)
    
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    context = {
        'grouped_tests': dict(grouped_tests),
        'title': 'GAT Тесты',
        'add_url': 'gat_test_add', # URL для кнопки "Добавить"
        'edit_url': 'gat_test_edit', # URL для кнопки "Редактировать"
        'delete_url': 'gat_test_delete', # URL для кнопки "Удалить"
    }
    # --- КОНЕЦ ИСПРАВЛЕНИЯ ---

    return render(request, 'gat_tests/list.html', context)

class GatTestCreateView(LoginRequiredMixin, CreateView):
    model = GatTest; form_class = GatTestForm; template_name = 'gat_tests/form.html'; success_url = reverse_lazy('gat_test_list')
    extra_context = {'title': 'Назначить GAT Тест', 'cancel_url': 'gat_test_list'}

class GatTestUpdateView(LoginRequiredMixin, UpdateView):
    model = GatTest; form_class = GatTestForm; template_name = 'gat_tests/form.html'; success_url = reverse_lazy('gat_test_list')
    extra_context = {'title': 'Редактировать GAT Тест', 'cancel_url': 'gat_test_list'}

class GatTestDeleteView(LoginRequiredMixin, DeleteView):
    model = GatTest; template_name = 'gat_tests/confirm_delete.html'; success_url = reverse_lazy('gat_test_list')
    extra_context = {'title': 'Удалить GAT Тест', 'cancel_url': 'gat_test_list'}

@login_required
def gat_test_delete_results_view(request, pk):
    gat_test = get_object_or_404(GatTest, pk=pk)
    results_to_delete = gat_test.student_results.all()
    count = results_to_delete.count()
    if request.method == 'POST':
        results_to_delete.delete()
        messages.success(request, f'Все {count} результатов для теста "{gat_test.name}" были успешно удалены.')
        return redirect('gat_test_list')
    context = {'item': gat_test, 'count': count, 'title': f'Удалить результаты для {gat_test.name}', 'cancel_url': 'gat_test_list'}
    return render(request, 'results/confirm_delete_batch.html', context)


# --- РЕЗУЛЬТАТЫ И ОТЧЕТЫ ---

@login_required
def upload_results_view(request):
    """Обрабатывает загрузку Excel файла с результатами."""
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            gat_test = form.cleaned_data['gat_test']
            excel_file = request.FILES['file']
            try:
                report = services.process_excel_results(excel_file, gat_test)
                messages.success(request, f"Успешно обработано {report['processed_count']} результатов.")
                if report['skipped_count'] > 0:
                    messages.warning(request, f"Пропущено {report['skipped_count']} студентов (возможно, из-за несоответствия класса).")
                return redirect('detailed_results_list', test_number=gat_test.test_number)
            except ValueError as e:
                messages.error(request, f'Ошибка в данных файла: {e}')
            except Exception as e:
                messages.error(request, f'Произошла непредвиденная ошибка при обработке файла: {e}')
    else:
        form = UploadFileForm()
    return render(request, 'results/upload_form.html', {'form': form, 'title': 'Загрузка результатов'})

def get_detailed_results_data(test_number, request_get):
    """Вспомогательная функция для получения и фильтрации данных для детальных отчетов."""
    year_id = request_get.get('year'); quarter_id = request_get.get('quarter'); school_id = request_get.get('school'); class_id = request_get.get('class')
    tests_qs = GatTest.objects.filter(test_number=test_number).select_related('quarter__year', 'school_class__school')
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
    students_data, results_map = [], {res.student_id: res for res in student_results}
    students = Student.objects.filter(id__in=results_map.keys()).select_related('school_class')
    for student in students:
        result = results_map.get(student.id)
        total_score = sum(sum(answers) for answers in result.scores.values()) if result and isinstance(result.scores, dict) else 0
        students_data.append({'student': student, 'result': result, 'total_score': total_score})
    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    return students_data, table_header

@login_required
def detailed_results_list_view(request, test_number):
    """Отображает детальный рейтинг GAT-1 или GAT-2."""
    students_data, table_header = get_detailed_results_data(test_number, request.GET)
    context = {
        'title': f'Детальный рейтинг GAT-{test_number}', 'students_data': students_data, 'table_header': table_header,
        'years': AcademicYear.objects.all(), 'schools': School.objects.all(), 'selected_year': request.GET.get('year'),
        'selected_quarter': request.GET.get('quarter'), 'selected_school': request.GET.get('school'),
        'selected_class': request.GET.get('class'), 'test_number': test_number
    }
    return render(request, 'results/detailed_results_list.html', context)



@login_required
def student_result_detail_view(request, pk):
    result = get_object_or_404(StudentResult, pk=pk); subject_map = {s.id: s for s in Subject.objects.all()}; processed_scores = {}
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
    # Сохраняем номер теста для редиректа
    test_number = result.gat_test.test_number
    if request.method == 'POST':
        result.delete()
        messages.success(request, f'Результат для "{result.student}" был успешно удален.')
        return redirect('detailed_results_list', test_number=test_number)
    context = {'item': result, 'title': f'Удалить результат: {result.student}', 'cancel_url': reverse('student_result_detail', kwargs={'pk': pk})}
    return render(request, 'results/confirm_delete_result.html', context)

# --- АРХИВ И СРАВНЕНИЕ ---

@login_required
def archive_years_view(request):
    year_ids_with_results = StudentResult.objects.values_list('gat_test__quarter__year_id', flat=True).distinct()
    years = AcademicYear.objects.filter(id__in=year_ids_with_results)
    context = {'years': years, 'title': 'Архив: Выберите Год'}
    return render(request, 'results/archive_years.html', context)

@login_required
def archive_quarters_view(request, year_id):
    year = get_object_or_404(AcademicYear, id=year_id)
    quarters = Quarter.objects.filter(year=year, gattests__student_results__isnull=False).distinct().order_by('start_date')
    context = {'year': year, 'quarters': quarters, 'title': f'Архив: {year.name}'}
    return render(request, 'results/archive_quarters.html', context)

@login_required
def archive_schools_view(request, quarter_id):
    quarter = get_object_or_404(Quarter, id=quarter_id)
    schools = School.objects.filter(classes__gattests__quarter=quarter, classes__gattests__student_results__isnull=False).distinct().order_by('name')
    context = {'quarter': quarter, 'schools': schools, 'title': f'Архив: {quarter}'}
    return render(request, 'results/archive_schools.html', context)

@login_required
def archive_classes_view(request, quarter_id, school_id):
    quarter = get_object_or_404(Quarter, id=quarter_id)
    school = get_object_or_404(School, id=school_id)
    classes = SchoolClass.objects.filter(school=school, gattests__quarter=quarter, gattests__student_results__isnull=False).distinct().order_by('name')
    context = {'quarter': quarter, 'school': school, 'classes': classes, 'title': f'Архив: {school.name}'}
    return render(request, 'results/archive_classes.html', context)

@login_required
def gat_test_archive_view(request, quarter_id, class_id):
    school_class = get_object_or_404(SchoolClass, id=class_id); quarter = get_object_or_404(Quarter, id=quarter_id)
    tests = GatTest.objects.filter(school_class=school_class, quarter=quarter).annotate(num_results=Count('student_results')).filter(num_results__gt=0).order_by('test_number')
    test1 = tests.filter(test_number=1).first(); test2 = tests.filter(test_number=2).first()
    context = {'school_class': school_class, 'quarter': quarter, 'tests': tests, 'title': f'Тесты для {school_class.name}', 'show_comparison_card': bool(test1 and test2), 'test1': test1, 'test2': test2}
    return render(request, 'results/results_archive.html', context)

# --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
def _get_data_for_test(gat_test):
    """
    (УЛУЧШЕННАЯ ВЕРСИЯ)
    Вспомогательная функция для получения и обработки данных для детальных таблиц.
    """
    if not gat_test:
        return [], []

    # 1. Формируем заголовок таблицы
    table_header = []
    class_subjects = ClassSubject.objects.filter(
        school_class=gat_test.school_class,
        subject__in=gat_test.subjects.all()
    ).select_related('subject').order_by('subject__name')
    
    for cs in class_subjects:
        table_header.append({
            'subject': cs.subject,
            'questions': range(1, cs.number_of_questions + 1)
        })

    # 2. Получаем результаты и сразу "подтягиваем" связанных студентов
    student_results = StudentResult.objects.filter(gat_test=gat_test).select_related('student__school_class')

    # 3. Собираем данные в нужную структуру
    students_data = []
    for result in student_results:
        # Считаем общий балл
        total_score = 0
        if isinstance(result.scores, dict):
            total_score = sum(sum(answers) for answers in result.scores.values() if isinstance(answers, list))
        
        students_data.append({
            'student': result.student,
            'result': result,
            'total_score': total_score,
        })

    # 4. Сортируем итоговый список по общему баллу
    students_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    return students_data, table_header

# --- API ДЛЯ ДИНАМИЧЕСКОЙ ЗАГРУЗКИ (AJAX) ---

@login_required
def load_quarters(request):
    year_id = request.GET.get('year_id')
    quarters = Quarter.objects.filter(year_id=year_id).order_by('name') if year_id else Quarter.objects.none()
    return JsonResponse(list(quarters.values('id', 'name')), safe=False)

@login_required
def load_classes(request):
    school_id = request.GET.get('school_id')
    classes = SchoolClass.objects.filter(school_id=school_id).order_by('name') if school_id else SchoolClass.objects.none()
    return JsonResponse(list(classes.values('id', 'name')), safe=False)

@login_required
def get_previous_subjects_view(request):
    class_id, quarter_id, test_number = request.GET.get('class_id'), request.GET.get('quarter_id'), request.GET.get('test_number')
    if not all([class_id, quarter_id, test_number]): return JsonResponse({'subject_ids': []})
    try:
        previous_test = GatTest.objects.filter(school_class_id=class_id, quarter_id=quarter_id, test_number__lt=int(test_number)).order_by('-test_number').first()
        if previous_test:
            return JsonResponse({'subject_ids': list(previous_test.subjects.values_list('id', flat=True))})
    except (ValueError, TypeError): pass
    return JsonResponse({'subject_ids': []})


# --- ЭКСПОРТ ДАННЫХ ---

@login_required
def export_detailed_results_excel(request, test_number):
    """Экспортирует детальный отчет в Excel."""
    students_data, table_header = get_detailed_results_data(test_number, request.GET)
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="gat_{test_number}_results.xlsx"'
    workbook = Workbook(); sheet = workbook.active; sheet.title = f'GAT-{test_number} Результаты'
    headers = ["№", "ФИО", "Класс"]
    for header in table_header:
        for q_num in header['questions']: headers.append(f"{header['subject'].abbreviation}_{q_num}")
    headers.append("Итог")
    sheet.append(headers)
    for i, data in enumerate(students_data, 1):
        row = [i, str(data['student']), data['student'].school_class.name]
        for header in table_header:
            answers = data['result'].scores.get(str(header['subject'].id), [])
            for q_num_index in range(len(header['questions'])):
                row.append(1 if q_num_index < len(answers) and answers[q_num_index] else 0)
        row.append(data['total_score'])
        sheet.append(row)
    workbook.save(response)
    return response

@login_required
def export_detailed_results_pdf(request, test_number):
    """Экспортирует детальный отчет в PDF."""
    students_data, table_header = get_detailed_results_data(test_number, request.GET)
    html_string = render_to_string('results/detailed_results_pdf.html', {'students_data': students_data, 'table_header': table_header, 'title': f'Детальный рейтинг GAT-{test_number}'})
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="gat_{test_number}_results.pdf"'
    HTML(string=html_string).write_pdf(response)
    return response

@login_required
def class_results_view(request, quarter_id, class_id):
    """
    Отображает итоговую страницу с результатами GAT-1, GAT-2 и общим баллом
    для конкретного класса в рамках одной четверти.
    """
    school_class = get_object_or_404(SchoolClass, id=class_id)
    quarter = get_object_or_404(Quarter, id=quarter_id)

    # Находим всех студентов в этом классе
    students_in_class = Student.objects.filter(school_class=school_class)

    # Находим результаты GAT-1 и GAT-2 для этих студентов ИМЕННО в этой четверти
    results_gat1 = StudentResult.objects.filter(
        student__in=students_in_class,
        gat_test__test_number=1,
        gat_test__quarter=quarter
    )
    results_gat2 = StudentResult.objects.filter(
        student__in=students_in_class,
        gat_test__test_number=2,
        gat_test__quarter=quarter
    )

    # Преобразуем результаты в удобный словарь для быстрого доступа
    scores_map1 = {res.student_id: sum(sum(ans) for ans in res.scores.values()) for res in results_gat1}
    scores_map2 = {res.student_id: sum(sum(ans) for ans in res.scores.values()) for res in results_gat2}

    # Собираем итоговый список студентов с их баллами
    student_final_list = []
    for student in students_in_class:
        score1 = scores_map1.get(student.id) # Используем .get() для отсутствующих результатов
        score2 = scores_map2.get(student.id)
        
        # Считаем общий балл, только если есть оба результата
        total_score = None
        if score1 is not None and score2 is not None:
            total_score = score1 + score2

        student_final_list.append({
            'student': student,
            'score1': score1,
            'score2': score2,
            'total_score': total_score,
        })

    # Сортируем список по общему баллу (сначала те, у кого есть балл)
    student_final_list.sort(key=lambda x: (x['total_score'] is None, -x['total_score'] if x['total_score'] is not None else 0))

    context = {
        'title': f'Итоговый рейтинг: {school_class.name}',
        'school_class': school_class,
        'quarter': quarter,
        'students_data': student_final_list,
    }
    return render(request, 'results/class_results.html', context)


@login_required
def class_results_dashboard_view(request, quarter_id, class_id):
    """
    Отображает страницу-дэшборд с результатами класса.
    ОПТИМИЗИРОВАННАЯ ВЕРСЯ: Использует _get_data_for_test для всех вкладок
    и собирает итоговые данные без лишних запросов к БД.
    """
    school_class = get_object_or_404(SchoolClass, id=class_id)
    quarter = get_object_or_404(Quarter, id=quarter_id)

    test_gat1 = GatTest.objects.filter(school_class=school_class, quarter=quarter, test_number=1).first()
    test_gat2 = GatTest.objects.filter(school_class=school_class, quarter=quarter, test_number=2).first()

    # 1. Получаем детальные данные для GAT-1 и GAT-2
    # Эта функция возвращает данные в правильной структуре для detailed_table.html
    students_data_gat1, table_header_gat1 = _get_data_for_test(test_gat1)
    students_data_gat2, table_header_gat2 = _get_data_for_test(test_gat2)

    # 2. Собираем данные для итоговой вкладки (Total) без лишних запросов к БД
    all_students_map = {}

    # Сначала проходим по результатам GAT-1
    for data in students_data_gat1:
        student = data['student']
        if student.id not in all_students_map:
            # Если студента еще нет в нашем словаре, добавляем его
            all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score1'] = data['total_score']

    # Затем по результатам GAT-2, обновляя или добавляя студентов
    for data in students_data_gat2:
        student = data['student']
        if student.id not in all_students_map:
            all_students_map[student.id] = {'student': student, 'score1': None, 'score2': None}
        all_students_map[student.id]['score2'] = data['total_score']
    
    # Теперь преобразуем словарь в итоговый список
    students_data_total = []
    for student_id, data in all_students_map.items():
        score1 = data.get('score1')
        score2 = data.get('score2')
        total_score = None
        # Считаем сумму, даже если один из тестов пропущен
        if score1 is not None or score2 is not None:
             total_score = (score1 or 0) + (score2 or 0)
        
        students_data_total.append({
            'student': data['student'], 'score1': score1, 'score2': score2, 'total_score': total_score,
        })
    
    # Сортируем итоговый список по общему баллу
    students_data_total.sort(key=lambda x: (x['total_score'] is None, -x.get('total_score', 0) if x.get('total_score') is not None else 0))

    context = {
        'title': f'Отчет: {school_class.name}',
        'school_class': school_class,
        'quarter': quarter,
        # Данные для вкладки "Итоговый рейтинг"
        'students_data_total': students_data_total,
        # Детальные данные для вкладки GAT-1
        'students_data_gat1': students_data_gat1,
        'table_header_gat1': table_header_gat1,
        # Детальные данные для вкладки GAT-2
        'students_data_gat2': students_data_gat2,
        'table_header_gat2': table_header_gat2,
        # Объекты тестов для проверки их существования в шаблоне
        'test_gat1': test_gat1,
        'test_gat2': test_gat2,
    }
    return render(request, 'results/class_results_dashboard.html', context)

@login_required
def compare_class_tests_view(request, test1_id, test2_id):
    test1 = get_object_or_404(GatTest, id=test1_id)
    test2 = get_object_or_404(GatTest, id=test2_id)
    
    # Существующая логика для итогового рейтинга
    all_student_ids = set(StudentResult.objects.filter(gat_test=test1).values_list('student_id', flat=True)) | set(StudentResult.objects.filter(gat_test=test2).values_list('student_id', flat=True))
    all_students = Student.objects.filter(id__in=all_student_ids)
    results1_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test1)}
    results2_map = {res.student_id: res for res in StudentResult.objects.filter(gat_test=test2)}
    full_scores1 = [{'student': s, 'score': sum(sum(ans) for ans in results1_map[s.id].scores.values()) if s.id in results1_map else 0, 'present': s.id in results1_map} for s in all_students]
    full_scores2 = [{'student': s, 'score': sum(sum(ans) for ans in results2_map[s.id].scores.values()) if s.id in results2_map else 0, 'present': s.id in results2_map} for s in all_students]
    rank_map1 = {item['student'].id: i + 1 for i, item in enumerate(sorted(full_scores1, key=lambda x: x['score'], reverse=True))}
    rank_map2 = {item['student'].id: i + 1 for i, item in enumerate(sorted(full_scores2, key=lambda x: x['score'], reverse=True))}
    comparison_results = []
    for student in all_students:
        is_present1, is_present2 = student.id in results1_map, student.id in results2_map
        rank1, rank2 = rank_map1.get(student.id), rank_map2.get(student.id)
        comparison_results.append({'student': student, 'rank1': rank1 if is_present1 else '—', 'rank2': rank2 if is_present2 else '—', 'avg_rank': (rank1 + rank2) / 2 if is_present1 and is_present2 else float('inf')})
    comparison_results.sort(key=lambda x: x['avg_rank'])

    # Получаем детальные данные для каждого теста
    students_data_1, table_header_1 = _get_data_for_test(test1)
    students_data_2, table_header_2 = _get_data_for_test(test2)

    context = {
        'results': comparison_results,
        'test1': test1,
        'test2': test2,
        'title': f'Итоговый рейтинг для {test1.school_class.name}',
        # Добавляем новые данные в контекст для вкладок
        'students_data_1': students_data_1,
        'table_header_1': table_header_1,
        'students_data_2': students_data_2,
        'table_header_2': table_header_2,
    }
    return render(request, 'results/comparison_detail.html', context)

@login_required
def statistics_view(request):
    """
    Отображает продвинутую страницу статистики с фильтрами, KPI и несколькими графиками.
    (НОВАЯ, ПЕРЕРАБОТАННАЯ ВЕРСИЯ)
    """
    # 1. ПОЛУЧЕНИЕ ДАННЫХ ДЛЯ ФИЛЬТРОВ
    schools = School.objects.all()
    quarters = Quarter.objects.annotate(test_count=Count('gattests')).filter(test_count__gt=0).order_by('-year__start_date', '-start_date')

    # 2. ПОЛУЧЕНИЕ ВЫБОРА ПОЛЬЗОВАТЕЛЯ ИЗ GET-ЗАПРОСА
    selected_school_id = request.GET.get('school')
    selected_quarter_id = request.GET.get('quarter')
    selected_test_number = request.GET.get('test_number')

    # 3. ФИЛЬТРАЦИЯ ОСНОВНОГО НАБОРА ДАННЫХ
    results_qs = StudentResult.objects.select_related('student', 'gat_test', 'student__school_class').all()
    if selected_school_id:
        results_qs = results_qs.filter(student__school_class__school_id=selected_school_id)
    if selected_quarter_id:
        results_qs = results_qs.filter(gat_test__quarter_id=selected_quarter_id)
    if selected_test_number:
        results_qs = results_qs.filter(gat_test__test_number=selected_test_number)

    # 4. РАСЧЕТ ВСЕХ ПОКАЗАТЕЛЕЙ
    # Собираем данные о баллах в один список для удобства
    student_scores = []
    subject_scores = defaultdict(lambda: {'total': 0, 'correct': 0})
    subject_map = {s.id: s.name for s in Subject.objects.all()}

    for r in results_qs:
        total_score = 0
        for subject_id_str, answers in r.scores.items():
            correct = sum(answers)
            total = len(answers)
            total_score += correct
            
            subject_name = subject_map.get(int(subject_id_str))
            if subject_name:
                subject_scores[subject_name]['correct'] += correct
                subject_scores[subject_name]['total'] += total
        
        student_scores.append({'student': r.student, 'score': total_score})

    # --- KPI для карточек ---
    total_tests_taken = len(student_scores)
    total_students = results_qs.values('student').distinct().count()
    average_score = round(sum(s['score'] for s in student_scores) / total_tests_taken, 1) if total_tests_taken > 0 else 0
    
    # Считаем % учеников, набравших больше 50% (условно, если в среднем 1 вопрос = 1 балл, а вопросов 100)
    pass_rate = round(sum(1 for s in student_scores if s['score'] > 50) / total_tests_taken * 100, 1) if total_tests_taken > 0 else 0
    
    # --- Рейтинг предметов ---
    subject_performance = []
    for name, data in subject_scores.items():
        if data['total'] > 0:
            percentage = round(data['correct'] / data['total'] * 100, 1)
            subject_performance.append({'name': name, 'percentage': percentage})
    subject_performance.sort(key=lambda x: x['percentage'], reverse=True)
    
    top_subject = subject_performance[0] if subject_performance else {'name': 'N/A', 'percentage': 0}
    bottom_subject = subject_performance[-1] if subject_performance else {'name': 'N/A', 'percentage': 0}

    # --- Данные для графика распределения баллов ---
    score_bins = defaultdict(int)
    for s in student_scores:
        bin = (s['score'] // 10) * 10  # Группируем по 10 баллов
        score_bins[bin] += 1
    
    distribution_labels = [f"{i}-{i+9}" for i in range(0, 101, 10)]
    distribution_data = [score_bins.get(i, 0) for i in range(0, 101, 10)]

    # --- Топ-10 студентов ---
    top_10_students = sorted(student_scores, key=lambda x: x['score'], reverse=True)[:10]

    context = {
        'title': 'Статистика',
        # Фильтры
        'schools': schools, 'quarters': quarters,
        'selected_school_id': int(selected_school_id) if selected_school_id else None,
        'selected_quarter_id': int(selected_quarter_id) if selected_quarter_id else None,
        'selected_test_number': int(selected_test_number) if selected_test_number else None,
        # KPI для карточек
        'total_students': total_students,
        'total_tests_taken': total_tests_taken,
        'average_score': average_score,
        'pass_rate': pass_rate,
        'top_subject': top_subject,
        'bottom_subject': bottom_subject,
        # Данные для графиков
        'subject_perf_labels': json.dumps([s['name'] for s in subject_performance], ensure_ascii=False),
        'subject_perf_data': json.dumps([s['percentage'] for s in subject_performance]),
        'distribution_labels': json.dumps(distribution_labels),
        'distribution_data': json.dumps(distribution_data),
        # Данные для таблиц
        'top_10_students': top_10_students,
    }
    return render(request, 'statistics.html', context)

@login_required
def analysis_view(request):
    """
    Отображает страницу для сравнения успеваемости РАЗНЫХ КЛАССОВ
    в одной школе по результатам одного теста.
    (НОВАЯ, ПЕРЕРАБОТАННАЯ ВЕРСИЯ)
    """
    # 1. Получаем данные для фильтров
    schools = School.objects.all()
    quarters = Quarter.objects.annotate(test_count=Count('gattests')).filter(test_count__gt=0)

    # 2. Получаем выбор пользователя из GET-запроса
    selected_school_id = request.GET.get('school')
    selected_quarter_id = request.GET.get('quarter')
    selected_test_number = request.GET.get('test_number')

    # 3. Инициализируем переменные для результатов
    analysis_data = defaultdict(dict)
    table_data = defaultdict(dict)
    chart_labels = []
    chart_datasets = []
    
    # 4. Основная логика: выполняем, только если выбраны все фильтры
    if selected_school_id and selected_quarter_id and selected_test_number:
        # Находим все GAT-тесты, которые соответствуют нашему выбору
        # (например, все GAT-1 для всех классов школы №5 в 1-й четверти)
        tests = GatTest.objects.filter(
            school_class__school_id=selected_school_id,
            quarter_id=selected_quarter_id,
            test_number=selected_test_number
        ).select_related('school_class')

        # Получаем результаты для всех найденных тестов одним запросом
        results = StudentResult.objects.filter(gat_test__in=tests)
        
        # Получаем карту всех предметов для дальнейшего использования
        subject_map = {str(s.id): s.name for s in Subject.objects.all()}

        # 5. Агрегируем данные: собираем статистику по каждому классу и предмету
        for result in results:
            class_name = result.gat_test.school_class.name
            for subject_id_str, answers in result.scores.items():
                subject_name = subject_map.get(subject_id_str)
                if subject_name:
                    # 'correct' и 'total' - временные поля для подсчета
                    if 'correct' not in analysis_data[class_name].get(subject_name, {}):
                        analysis_data[class_name][subject_name] = {'correct': 0, 'total': 0}
                    
                    analysis_data[class_name][subject_name]['correct'] += sum(answers)
                    analysis_data[class_name][subject_name]['total'] += len(answers)

        # 6. Финальные расчеты и подготовка данных для графика и таблицы
        all_subjects = sorted(list(set(subj for class_data in analysis_data.values() for subj in class_data.keys())))
        chart_labels = all_subjects
        
        class_names = sorted(analysis_data.keys())

        for class_name in class_names:
            dataset = {
                'label': class_name,
                'data': []
            }
            for subject_name in all_subjects:
                data = analysis_data[class_name].get(subject_name)
                if data and data['total'] > 0:
                    percentage = round((data['correct'] / data['total']) * 100, 1)
                    dataset['data'].append(percentage)
                    table_data[subject_name][class_name] = percentage
                else:
                    dataset['data'].append(0)
                    table_data[subject_name][class_name] = 0
            
            chart_datasets.append(dataset)

    context = {
        'title': 'Анализ успеваемости',
        'schools': schools,
        'quarters': quarters,
        'has_results': bool(analysis_data),
        # Данные для графика
        'chart_labels': json.dumps(chart_labels, ensure_ascii=False),
        'chart_datasets': json.dumps(chart_datasets, ensure_ascii=False),
        # Данные для таблицы
        'table_data': dict(table_data),
        'table_headers': sorted(analysis_data.keys()),
        # Для сохранения выбора в фильтрах
        'selected_school_id': int(selected_school_id) if selected_school_id else None,
        'selected_quarter_id': int(selected_quarter_id) if selected_quarter_id else None,
        'selected_test_number': int(selected_test_number) if selected_test_number else None,
    }
    return render(request, 'analysis.html', context)

@login_required
def deep_analysis_view(request):
    """
    Углубленный анализ с фильтрами по четверти, школам, классам и предметам.
    (ФИНАЛЬНАЯ, КОМБИНИРОВАННАЯ ВЕРСИЯ)
    """
    form = DeepAnalysisForm(request.GET or None)
    
    if request.GET:
        school_ids = request.GET.getlist('schools')
        if school_ids:
            form.fields['school_classes'].queryset = SchoolClass.objects.filter(school_id__in=school_ids)
            form.fields['subjects'].queryset = Subject.objects.filter(school_id__in=school_ids)

    analysis_data = {}
    chart_data = '{}' # По умолчанию пустой JSON объект
    unique_subject_names = []
    first_school_data_normalized = None

    if form.is_valid():
        selected_quarter = form.cleaned_data['quarter']
        selected_schools = form.cleaned_data['schools']
        selected_classes = form.cleaned_data['school_classes']
        selected_subjects_qs = form.cleaned_data['subjects']
        selected_test_number = form.cleaned_data['test_number']
        
        subject_ids_to_fetch = [str(s.id) for s in selected_subjects_qs]
        results_qs = StudentResult.objects.filter(
            gat_test__quarter=selected_quarter,
            student__school_class__school__in=selected_schools,
            gat_test__test_number=selected_test_number,
            scores__has_any_keys=subject_ids_to_fetch
        ).select_related('student__school_class__school')
        
        if selected_classes.exists():
            selected_class_ids = list(selected_classes.values_list('id', flat=True))
            subclass_ids = list(SchoolClass.objects.filter(parent__in=selected_class_ids).values_list('id', flat=True))
            all_relevant_class_ids = set(selected_class_ids + subclass_ids)
            results_qs = results_qs.filter(student__school_class_id__in=all_relevant_class_ids)

        if results_qs.exists():
            unique_subject_names = sorted(list(set(selected_subjects_qs.values_list('name', flat=True))))
            
            initial_data = {}
            for school in selected_schools:
                initial_data[school.id] = {'school_name': school.name, 'subjects': {}}
                for name in unique_subject_names:
                    initial_data[school.id]['subjects'][name] = {
                        'subject_name': name,
                        'question_details': defaultdict(lambda: {'correct': 0, 'total': 0, 'percentage': 0})
                    }
            
            subject_id_to_name_map = {s.id: s.name for s in selected_subjects_qs}

            for result in results_qs:
                school_id = result.student.school_class.school.id
                if school_id not in initial_data: continue
                
                for subject_id_str, answers in result.scores.items():
                    subject_name = subject_id_to_name_map.get(int(subject_id_str))
                    if subject_name and subject_name in initial_data[school_id]['subjects']:
                        data_ref = initial_data[school_id]['subjects'][subject_name]
                        for i, answer in enumerate(answers):
                            q_num = str(i + 1)
                            data_ref['question_details'][q_num]['correct'] += answer
                            data_ref['question_details'][q_num]['total'] += 1

            for school_id, school_data in initial_data.items():
                for subject_name, subject_data in school_data['subjects'].items():
                    for q_num, q_data in subject_data['question_details'].items():
                        if q_data['total'] > 0:
                            q_data['percentage'] = round((q_data['correct'] / q_data['total']) * 100, 1)
                    subject_data['question_details'] = dict(subject_data['question_details'])
            
            analysis_data = initial_data
            
            chart_labels = unique_subject_names
            chart_datasets = []
            for school in selected_schools:
                dataset_data = []
                for name in chart_labels:
                    total_correct, total_questions = 0, 0
                    q_details = analysis_data.get(school.id, {}).get('subjects', {}).get(name, {}).get('question_details', {})
                    for q_data in q_details.values():
                        total_correct += q_data['correct']
                        total_questions += q_data['total']
                    percentage = round((total_correct / total_questions) * 100, 1) if total_questions > 0 else 0
                    dataset_data.append(percentage)
                chart_datasets.append({'label': school.name, 'data': dataset_data})
            
            chart_data = json.dumps({'labels': chart_labels, 'datasets': chart_datasets}, ensure_ascii=False)

            if analysis_data:
                first_school_data_normalized = next(iter(analysis_data.values()), None)

    context = {
        'title': 'Углубленный анализ',
        'form': form,
        'analysis_data': analysis_data,
        'unique_subject_names': unique_subject_names,
        'chart_data': chart_data,
        'has_results': bool(analysis_data),
        'first_school_data': first_school_data_normalized,
    }
    return render(request, 'deep_analysis.html', context)

@login_required
def subject_list_view(request):
    """
    Отображает список предметов, сгруппированных по школам.
    """
    # Получаем все школы и сразу подгружаем связанные с ними предметы одним запросом
    # для оптимизации (prefetch_related)
    schools_with_subjects = School.objects.prefetch_related('subjects').order_by('name')

    context = {
        'title': 'Предметы по школам',
        'schools_with_subjects': schools_with_subjects,
        'add_url_name': 'subject_add' # Имя URL для кнопки "Добавить"
    }
    return render(request, 'subjects/list.html', context)

# --- ИЗМЕНЕНИЯ В SubjectCreateView ---
class SubjectCreateView(LoginRequiredMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'subjects/form.html'
    success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Добавить Предмет', 'cancel_url': 'subject_list'}
    
    # Этот метод автоматически подставит школу в форму,
    # если мы перешли на страницу добавления по ссылке от конкретной школы
    def get_initial(self):
        initial = super().get_initial()
        school_id = self.request.GET.get('school')
        if school_id:
            try:
                initial['school'] = School.objects.get(pk=school_id)
            except School.DoesNotExist:
                pass
        return initial
    
def _get_grade_and_subjects_performance(result, subject_map):
    """Рассчитывает 10-балльную оценку, лучший и худший предметы."""
    
    # 1. Считаем максимальный возможный балл за тест
    class_subjects = ClassSubject.objects.filter(
        school_class=result.gat_test.school_class,
        subject_id__in=result.scores.keys()
    )
    max_score = sum(cs.number_of_questions for cs in class_subjects)
    
    if max_score == 0:
        return 0, None, None

    # 2. Считаем балл студента и процент
    student_score = sum(sum(ans) for ans in result.scores.values())
    percentage = (student_score / max_score) * 100
    
    # 3. Конвертируем процент в 10-балльную оценку
    if percentage >= 95: grade = 10
    elif percentage >= 85: grade = 9
    elif percentage >= 75: grade = 8
    elif percentage >= 65: grade = 7
    elif percentage >= 55: grade = 6
    elif percentage >= 45: grade = 5
    elif percentage >= 35: grade = 4
    elif percentage >= 25: grade = 3
    elif percentage >= 15: grade = 2
    else: grade = 1
    
    # 4. Находим лучший и худший предметы
    subject_performance = []
    for subj_id, answers in result.scores.items():
        total_q = len(answers)
        correct_q = sum(answers)
        if total_q > 0:
            perf = (correct_q / total_q) * 100
            subject_performance.append({'name': subject_map.get(int(subj_id)), 'perf': perf})
    
    if not subject_performance:
        return grade, None, None
        
    best_subject = max(subject_performance, key=lambda x: x['perf'])
    worst_subject = min(subject_performance, key=lambda x: x['perf'])
    
    return grade, best_subject, worst_subject

# Основная view-функция
@login_required
def student_progress_view(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student_results = student.results.select_related(
        'gat_test__quarter__year', 
        'gat_test__school_class__parent', 
        'gat_test__school_class__school'
    ).order_by('-gat_test__test_date')
    
    subject_map = {s.id: s.name for s in Subject.objects.all()}
    detailed_results_data = []

    for result in student_results:
        gat_test = result.gat_test
        student_current_score = sum(sum(a) for a in result.scores.values())

        # --- ИЗМЕНЕНИЕ ЗДЕСЬ: ПОЛНОСТЬЮ НОВАЯ И КОРРЕКТНАЯ ЛОГИКА РАСЧЕТА РЕЙТИНГОВ ---

        # Сначала находим всех участников теста на параллели (например, все 5-е классы)
        base_class = gat_test.school_class.parent or gat_test.school_class
        parallel_classes = SchoolClass.objects.filter(parent=base_class) | SchoolClass.objects.filter(id=base_class.id)
        parallel_tests = GatTest.objects.filter(
            school_class__in=parallel_classes,
            test_number=gat_test.test_number,
            quarter=gat_test.quarter
        )
        parallel_results_qs = StudentResult.objects.filter(gat_test__in=parallel_tests).select_related('student')

        # 1. Рейтинг по своему классу (например, 5В)
        #    Фильтруем общие результаты по параллели, оставляя только учеников из нужного класса
        class_results_qs = parallel_results_qs.filter(student__school_class=student.school_class)
        class_scores = sorted([sum(sum(a) for a in r.scores.values()) for r in class_results_qs], reverse=True)
        try:
            class_rank = class_scores.index(student_current_score) + 1
        except ValueError:
            class_rank = None
        
        # 2. Рейтинг по параллели (все 5-е классы)
        parallel_scores = sorted([sum(sum(a) for a in r.scores.values()) for r in parallel_results_qs], reverse=True)
        try:
            parallel_rank = parallel_scores.index(student_current_score) + 1
        except ValueError:
            parallel_rank = None

        # 3. Рейтинг по школе (все классы этой школы)
        school = gat_test.school_class.school
        school_tests = GatTest.objects.filter(school_class__school=school, test_number=gat_test.test_number, quarter=gat_test.quarter)
        school_results_qs = StudentResult.objects.filter(gat_test__in=school_tests)
        school_scores = sorted([sum(sum(a) for a in r.scores.values()) for r in school_results_qs], reverse=True)
        try:
            school_rank = school_scores.index(student_current_score) + 1
        except ValueError:
            school_rank = None

        # --- КОНЕЦ БЛОКА ИЗМЕНЕНИЙ ---

        grade, best_s, worst_s = _get_grade_and_subjects_performance(result, subject_map)
        processed_scores = []
        if isinstance(result.scores, dict):
            for sid_str, ans in result.scores.items():
                subject_name = subject_map.get(int(sid_str))
                if subject_name:
                    total_q, correct_q = len(ans), sum(ans)
                    percentage = round((correct_q / total_q) * 100, 1) if total_q > 0 else 0
                    processed_scores.append({
                        'subject': subject_name, 'answers': ans, 'correct': correct_q,
                        'incorrect': total_q - correct_q, 'percentage': percentage,
                        'grade': _calculate_grade_from_percentage(percentage),
                    })

        detailed_results_data.append({
            'result': result,
            'class_rank': class_rank, 'class_total': len(class_scores),
            'parallel_rank': parallel_rank, 'parallel_total': len(parallel_scores),
            'school_rank': school_rank, 'school_total': len(school_scores),
            'grade': grade, 'best_subject': best_s, 'worst_subject': worst_s,
            'processed_scores': processed_scores,
        })
        
    comparison_data = None
    if len(detailed_results_data) >= 2:
        latest, previous = detailed_results_data[0], detailed_results_data[1]
        comparison_data = {
            'latest': latest, 'previous': previous,
            'grade_diff': latest['grade'] - previous['grade'],
            'rank_diff': (previous.get('class_rank') - latest.get('class_rank')) if previous.get('class_rank') and latest.get('class_rank') else None,
        }

    context = {
        'title': f'Аналитика студента: {student}', 'student': student,
        'detailed_results_data': detailed_results_data, 'comparison_data': comparison_data,
    }
    return render(request, 'results/student_progress.html', context)

@login_required
def load_subjects_and_classes_for_schools(request):
    """ API для динамической загрузки предметов и классов по выбранным школам """
    school_ids = request.GET.getlist('school_ids[]')
    if not school_ids:
        return JsonResponse({'subjects': [], 'classes': []})
    
    subjects = Subject.objects.filter(school_id__in=school_ids).order_by('name').values('id', 'name', 'school__name')
    classes = SchoolClass.objects.filter(school_id__in=school_ids).order_by('name').values('id', 'name', 'school__name')

    # Добавляем название школы к имени для ясности в списке
    subjects_data = [
        {'id': s['id'], 'name': f"{s['name']} ({s['school__name']})"} for s in subjects
    ]
    classes_data = [
        {'id': c['id'], 'name': f"{c['name']} ({c['school__name']})"} for c in classes
    ]
    
    return JsonResponse({'subjects': subjects_data, 'classes': classes_data})
@login_required
def header_search_api(request):
    query = request.GET.get('q', '')
    results = []
    if query:
        # Ищем студентов
        students = Student.objects.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(student_id__icontains=query)
        )[:5]
        for s in students:
            results.append({
                'type': 'Студент',
                'name': f"{s.first_name} {s.last_name} ({s.student_id})",
                'url': reverse('student_progress', args=[s.id])
            })
        
        # Ищем тесты
        tests = GatTest.objects.filter(name__icontains=query)[:5]
        for t in tests:
            results.append({
                'type': 'Тест',
                'name': t.name,
                'url': reverse('class_results_dashboard', args=[t.quarter_id, t.school_class_id])
            })
            
    return JsonResponse({'results': results})

@login_required
def profile_view(request):
    user = request.user
    
    # --- ИСПРАВЛЕНИЕ ЗДЕСЬ ---
    # Эта команда либо находит существующий профиль, либо создает новый.
    # Это решает проблему для старых пользователей, у которых его нет.
    profile, created = UserProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            # Используем `profile` вместо `user.profile`
            profile_form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
            if profile_form.is_valid():
                user.first_name = profile_form.cleaned_data['first_name']
                user.last_name = profile_form.cleaned_data['last_name']
                user.save()
                profile_form.save()
                messages.success(request, 'Ваши данные успешно обновлены.')
                return redirect('profile')
        
        elif action == 'change_password':
            password_form = CustomPasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Ваш пароль успешно изменен.')
                return redirect('profile')
        
        elif action == 'change_email':
            email_form = EmailChangeForm(request.POST, instance=user)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, 'Ваш email успешно изменен.')
                return redirect('profile')

    # Для GET-запроса, если формы не были отправлены или невалидны
    profile_form = ProfileUpdateForm(instance=profile, initial={'first_name': user.first_name, 'last_name': user.last_name})
    password_form = CustomPasswordChangeForm(user)
    email_form = EmailChangeForm(instance=user)

    context = {
        'title': 'Мой профиль',
        'profile_form': profile_form,
        'password_form': password_form,
        'email_form': email_form,
    }
    return render(request, 'profile.html', context)

def _calculate_grade_from_percentage(percentage):
    """Конвертирует процент в 10-балльную оценку."""
    if percentage >= 95: return 10
    elif percentage >= 85: return 9
    elif percentage >= 75: return 8
    elif percentage >= 65: return 7
    elif percentage >= 55: return 6
    elif percentage >= 45: return 5
    elif percentage >= 35: return 4
    elif percentage >= 25: return 3
    elif percentage >= 15: return 2
    else: return 1