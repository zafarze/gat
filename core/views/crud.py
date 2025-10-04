# D:\New_GAT\core\views\crud.py (ФИНАЛЬНАЯ ВЕРСИЯ С ПРАВАМИ ДОСТУПА)

from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Count

from ..models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    ClassSubject, GatTest, Student, TeacherNote
)
from ..forms import (
    AcademicYearForm, QuarterForm, SchoolForm, SchoolClassForm, SubjectForm,
    ClassSubjectForm, GatTestForm, TeacherNoteForm
)
from .permissions import get_accessible_schools # <--- Подключаем нашу "умную" функцию


# --- ACADEMIC YEAR, QUARTER (без изменений) ---
class AcademicYearListView(LoginRequiredMixin, ListView):
    model = AcademicYear; template_name = 'years/list.html'; context_object_name = 'items'
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


# --- SCHOOL (ВАЖНОЕ ИЗМЕНЕНИЕ) ---
class SchoolListView(LoginRequiredMixin, ListView):
    model = School
    template_name = 'schools/list.html'
    context_object_name = 'items'
    
    def get_queryset(self):
        queryset = super().get_queryset().order_by('name')
        # Если пользователь не администратор, фильтруем школы
        if not self.request.user.is_superuser:
            accessible_schools = get_accessible_schools(self.request.user)
            queryset = queryset.filter(id__in=accessible_schools.values_list('id', flat=True))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Школы'
        # Директору не даем права добавлять/редактировать/удалять школы
        if self.request.user.is_superuser:
            context['add_url'] = 'school_add'
            context['edit_url'] = 'school_edit'
            context['delete_url'] = 'school_delete'
        return context

class SchoolCreateView(LoginRequiredMixin, CreateView):
    model = School; form_class = SchoolForm; template_name = 'schools/form.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Добавить Школу', 'cancel_url': 'school_list'}

class SchoolUpdateView(LoginRequiredMixin, UpdateView):
    model = School; form_class = SchoolForm; template_name = 'schools/form.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Редактировать Школу', 'cancel_url': 'school_list'}

class SchoolDeleteView(LoginRequiredMixin, DeleteView):
    model = School; template_name = 'schools/confirm_delete.html'; success_url = reverse_lazy('school_list')
    extra_context = {'title': 'Удалить Школу', 'cancel_url': 'school_list'}


# --- SCHOOL CLASS (ВАЖНОЕ ИЗМЕНЕНИЕ) ---
class SchoolClassListView(LoginRequiredMixin, ListView):
    model = School
    template_name = 'classes/list.html'
    context_object_name = 'schools'
    
    def get_queryset(self):
        queryset = School.objects.prefetch_related('classes').order_by('name')
        if not self.request.user.is_superuser:
            accessible_schools = get_accessible_schools(self.request.user)
            queryset = queryset.filter(id__in=accessible_schools.values_list('id', flat=True))
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Классы по школам'
        # Показываем кнопки только администратору
        if self.request.user.is_superuser:
            context['add_url'] = 'class_add'
            context['edit_url'] = 'class_edit'
            context['delete_url'] = 'class_delete'
        return context

class SchoolClassCreateView(LoginRequiredMixin, CreateView):
    model = SchoolClass; form_class = SchoolClassForm; template_name = 'classes/form.html'; success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Добавить Класс', 'cancel_url': 'class_list'}
    def get_initial(self):
        initial = super().get_initial()
        school_id = self.request.GET.get('school')
        if school_id: initial['school'] = school_id
        return initial

class SchoolClassUpdateView(LoginRequiredMixin, UpdateView):
    model = SchoolClass; form_class = SchoolClassForm; template_name = 'classes/form.html'; success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Редактировать Класс', 'cancel_url': 'class_list'}

class SchoolClassDeleteView(LoginRequiredMixin, DeleteView):
    model = SchoolClass; template_name = 'classes/confirm_delete.html'; success_url = reverse_lazy('class_list')
    extra_context = {'title': 'Удалить Класс', 'cancel_url': 'class_list'}


# --- SUBJECT (ВАЖНОЕ ИЗМЕНЕНИЕ) ---
@login_required
def subject_list_view(request):
    schools_qs = School.objects.prefetch_related('subjects').order_by('name')
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        schools_qs = schools_qs.filter(id__in=accessible_schools.values_list('id', flat=True))
    
    context = {'title': 'Предметы по школам', 'schools_with_subjects': schools_qs}
    if request.user.is_superuser:
        context['add_url_name'] = 'subject_add'
    return render(request, 'subjects/list.html', context)

