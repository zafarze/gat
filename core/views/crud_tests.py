# D:\GAT\core\views\crud_tests.py (ПОЛНАЯ ОБНОВЛЕННАЯ ВЕРСИЯ)

import json
from collections import defaultdict
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
import random
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.urls import reverse_lazy
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from django.db.models import Count, Q
from core.models import DifficultyRule

# АБСОЛЮТНЫЕ ИМПОРТЫ
from core.models import (
    School, SchoolClass, Subject, GatTest, TeacherNote, BankQuestion # <-- ДОБАВЛЕНО ЗДЕСЬ
)
from core.forms import (
    GatTestForm, TeacherNoteForm
)
from core.views.permissions import get_accessible_schools
# --- 👇 Убедись, что импорты из crud_base правильные 👇 ---
from .crud_base import HtmxCreateView, HtmxUpdateView, HtmxDeleteView
# --- КОНЕЦ ---

# =============================================================================
# --- GAT ТЕСТЫ (GAT TEST) ---
# =============================================================================

@login_required
def gat_test_list_view(request):
    # Эта функция остается без изменений
    base_qs = GatTest.objects.select_related('school', 'school_class', 'quarter').order_by('-test_date', 'name')
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        base_qs = base_qs.filter(school__in=accessible_schools)

    grouped_tests = defaultdict(list)
    for test in base_qs:
        if test.school:
            grouped_tests[test.school].append(test)

    sorted_grouped_tests = dict(sorted(grouped_tests.items(), key=lambda item: item[0].name))
    context = {
        'grouped_tests': sorted_grouped_tests,
        'title': 'GAT Тесты',
        'add_url': 'core:gat_test_add',
        'edit_url': 'core:gat_test_edit',
        'delete_url': 'core:gat_test_delete'
    }
    return render(request, 'gat_tests/list.html', context)


class GatTestCreateView(HtmxCreateView):
    model = GatTest
    form_class = GatTestForm
    template_name_prefix = 'gat_tests'
    list_url_name = 'core:gat_test_list' # URL для обычного редиректа

    def get_form_kwargs(self):
        # Этот метод остается без изменений
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        if school_id := self.request.GET.get('school'):
            try:
                kwargs['school'] = School.objects.get(pk=school_id)
            except School.DoesNotExist:
                pass
        return kwargs

    def get_context_data(self, **kwargs):
        # Этот метод остается почти без изменений, добавим kwargs в super() для form_invalid
        context = super(HtmxCreateView, self).get_context_data(**kwargs) # Используем базовый HtmxCreateView
        context['title'] = 'Назначить GAT Тест'
        return context

    # --- 👇 ОБНОВЛЕННЫЙ FORM_VALID 👇 ---
    def form_valid(self, form):
        self.object = form.save()
        success_message = f"Тест '{self.object.name}' успешно назначен."
        messages.success(self.request, success_message)

        if self.request.htmx:
            # Отправляем заголовок для перезагрузки всей страницы
            headers = {'HX-Refresh': 'true'}
            # Ответ 204 No Content с заголовком
            return HttpResponse(status=204, headers=headers)

        # Редирект для обычного (не HTMX) запроса
        return redirect(reverse_lazy(self.list_url_name))
    # --- КОНЕЦ ОБНОВЛЕНИЯ ---

    # --- 👇 ОБНОВЛЕННЫЙ FORM_INVALID 👇 ---
    def form_invalid(self, form):
        # Логика для подгрузки queryset для зависимого поля при ошибке
        school_id = self.request.POST.get('school')
        if school_id:
            try:
                school = School.objects.get(pk=school_id)
                form.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, parent__isnull=True).order_by('name')
            except School.DoesNotExist:
                # Если школа не найдена, очищаем queryset, чтобы избежать ошибок
                form.fields['school_class'].queryset = SchoolClass.objects.none()

        if self.request.htmx:
            # Собираем контекст, передавая невалидную форму
            context = self.get_context_data(form=form)
            # Рендерим ТОЛЬКО содержимое формы (_form_content.html)
            response = render(self.request, f'{self.template_name_prefix}/partials/_form_content.html', context)
            # Устанавливаем статус 422 для HTMX
            response.status_code = 422
            return response

        # Стандартное поведение для обычного (не HTMX) запроса
        return super().form_invalid(form)
    # --- КОНЕЦ ОБНОВЛЕНИЯ ---


