# D:\New_GAT\core\views\crud.py (ОБНОВЛЕННАЯ ВЕРСИЯ БЕЗ ДУБЛИКАТОВ)

import json
from collections import defaultdict
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import FormView, ListView, CreateView, UpdateView, DeleteView
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.urls import reverse_lazy
from django.template.loader import render_to_string
from core.forms import GatTestForm
from core.models import School, SchoolClass, Subject
from core.forms import QuestionCountForm
from accounts.models import UserProfile

# АБСОЛЮТНЫЕ ИМПОРТЫ
from core.models import (
    AcademicYear, Quarter, School, SchoolClass, Subject, GatTest, TeacherNote, QuestionCount
)
from core.forms import (
    AcademicYearForm, QuarterForm, SchoolForm, SchoolClassForm,
    SubjectForm, GatTestForm, TeacherNoteForm, QuestionCountForm,
    QuestionCountBulkSchoolForm
)
from core.views.permissions import get_accessible_schools

# =============================================================================
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ И СЛОВАРИ ---
# =============================================================================
VIEW_MAP = {}

def get_list_view_instance(model_name, request):
    """
    Возвращает экземпляр ListView для указанной модели.
    Используется для получения queryset с учётом прав доступа.
    """
    from .crud import AcademicYearListView, QuarterListView, SchoolListView, SchoolClassListView, SubjectListView

    if not VIEW_MAP:
        VIEW_MAP.update({
            'AcademicYear': AcademicYearListView,
            'Quarter': QuarterListView,
            'School': SchoolListView,
            'SchoolClass': SchoolClassListView,
            'Subject': SubjectListView,
        })
    view_class = VIEW_MAP.get(model_name)
    if view_class:
        instance = view_class()
        instance.request = request
        return instance
    return None

def _get_question_count_htmx_response(request, school, success_message, message_type='success', is_delete=False):
    """
    Вспомогательная функция: генерирует HTMX-ответ для CRUD-операций с QuestionCount.
    Возвращает обновленное содержимое таблицы для конкретной школы.
    """
    school.all_question_counts = QuestionCount.objects.filter(
        school_class__school=school
    ).select_related('subject', 'school_class').order_by('subject__name')

    modal_event = "close-delete-modal" if is_delete else "close-modal"
    trigger = {
        modal_event: True,
        "show-message": {"text": success_message, "type": message_type}
    }
    target_id = f"#qc-tbody-{school.id}"
    headers = {
        'HX-Trigger': json.dumps(trigger),
        'HX-Retarget': target_id,
        'HX-Reswap': 'innerHTML'
    }

    html = render_to_string('question_counts/partials/_table_rows.html', {'school': school}, request=request)
    return HttpResponse(html, headers=headers)

# =============================================================================
# --- БАЗОВЫЕ КЛАССЫ С ЛОГИКОЙ HTMX ---
# =============================================================================
class HtmxListView(LoginRequiredMixin, ListView):
    template_name_prefix = None
    
    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not user.is_staff and not user.is_superuser:
            if hasattr(self.model, 'school'):
                accessible_schools = get_accessible_schools(user)
                qs = qs.filter(school__in=accessible_schools)
            elif hasattr(self.model, 'school_class'):
                accessible_schools = get_accessible_schools(user)
                qs = qs.filter(school_class__school__in=accessible_schools)
        return qs

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/_table.html']
        return [f'{self.template_name_prefix}/list.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'object_list' in context:
            context['items'] = context.pop('object_list')
        return context

class HtmxCreateView(LoginRequiredMixin, CreateView):
    template_name_prefix = None
    list_url_name = None

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)

        if self.request.htmx:
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            
            list_view = get_list_view_instance(self.model.__name__, self.request)
            context = {'items': list_view.get_queryset(), **list_view.extra_context}
            
            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Добавить: {self.model._meta.verbose_name}'
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context
    
    def form_invalid(self, form):
        if self.request.htmx:
            response = render(self.request, f'{self.template_name_prefix}/partials/_form_content.html', self.get_context_data(form=form))
        return super().form_invalid(form)