class SubjectCreateView(LoginRequiredMixin, CreateView):
    model = Subject; form_class = SubjectForm; template_name = 'subjects/form.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Добавить Предмет', 'cancel_url': 'subject_list'}
    def get_initial(self):
        initial = super().get_initial()
        school_id = self.request.GET.get('school')
        if school_id:
            try: initial['school'] = School.objects.get(pk=school_id)
            except School.DoesNotExist: pass
        return initial

class SubjectUpdateView(LoginRequiredMixin, UpdateView):
    model = Subject; form_class = SubjectForm; template_name = 'subjects/form.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Редактировать Предмет', 'cancel_url': 'subject_list'}

class SubjectDeleteView(LoginRequiredMixin, DeleteView):
    model = Subject; template_name = 'subjects/confirm_delete.html'; success_url = reverse_lazy('subject_list')
    extra_context = {'title': 'Удалить Предмет', 'cancel_url': 'subject_list'}


# --- CLASS SUBJECT (ВАЖНОЕ ИЗМЕНЕНИЕ) ---
class ClassSubjectListView(LoginRequiredMixin, ListView):
    model = SchoolClass
    template_name = 'class_subjects/list.html'
    context_object_name = 'classes'

    def get_queryset(self):
        queryset = SchoolClass.objects.annotate(num_subjects=Count('subjects')).filter(num_subjects__gt=0).prefetch_related('classsubject_set__subject').order_by('school__name', 'name')
        if not self.request.user.is_superuser:
            accessible_schools = get_accessible_schools(self.request.user)
            queryset = queryset.filter(school__in=accessible_schools)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Учебный план'
        if self.request.user.is_superuser:
            context['add_url'] = 'class_subject_add'
            context['edit_url'] = 'class_subject_edit'
            context['delete_url'] = 'class_subject_delete'
        return context

class ClassSubjectCreateView(LoginRequiredMixin, CreateView):
    model = ClassSubject; form_class = ClassSubjectForm; template_name = 'class_subjects/form.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Добавить предмет в класс', 'cancel_url': 'class_subject_list'}

class ClassSubjectUpdateView(LoginRequiredMixin, UpdateView):
    model = ClassSubject; form_class = ClassSubjectForm; template_name = 'class_subjects/form.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Редактировать предмет в классе', 'cancel_url': 'class_subject_list'}

class ClassSubjectDeleteView(LoginRequiredMixin, DeleteView):
    model = ClassSubject; template_name = 'class_subjects/confirm_delete.html'; success_url = reverse_lazy('class_subject_list')
    extra_context = {'title': 'Удалить предмет из класса', 'cancel_url': 'class_subject_list'}


# --- GAT TEST (ВАЖНОЕ ИЗМЕНЕНИЕ) ---
@login_required
def gat_test_list_view(request):
    grouped_tests = defaultdict(list)
    tests_qs = GatTest.objects.select_related('school_class__school', 'quarter').prefetch_related('subjects').order_by('school_class__school__name', 'name')
    
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        tests_qs = tests_qs.filter(school_class__school__in=accessible_schools)

    for test in tests_qs:
        grouped_tests[test.school_class.school].append(test)

    context = {'grouped_tests': dict(grouped_tests), 'title': 'GAT Тесты'}
    if request.user.is_superuser:
        context['add_url'] = 'gat_test_add'
        context['edit_url'] = 'gat_test_edit'
        context['delete_url'] = 'gat_test_delete'
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


# --- TEACHER NOTE (без изменений) ---
class TeacherNoteCreateView(LoginRequiredMixin, CreateView):
    model = TeacherNote; form_class = TeacherNoteForm; template_name = 'notes/form.html'
    def form_valid(self, form):
        student = get_object_or_404(Student, pk=self.kwargs['student_pk'])
        form.instance.student = student
        form.instance.author = self.request.user
        messages.success(self.request, "Заметка успешно добавлена.")
        return super().form_valid(form)
    def get_success_url(self):
        return reverse_lazy('student_progress', kwargs={'student_id': self.kwargs['student_pk']})
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['student'] = get_object_or_404(Student, pk=self.kwargs['student_pk'])
        context['title'] = "Добавить заметку"
        return context

class TeacherNoteDeleteView(LoginRequiredMixin, DeleteView):
    model = TeacherNote; template_name = 'notes/confirm_delete.html'
    def get_success_url(self):
        messages.success(self.request, "Заметка успешно удалена.")
        return reverse_lazy('student_progress', kwargs={'student_id': self.object.student.pk})
    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            return qs.filter(author=self.request.user)
        return qs