class GatTestUpdateView(HtmxUpdateView):
    model = GatTest
    form_class = GatTestForm
    # --- 👇 ИЗМЕНЯЕМ template_name 👇 ---
    template_name = 'gat_tests/assembly_page.html' # Указываем новый ОБЕРТОЧНЫЙ шаблон
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---
    template_name_prefix = 'gat_tests'
    list_url_name = 'core:gat_test_list'

    def get_template_names(self):
        """
        Явно указывает, какой шаблон использовать.
        """
        # --- 👇 ИЗМЕНЯЕМ шаблон здесь 👇 ---
        # Всегда используем основной ОБЕРТОЧНЫЙ шаблон для этого view.
        return ['gat_tests/assembly_page.html']

    def get_form_kwargs(self):
        # Этот метод остается без изменений
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        school = self.object.school if self.object else None
        if school_id := self.request.POST.get('school'): # Проверяем POST для form_invalid
             try:
                school = School.objects.get(pk=school_id)
             except School.DoesNotExist:
                 pass
        elif self.object: # Используем школу из объекта при GET
            school = self.object.school

        kwargs['school'] = school
        return kwargs

    def get_context_data(self, **kwargs):
        # Этот метод остается без изменений
        context = super().get_context_data(**kwargs)
        context['title'] = f'Сборка теста: {self.object.name}'

        test_object = self.object
        test_parallel = test_object.school_class

        added_question_ids = set(test_object.questions.values_list('id', flat=True))
        context['added_question_ids'] = added_question_ids
        context['added_questions'] = test_object.questions.select_related('subject', 'topic').order_by('subject__name', 'id')

        available_questions = BankQuestion.objects.filter(
            school_class=test_parallel
        ).select_related(
            'subject', 'topic'
        ).order_by('subject__name', 'topic__name', 'id')

        context['available_questions'] = available_questions
        context['test_id'] = test_object.id
        return context

    def form_valid(self, form):
        # Этот метод остается без изменений
        self.object = form.save()
        success_message = f"Параметры теста '{self.object.name}' успешно обновлены."
        messages.success(self.request, success_message)

        if self.request.htmx:
            headers = {'HX-Refresh': 'true'}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

    # --- 👇 ИЗМЕНЕННЫЙ form_invalid 👇 ---
    def form_invalid(self, form):
        # Логика для school_class queryset остается
        school_id = self.request.POST.get('school')
        if school_id:
            try:
                school = School.objects.get(pk=school_id)
                form.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, parent__isnull=True).order_by('name')
            except School.DoesNotExist:
                form.fields['school_class'].queryset = SchoolClass.objects.none()

        # Для HTMX и НЕ-HTMX запросов при ошибке просто перерисовываем всю страницу
        # используя шаблон, который вернет get_template_names()
        return self.render_to_response(self.get_context_data(form=form))
    # --- КОНЕЦ ОБНОВЛЕНИЯ ---

# --- 👇 ОБНОВЛЕННЫЙ DELETE VIEW 👇 ---
class GatTestDeleteView(HtmxDeleteView):
    model = GatTest
    template_name = 'gat_tests/confirm_delete.html' # Шаблон для GET запроса (окно подтверждения)
    # template_name_prefix не нужен, так как мы не используем базовый post
    list_url_name = 'core:gat_test_list' # URL для обычного редиректа

    # get_success_url не нужен, так как мы делаем рефреш через HTMX

    def get_context_data(self, **kwargs):
        # Этот метод нужен для заголовка окна подтверждения
        context = super().get_context_data(**kwargs)
        context['title'] = f'Удалить GAT Тест: {self.object.name}'
        context['cancel_url'] = reverse_lazy(self.list_url_name) # Для кнопки "Отмена" (если нужна)
        return context

    def post(self, request, *args, **kwargs):
        """ Обрабатываем POST запрос на удаление """
        self.object = self.get_object()
        item_name = str(self.object)
        success_url = reverse_lazy(self.list_url_name) # URL для обычного редиректа

        self.object.delete()
        success_message = f'Тест "{item_name}" успешно удален.'
        messages.error(self.request, success_message) # Используем error для красного сообщения

        if self.request.htmx:
            # Отправляем заголовок для перезагрузки страницы
            headers = {'HX-Refresh': 'true'}
            # Можно добавить триггер для сообщения, но перезагрузка его покажет
            # trigger = {"show-message": {"text": success_message, "type": "error"}}
            # headers['HX-Trigger'] = json.dumps(trigger)
            return HttpResponse(status=204, headers=headers)

        # Редирект для обычного (не HTMX) запроса
        return HttpResponseRedirect(success_url)