class HtmxFormView(LoginRequiredMixin, FormView):
    template_name_prefix = None
    list_url_name = None

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        raise NotImplementedError("You must implement form_valid in a subclass.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Форма"
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context
    
    def form_invalid(self, form):
        if self.request.htmx:
            return render(self.request, self.get_template_names()[0], self.get_context_data(form=form))
        return super().form_invalid(form)

class HtmxUpdateView(LoginRequiredMixin, UpdateView):
    template_name_prefix = None
    list_url_name = None

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            
            list_view = get_list_view_instance(self.model.__name__, self.request)
            context = {'items': list_view.get_queryset(), **list_view.extra_context}
            
            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Редактировать: {self.object}'
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context

    def form_invalid(self, form):
        if self.request.htmx:
            response = render(self.request, f'{self.template_name_prefix}/partials/_form_content.html', self.get_context_data(form=form))
        return super().form_invalid(form)

class HtmxDeleteView(LoginRequiredMixin, DeleteView):
    template_name_prefix = None
    list_url_name = None

    def get_success_url(self):
        return reverse_lazy(self.list_url_name)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Удалить: {self.object}'
        context['cancel_url'] = reverse_lazy(self.list_url_name)
        return context

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            item_name = str(self.object)
            model_name = self.object.__class__.__name__
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message)

            trigger = {"close-delete-modal": True, "show-message": {"text": success_message, "type": "error"}}
            headers = {'HX-Trigger': json.dumps(trigger)}

            list_view = get_list_view_instance(model_name, self.request)
            context = {'items': list_view.get_queryset(), **list_view.extra_context}
            
            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)
        
        return super().post(request, *args, **kwargs)

# =============================================================================
# --- УПРАВЛЕНИЕ (MANAGEMENT) ---
# =============================================================================
@login_required
def management_dashboard_view(request):
    return render(request, 'management.html')

# =============================================================================
# --- УЧЕБНЫЕ ГОДЫ (ACADEMIC YEAR) ---
# =============================================================================
class AcademicYearListView(HtmxListView):
    model = AcademicYear
    template_name_prefix = 'years'
    extra_context = {
        'title': 'Учебные годы', 
        'add_url': 'core:year_add',
        'edit_url': 'core:year_edit',
        'delete_url': 'core:year_delete'
    }

class AcademicYearCreateView(HtmxCreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

class AcademicYearUpdateView(HtmxUpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

class AcademicYearDeleteView(HtmxDeleteView):
    model = AcademicYear
    template_name = 'years/confirm_delete.html'
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

# =============================================================================
# --- ЧЕТВЕРТИ (QUARTER) ---
# =============================================================================
class QuarterListView(HtmxListView):
    model = Quarter
    template_name_prefix = 'quarters'
    extra_context = {
        'title': 'Четверти',
        'add_url': 'core:quarter_add',
        'edit_url': 'core:quarter_edit',
        'delete_url': 'core:quarter_delete'
    }

    def get_queryset(self):
        # РЕШЕНИЕ: Мы полностью переопределяем (overrides) логику родительского класса.
        # Вместо сложной фильтрации, которая скрывает "пустые" четверти,
        # мы просто возвращаем ВСЕ четверти, так как это базовый справочник.
        # Фильтрация по правам доступа здесь не нужна.
        
        # Мы оставляем оптимизацию `select_related` и сортировку.
        return Quarter.objects.select_related('year').order_by('-year__start_date', 'start_date')

class QuarterCreateView(HtmxCreateView):
    model = Quarter
    form_class = QuarterForm
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

class QuarterUpdateView(HtmxUpdateView):
    model = Quarter
    form_class = QuarterForm
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

class QuarterDeleteView(HtmxDeleteView):
    model = Quarter
    template_name = 'quarters/confirm_delete.html'
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

# =============================================================================
# --- ШКОЛЫ (SCHOOL) ---
# =============================================================================
class SchoolListView(HtmxListView):
    model = School
    template_name_prefix = 'schools'
    extra_context = {
        'title': 'Школы',
        'add_url': 'core:school_add',
        'edit_url': 'core:school_edit',
        'delete_url': 'core:school_delete',
        'table_template': 'schools/_table.html'
    }

    # ✨ ИЗМЕНЕНИЕ: Полностью переопределяем get_queryset ✨
    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'profile', None)

        # 1. Суперпользователь видит все школы
        if user.is_superuser:
            queryset = School.objects.all()
        # 2. Директор видит ТОЛЬКО свои назначенные школы
        elif profile and profile.role == UserProfile.Role.DIRECTOR:
            # Используем M2M поле 'schools' из профиля Директора
            queryset = profile.schools.all()
        # 3. Остальные видят школы согласно общим правилам доступа (на всякий случай)
        else:
            queryset = get_accessible_schools(user)

        # --- Применяем логику сортировки (остается без изменений) ---
        sort_by = self.request.GET.get('sort', 'school_id')
        direction = self.request.GET.get('direction', 'asc')

        allowed_sort_fields = ['school_id', 'name', 'city']
        if sort_by not in allowed_sort_fields:
            sort_by = 'school_id'

        if direction == 'desc':
            sort_by = f'-{sort_by}'

        return queryset.order_by(sort_by)
    # ✨ КОНЕЦ ИЗМЕНЕНИЯ ✨

    def get_context_data(self, **kwargs):
        # Передаем текущие параметры сортировки в шаблон
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'school_id')
        context['current_direction'] = self.request.GET.get('direction', 'asc')
        return context

class SchoolCreateView(HtmxCreateView):
    model = School
    form_class = SchoolForm
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

class SchoolUpdateView(HtmxUpdateView):
    model = School
    form_class = SchoolForm
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

class SchoolDeleteView(HtmxDeleteView):
    model = School
    template_name = 'schools/confirm_delete.html'
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

# =============================================================================
# --- КЛАССЫ (SCHOOL CLASS) ---
# =============================================================================

class SchoolClassListView(HtmxListView):
    # Моделью остаются Школы, так как мы группируем по ним
    model = School
    template_name_prefix = 'classes'
    extra_context = {
        'title': 'Классы',
        'add_url': 'core:class_add',
        'edit_url': 'core:class_edit',
        'delete_url': 'core:class_delete'
    }

    def get_queryset(self):
        # 1. Получаем школы, доступные текущему пользователю
        schools_qs = get_accessible_schools(self.request.user)

        # 2. Оптимизируем запрос: для каждой школы заранее подгружаем
        #    все связанные с ней классы, отсортированные по имени.
        return schools_qs.prefetch_related(
            Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        # Переименовываем queryset в 'schools' для соответствия шаблону
        context = super().get_context_data(**kwargs)
        if 'items' in context:
            context['schools'] = context.pop('items')
        return context

class SchoolClassCreateView(HtmxCreateView):
    model = SchoolClass
    form_class = SchoolClassForm
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if school_id := self.request.GET.get('school'):
            kwargs['school'] = get_object_or_404(School, pk=school_id)
            kwargs['initial'] = {'school': school_id}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school_id_for_htmx'] = self.request.GET.get('school')
        return context

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            school = self.object.school
            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=school.pk)
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SchoolClassUpdateView(HtmxUpdateView):
    model = SchoolClass
    form_class = SchoolClassForm
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object:
            kwargs['school'] = self.object.school
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            school = self.object.school
            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=school.pk)
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SchoolClassDeleteView(HtmxDeleteView):
    model = SchoolClass
    template_name = 'classes/confirm_delete.html'
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            school = self.object.school
            item_name = str(self.object)
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message)

            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=school.pk)
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-delete-modal": True, "show-message": {"text": success_message, "type": "error"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)
        
        return super().post(request, *args, **kwargs)