# --- КОНЕЦ ОБНОВЛЕНИЯ ---


@login_required
def gat_test_delete_results_view(request, pk):
    # Эта функция остается без изменений
    gat_test = get_object_or_404(GatTest, pk=pk)
    results = gat_test.results.all()
    count = results.count()

    if request.method == 'POST':
        results.delete()
        messages.success(request, f'Все {count} результатов для теста "{gat_test.name}" были успешно удалены.')
        return redirect('core:gat_test_list')

    context = {
        'item': gat_test,
        'count': count,
        'title': f'Удалить результаты для {gat_test.name}',
        'cancel_url': reverse_lazy('core:gat_test_list') # Исправлен cancel_url
    }
    return render(request, 'results/confirm_delete_batch.html', context)


# =============================================================================
# --- ЗАМЕТКИ УЧИТЕЛЯ (TEACHER NOTE) ---
# =============================================================================
# Эти классы остаются без изменений, так как они не используют HTMX для обновления списка
class TeacherNoteCreateView(HtmxCreateView):
    model = TeacherNote
    form_class = TeacherNoteForm
    template_name = 'students/partials/note_form.html'

    def form_valid(self, form):
        form.instance.author = self.request.user
        form.instance.student_id = self.kwargs.get('student_pk')
        form.save()
        messages.success(self.request, 'Заметка добавлена.')
        return redirect('core:student_progress', student_id=self.kwargs.get('student_pk'))

class TeacherNoteDeleteView(HtmxDeleteView):
    model = TeacherNote

    def get_success_url(self):
        return reverse_lazy('core:student_progress', kwargs={'student_id': self.object.student_id})

    # Добавляем POST для стандартного удаления (без HTMX)
    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        success_url = self.get_success_url()
        note_text = str(self.object.note[:30]) + '...'
        self.object.delete()
        messages.error(request, f'Заметка "{note_text}" удалена.')
        return HttpResponseRedirect(success_url)

# =============================================================================
# --- ✨ НОВЫЙ БЛОК: СБОРКА ТЕСТА (HTMX) ✨ ---
# =============================================================================

def _get_assembly_context(test_pk):
    test_object = get_object_or_404(GatTest.objects.prefetch_related(
        'questions__subject', 'questions__topic'
    ), pk=test_pk)
    
    test_parallel = test_object.school_class
    
    # 1. Получаем уже добавленные вопросы
    added_questions = test_object.questions.select_related('subject', 'topic').order_by('subject__name', 'id')
    added_question_ids = set(added_questions.values_list('id', flat=True))

    # 2. --- ✨ НОВАЯ ЛОГИКА: СЧИТАЕМ СТАТИСТИКУ СЛОЖНОСТИ ✨ ---
    total_count = added_questions.count()
    stats = {
        'easy': {'count': 0, 'percent': 0, 'target': 0},
        'medium': {'count': 0, 'percent': 0, 'target': 0},
        'hard': {'count': 0, 'percent': 0, 'target': 0},
    }

    if total_count > 0:
        # Считаем факты
        stats['easy']['count'] = added_questions.filter(difficulty='EASY').count()
        stats['medium']['count'] = added_questions.filter(difficulty='MEDIUM').count()
        stats['hard']['count'] = added_questions.filter(difficulty='HARD').count()

        # Считаем проценты
        stats['easy']['percent'] = round((stats['easy']['count'] / total_count) * 100)
        stats['medium']['percent'] = round((stats['medium']['count'] / total_count) * 100)
        stats['hard']['percent'] = round((stats['hard']['count'] / total_count) * 100)

    # 3. --- Получаем целевые показатели (Rules) ---
    # В GAT тесте много предметов, поэтому берем "усредненное правило" или правило для первого предмета.
    # Для упрощения: покажем жесткий стандарт 40/40/20, если правил нет.
    
    # Пытаемся найти правила для предметов, которые есть в тесте
    subjects_in_test = test_object.questions.values_list('subject', flat=True).distinct()
    rules = DifficultyRule.objects.filter(
        school_class=test_parallel, 
        subject__in=subjects_in_test
    )
    
    # Если правило найдено (берем первое попавшееся для примера, 
    # в идеале нужно считать взвешенное среднее, но это сложно для начала)
    if rules.exists():
        rule = rules.first()
        stats['easy']['target'] = rule.easy_percent
        stats['medium']['target'] = rule.medium_percent
        stats['hard']['target'] = rule.hard_percent
    else:
        # Дефолт, если правил нет
        stats['easy']['target'] = 40
        stats['medium']['target'] = 40
        stats['hard']['target'] = 20

    # 4. Остальная логика (доступные вопросы)
    available_questions = BankQuestion.objects.filter(
        school_class=test_parallel
    ).select_related(
        'subject', 'topic'
    ).order_by('subject__name', 'topic__name', 'id')

    subject_counts = defaultdict(int)
    for q in added_questions:
        subject_counts[q.subject.name] += 1

    return {
        'object': test_object,
        'test_id': test_object.id,
        'added_questions': added_questions,
        'added_question_ids': added_question_ids,
        'available_questions': available_questions,
        'subject_counts': dict(subject_counts),
        'difficulty_stats': stats, # ✨ Передаем статистику в шаблон
    }