# =============================================================================
# --- ПРЕДМЕТЫ (SUBJECT) ---
# =============================================================================
class SubjectListView(HtmxListView): # Наследуемся от базового HtmxListView
    model = Subject # ✨ ИЗМЕНЕНИЕ: Модель теперь Subject
    template_name_prefix = 'subjects' # ✨ Указываем префикс для шаблонов
    extra_context = {
        'title': 'Предметы',
        'add_url': 'core:subject_add',
        'edit_url': 'core:subject_edit',
        'delete_url': 'core:subject_delete'
    }

    def get_queryset(self):
        # ✨ ИЗМЕНЕНИЕ: Просто возвращаем все предметы
        # Функция get_accessible_subjects() применяется при *использовании* данных,
        # а для простого списка справочника показываем все админам/директорам.
        # Эксперты/Учителя увидят только свои, если HtmxListView будет доработан,
        # но для базового списка это нормально.
        if self.request.user.is_staff or self.request.user.is_superuser:
             return Subject.objects.all().order_by('name')
        else:
             # Для других ролей можно вернуть пустой список или их предметы,
             # но пока для простоты вернем все (или пустой для безопасности)
             # return Subject.objects.none() # Вариант: Скрыть от не-админов
             return Subject.objects.all().order_by('name') # Вариант: Показать всем

    # ✨ ИЗМЕНЕНИЕ: Метод get_context_data из базового класса HtmxListView
    # уже переименовывает object_list в 'items', так что здесь ничего не нужно
    # def get_context_data(self, **kwargs):
    #     context = super().get_context_data(**kwargs)
    #     # Базовый класс уже помещает queryset в 'items'
    #     return context

# Классы SubjectCreateView, SubjectUpdateView, SubjectDeleteView остаются почти без изменений,
# НО нужно убрать привязку к ШКОЛЕ из form_valid и post, так как предметы глобальные.

class SubjectCreateView(HtmxCreateView):
    model = Subject
    form_class = SubjectForm
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'

    # ✨ ИЗМЕНЕНИЕ: Убираем get_form_kwargs и get_context_data, связанные со школой
    # def get_form_kwargs(self): ...
    # def get_context_data(self, **kwargs): ...

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)

        if self.request.htmx:
            # ✨ ИЗМЕНЕНИЕ: Обновляем весь список предметов, а не карточку школы
            list_view = SubjectListView() # Используем исправленный ListView
            list_view.request = self.request
            context = {'items': list_view.get_queryset(), **list_view.extra_context}
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SubjectUpdateView(HtmxUpdateView):
    model = Subject
    form_class = SubjectForm
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)

        if self.request.htmx:
            # ✨ ИЗМЕНЕНИЕ: Обновляем весь список предметов
            list_view = SubjectListView()
            list_view.request = self.request
            context = {'items': list_view.get_queryset(), **list_view.extra_context}
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SubjectDeleteView(HtmxDeleteView):
    model = Subject
    template_name = 'subjects/confirm_delete.html' # Убедитесь, что этот шаблон существует
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            item_name = str(self.object)
            model_name = self.object.__class__.__name__ # Получаем 'Subject'
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message)

            trigger = {"close-delete-modal": True, "show-message": {"text": success_message, "type": "error"}}
            headers = {'HX-Trigger': json.dumps(trigger)}

            # ✨ ИЗМЕНЕНИЕ: Обновляем весь список предметов
            list_view = SubjectListView()
            list_view.request = self.request
            context = {'items': list_view.get_queryset(), **list_view.extra_context}

            html = render_to_string(f'{self.template_name_prefix}/_table.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return super().post(request, *args, **kwargs)

# =============================================================================
# --- GAT ТЕСТЫ (GAT TEST) ---
# =============================================================================
def gat_test_list_view(request):
    base_qs = GatTest.objects.select_related('school', 'school_class', 'quarter').order_by('-test_date', 'name')
    if not request.user.is_superuser:
        accessible_schools = get_accessible_schools(request.user)
        base_qs = base_qs.filter(school__in=accessible_schools)
    
    grouped_tests = defaultdict(list)
    for test in base_qs:
        if test.school: # ✨✨✨ ДОБАВЛЕНА ЭТА ПРОВЕРКА ✨✨✨
            grouped_tests[test.school].append(test)
    
    sorted_grouped_tests = dict(sorted(grouped_tests.items(), key=lambda item: item[0].name))
    context = {'grouped_tests': sorted_grouped_tests, 'title': 'GAT Тесты'}
    return render(request, 'gat_tests/list.html', context)

def get_form_kwargs_for_gat(request, instance=None):
    """Вспомогательная функция для получения kwargs для GatTestForm."""
    kwargs = {'instance': instance}
    # Определяем ID школы из POST, GET или существующего объекта
    school_id = request.POST.get('school') or request.GET.get('school')
    if not school_id and instance:
        school_id = instance.school_id

    if school_id:
        try:
            kwargs['school'] = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            pass
    return kwargs

class GatTestCreateView(HtmxCreateView):
    model = GatTest
    form_class = GatTestForm
    template_name_prefix = 'gat_tests'
    list_url_name = 'core:gat_test_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Назначить GAT Тест'
        return context

    def form_valid(self, form):
        # Сохраняем основной объект GatTest
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        
        # ✨ НОВЫЙ КОД: Сохраняем количество вопросов для каждого выбранного предмета
        subjects = form.cleaned_data.get('subjects')
        school_class = form.cleaned_data.get('school_class')

        if subjects and school_class:
            for subject in subjects:
                # Ищем в POST-запросе поле с названием 'questions_ID', где ID - это id предмета
                question_count_key = f'questions_{subject.id}'
                if question_count_key in self.request.POST:
                    number_of_questions = self.request.POST.get(question_count_key)
                    # Если значение не пустое, создаем или обновляем запись QuestionCount
                    if number_of_questions:
                        QuestionCount.objects.update_or_create(
                            school_class=school_class,
                            subject=subject,
                            defaults={'number_of_questions': int(number_of_questions)}
                        )
        
        # --- (остальная часть функции остается без изменений) ---
        if self.request.htmx:
            base_qs = GatTest.objects.select_related('school', 'school_class', 'quarter').order_by('-test_date', 'name')
            if not self.request.user.is_superuser:
                accessible_schools = get_accessible_schools(self.request.user)
                base_qs = base_qs.filter(school__in=accessible_schools)
            
            grouped_tests = defaultdict(list)
            for test in base_qs:
                if test.school:
                    grouped_tests[test.school].append(test)
            
            sorted_grouped_tests = dict(sorted(grouped_tests.items(), key=lambda item: item[0].name))
            
            html = render_to_string(
                'gat_tests/partials/_test_list_content.html', 
                {'grouped_tests': sorted_grouped_tests, 'user': self.request.user},
                request=self.request
            )
            
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger), 'HX-Retarget': '#test-list-container', 'HX-Reswap': 'innerHTML'}
            
            return HttpResponse(html, headers=headers)

        messages.success(self.request, success_message)
        return redirect(reverse_lazy(self.list_url_name))

    def form_invalid(self, form):
        print("ОШИБКИ ВАЛИДАЦИИ ФОРМЫ:", form.errors) 
        if self.request.htmx:
            school_id = self.request.POST.get('school')
            if school_id:
                try:
                    school = School.objects.get(pk=school_id)
                    form.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, parent__isnull=True).order_by('name')
                    form.fields['subjects'].queryset = Subject.objects.filter(school=school).order_by('name')
                except School.DoesNotExist:
                    pass
            
            response = render(self.request, 'gat_tests/_form_content.html', self.get_context_data(form=form))
            response['HX-Retrigger'] = 'form-validation-error'
            return response
        
        return super().form_invalid(form)