@login_required
@require_POST # Принимаем только POST-запросы
def add_question_to_test(request, test_pk, question_pk):
    """
    HTMX View: Добавляет вопрос (BankQuestion) в тест (GatTest).
    """
    test = get_object_or_404(GatTest, pk=test_pk)
    question = get_object_or_404(BankQuestion, pk=question_pk)
    
    # Добавляем вопрос в M2M-связь
    test.questions.add(question)
    
    # Получаем обновленный контекст
    context = _get_assembly_context(test_pk)
    
    # Рендерим и возвращаем только правую колонку
    return render(request, 'gat_tests/partials/_assembly_panel.html', context)

@login_required
@require_POST # Принимаем только POST-запросы
def remove_question_from_test(request, test_pk, question_pk):
    """
    HTMX View: Удаляет вопрос (BankQuestion) из теста (GatTest).
    """
    test = get_object_or_404(GatTest, pk=test_pk)
    question = get_object_or_404(BankQuestion, pk=question_pk)
    
    # Удаляем вопрос из M2M-связи
    test.questions.remove(question)
    
    # Получаем обновленный контекст
    context = _get_assembly_context(test_pk)
    
    # Рендерим и возвращаем только правую колонку
    return render(request, 'gat_tests/partials/_assembly_panel.html', context)

def get_balanced_questions(subject, total_count):
    """
    Возвращает список вопросов (QuerySet) по схеме:
    40% Легкие, 40% Средние, 20% Сложные.
    """
    # 1. Считаем сколько нужно вопросов каждого типа
    easy_needed = int(total_count * 0.4)
    medium_needed = int(total_count * 0.4)
    hard_needed = total_count - easy_needed - medium_needed # Остаток берем как сложные

    # 2. Достаем ID вопросов из базы
    # Используем values_list для оптимизации (получаем только ID)
    qs = BankQuestion.objects.filter(subject=subject)
    
    easy_ids = list(qs.filter(difficulty='EASY').values_list('id', flat=True))
    medium_ids = list(qs.filter(difficulty='MEDIUM').values_list('id', flat=True))
    hard_ids = list(qs.filter(difficulty='HARD').values_list('id', flat=True))

    selected_ids = []

    # 3. Функция-помощник для безопасного выбора
    def pick_ids(source_ids, count):
        if len(source_ids) >= count:
            return random.sample(source_ids, count)
        return source_ids # Если вопросов не хватает, берем все, что есть

    # 4. Набираем вопросы
    selected_ids.extend(pick_ids(easy_ids, easy_needed))
    selected_ids.extend(pick_ids(medium_ids, medium_needed))
    selected_ids.extend(pick_ids(hard_ids, hard_needed))

    # 5. Если вопросов не хватило до total_count (база маленькая), добираем любые
    current_count = len(selected_ids)
    if current_count < total_count:
        all_ids = set(easy_ids + medium_ids + hard_ids)
        used_ids = set(selected_ids)
        remaining_ids = list(all_ids - used_ids)
        needed = total_count - current_count
        selected_ids.extend(pick_ids(remaining_ids, needed))

    return BankQuestion.objects.filter(id__in=selected_ids)