class GatTestUpdateView(HtmxUpdateView):
    model = GatTest
    form_class = GatTestForm
    template_name_prefix = 'gat_tests'
    list_url_name = 'core:gat_test_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактировать GAT Тест'
        return context

    def form_valid(self, form):
        # ✨ ЛОГИКА СОХРАНЕНИЯ ЗДЕСЬ ИДЕНТИЧНА CREATEVIEW ✨
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'

        subjects = form.cleaned_data.get('subjects')
        school_class = form.cleaned_data.get('school_class')

        if subjects and school_class:
            for subject in subjects:
                question_count_key = f'questions_{subject.id}'
                if question_count_key in self.request.POST:
                    number_of_questions = self.request.POST.get(question_count_key)
                    if number_of_questions:
                        QuestionCount.objects.update_or_create(
                            school_class=school_class,
                            subject=subject,
                            defaults={'number_of_questions': int(number_of_questions)}
                        )
        
        # --- (остальная часть функции остается без изменений) ---
        if self.request.htmx:
            base_qs = GatTest.objects.select_related('school', 'school_class', 'quarter').order_by('-test_date', 'name')
            if not self.request.user.is_superuser:
                accessible_schools = get_accessible_schools(self.request.user)
                base_qs = base_qs.filter(school__in=accessible_schools)
            
            grouped_tests = defaultdict(list)
            for test in base_qs:
                if test.school:
                    grouped_tests[test.school].append(test)
            
            sorted_grouped_tests = dict(sorted(grouped_tests.items(), key=lambda item: item[0].name))
            
            html = render_to_string(
                'gat_tests/partials/_test_list_content.html', 
                {'grouped_tests': sorted_grouped_tests, 'user': self.request.user},
                request=self.request
            )
            
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger), 'HX-Retarget': '#test-list-container', 'HX-Reswap': 'innerHTML'}

            return HttpResponse(html, headers=headers)
        
        messages.success(self.request, success_message)
        return redirect(reverse_lazy(self.list_url_name))

    def form_invalid(self, form):
        if self.request.htmx:
            school_id = self.request.POST.get('school')
            if school_id:
                try:
                    school = School.objects.get(pk=school_id)
                    form.fields['school_class'].queryset = SchoolClass.objects.filter(school=school, parent__isnull=True).order_by('name')
                    form.fields['subjects'].queryset = Subject.objects.filter(school=school).order_by('name')
                except School.DoesNotExist:
                    pass
            
            response = render(self.request, 'gat_tests/_form_content.html', self.get_context_data(form=form))
            response['HX-Retrigger'] = 'form-validation-error'
            return response

        return super().form_invalid(form)

class GatTestDeleteView(HtmxDeleteView):
    model = GatTest
    template_name = 'gat_tests/confirm_delete.html'
    template_name_prefix = 'gat_tests'
    list_url_name = 'core:gat_test_list'

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            school = self.object.school 
            item_name = str(self.object)
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'

            trigger = {"close-delete-modal": True, "show-message": {"text": success_message, "type": "error"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            
            # ✨✨✨ ОБНОВЛЕННАЯ ЛОГИКА ✨✨✨
            # После удаления мы заново запрашиваем все тесты, чтобы перестроить весь список
            base_qs = GatTest.objects.select_related('school', 'school_class', 'quarter').order_by('-test_date', 'name')
            if not self.request.user.is_superuser:
                accessible_schools = get_accessible_schools(self.request.user)
                base_qs = base_qs.filter(school__in=accessible_schools)
            
            grouped_tests = defaultdict(list)
            for test in base_qs:
                if test.school:
                    grouped_tests[test.school].append(test)
            
            sorted_grouped_tests = dict(sorted(grouped_tests.items(), key=lambda item: item[0].name))
            
            html = render_to_string(
                'gat_tests/partials/_test_list_content.html', 
                {'grouped_tests': sorted_grouped_tests, 'user': self.request.user},
                request=self.request
            )
            
            # Указываем HTMX, что нужно заменить весь контейнер
            headers['HX-Retarget'] = '#test-list-container'
            headers['HX-Reswap'] = 'innerHTML'
            
            return HttpResponse(html, headers=headers)

        # Этот код остается для случаев без HTMX
        return super().post(request, *args, **kwargs)

@login_required
def gat_test_delete_results_view(request, pk):
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
        'cancel_url': 'core:gat_test_list'
    }
    return render(request, 'results/confirm_delete_batch.html', context)

# =============================================================================
# --- ЗАМЕТКИ УЧИТЕЛЯ (TEACHER NOTE) ---
# =============================================================================
class TeacherNoteCreateView(LoginRequiredMixin, CreateView):
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

# =============================================================================
# --- КОЛИЧЕСТВО ВОПРОСОВ (QUESTION COUNT) ---
# =============================================================================
class QuestionCountListView(HtmxListView):
    model = School
    template_name_prefix = 'question_counts'
    extra_context = {
        'title': 'Количество вопросов',
        'management_url': 'core:management',
        'single_add_url': 'core:question_count_add',
        'bulk_add_url': 'core:question_count_bulk_add',
        'edit_url': 'core:question_count_edit',
        'delete_url': 'core:question_count_delete',
    }
    
    def get_queryset(self):
        return get_accessible_schools(self.request.user).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        schools_list = list(context.pop('items', []))
        school_ids = [s.id for s in schools_list]
        all_qcs = QuestionCount.objects.filter(
            school_class__school_id__in=school_ids
        ).select_related('subject', 'school_class').order_by('subject__name')
        qcs_by_school = defaultdict(list)
        for qc in all_qcs:
            qcs_by_school[qc.school_class.school_id].append(qc)
        for school in schools_list:
            school.all_question_counts = qcs_by_school[school.id]
        context['schools'] = schools_list
        return context

class QuestionCountCreateView(HtmxCreateView):
    model = QuestionCount
    form_class = QuestionCountForm
    template_name_prefix = 'question_counts'
    list_url_name = 'core:question_count_list'

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            school = self.object.school_class.school
            return _get_question_count_htmx_response(self.request, school, success_message)

        return redirect(reverse_lazy(self.list_url_name))

class QuestionCountUpdateView(HtmxUpdateView):
    model = QuestionCount
    form_class = QuestionCountForm
    template_name_prefix = 'question_counts'
    list_url_name = 'core:question_count_list'

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            school = self.object.school_class.school
            return _get_question_count_htmx_response(self.request, school, success_message)

        return redirect(reverse_lazy(self.list_url_name))

class QuestionCountDeleteView(HtmxDeleteView):
    model = QuestionCount
    template_name_prefix = 'question_counts'
    list_url_name = 'core:question_count_list'

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            school = self.object.school_class.school
            item_name = str(self.object)
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message)
            
            return _get_question_count_htmx_response(
                self.request, 
                school, 
                success_message, 
                message_type='error', 
                is_delete=True
            )
        
        return super().post(request, *args, **kwargs)

class QuestionCountBulkCreateView(HtmxFormView):
    form_class = QuestionCountBulkSchoolForm
    template_name_prefix = 'question_counts'
    list_url_name = 'core:question_count_list'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Массовое добавление"
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        if self.request.method in ('GET', 'POST'):
            data = self.request.GET.copy()
            data.update(self.request.POST)
            kwargs['data'] = data
        return kwargs

    def get(self, request, *args, **kwargs):
        form = self.get_form()
        
        if 'schools' in request.GET:
            template = 'question_counts/partials/_bulk_modal_step_3_fields.html'
            return render(request, template, {'form': form})

        if 'academic_year' in request.GET:
            template = 'question_counts/partials/_bulk_modal_step_2_schools.html'
            return render(request, template, {'form': form})
        
        return super().get(request, *args, **kwargs)

    def get_template_names(self):
        if self.request.htmx:
            return [f'{self.template_name_prefix}/bulk_form_modal.html']
        return [f'{self.template_name_prefix}/form.html']

    def form_valid(self, form):
        schools = form.cleaned_data['schools']
        school_class = form.cleaned_data['school_class']
        subject = form.cleaned_data['subject']
        number = form.cleaned_data['number_of_questions']
        
        updated_count = 0
        created_count = 0

        for school in schools:
            target_class = SchoolClass.objects.get(school=school, name=school_class.name)
            
            _, created = QuestionCount.objects.update_or_create(
                school_class=target_class,
                subject=subject,
                defaults={'number_of_questions': number}
            )
            if created: created_count += 1
            else: updated_count += 1
        
        success_message = f"Операция завершена. Создано: {created_count}, обновлено: {updated_count}."
        messages.success(self.request, success_message)

        if self.request.htmx:
            trigger = {
                "close-modal": True, 
                "show-message": {"text": success_message, "type": "success"},
                "force-refresh": True 
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))