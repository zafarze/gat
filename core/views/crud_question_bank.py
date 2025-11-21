# D:\GAT\core\views\crud_question_bank.py (ИСПРАВЛЕННЫЙ ФАЙЛ)

import json
import logging
from collections import defaultdict
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.template.loader import render_to_string
from django.db.models import Prefetch, Count, Q
from django.forms import inlineformset_factory
from django.forms import inlineformset_factory, BaseInlineFormSet
from django.core.exceptions import ValidationError
from django.shortcuts import render, redirect, get_object_or_404 
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, JsonResponse
from django.views.decorators.http import require_POST
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from core.forms import ImportQuestionForm
from core.import_service import process_import

# АБСОЛЮТНЫЕ ИМПОРТЫ
from core.models import (
    School, SchoolClass, Subject, QuestionCount,
    QuestionTopic, BankQuestion, BankAnswerOption 
)
from accounts.models import UserProfile
from core.forms import (
    QuestionCountForm, QuestionCountBulkSchoolForm,
    QuestionTopicForm, BankQuestionForm,
    BankAnswerOptionForm
)
from core.views.permissions import get_accessible_schools, get_accessible_subjects
from .crud_base import (
    HtmxListView, HtmxCreateView, HtmxUpdateView, HtmxDeleteView, HtmxFormView
)

# =============================================================================
# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
# =============================================================================

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
        "show-message": {"text": success_message, "type": message_type},
        f"force-refresh-{school.id}": True
    }

    headers = {'HX-Trigger': json.dumps(trigger)}
    return HttpResponse(status=204, headers=headers)


# =============================================================================
# --- ФОРМСЕТ ДЛЯ ВАРИАНТОВ ОТВЕТОВ ---
# =============================================================================

# --- 👇 СНАЧАЛА ОПРЕДЕЛЯЕМ КЛАСС 👇 ---
class BaseBankAnswerOptionFormSet(BaseInlineFormSet):
    def clean(self):
        """Проверки: ровно один правильный, нет дубликатов, ровно 4 варианта."""
        super().clean()

        correct_count = 0
        forms_to_count = 0
        seen_texts = set() # Для проверки дубликатов

        for form in self.forms:
            if not form.is_valid() or (self.can_delete and form.cleaned_data.get('DELETE', False)):
                continue
            
            forms_to_count += 1
            
            # 1. Проверка правильного ответа
            if form.cleaned_data.get('is_correct'):
                correct_count += 1
            
            # 2. Проверка на дубликаты текстов (Requirement #2)
            text = form.cleaned_data.get('text', '').strip().lower()
            if text in seen_texts:
                raise ValidationError(f'Вариант ответа "{form.cleaned_data.get("text")}" повторяется. Варианты должны быть уникальными.')
            seen_texts.add(text)

        # 3. Строго 4 варианта (Requirement #1)
        if forms_to_count != 4:
             raise ValidationError(f'Вопрос должен иметь ровно 4 варианта ответа. Сейчас заполнено: {forms_to_count}.')

        if forms_to_count > 0 and correct_count != 1:
            raise ValidationError('Должен быть выбран ровно один правильный вариант ответа.')
# --- КОНЕЦ ОПРЕДЕЛЕНИЯ КЛАССА ---


# --- 👇 ПОТОМ ИСПОЛЬЗУЕМ ЕГО ЗДЕСЬ 👇 ---
BankAnswerOptionFormSet = inlineformset_factory(
    BankQuestion,
    BankAnswerOption,
    form=BankAnswerOptionForm,
    formset=BaseBankAnswerOptionFormSet,
    extra=4,      # Предлагать сразу 4 поля
    min_num=4,    # Минимум 4
    max_num=4,    # Максимум 4
    validate_min=True,
    validate_max=True,
    can_delete=False # Запрещаем удалять, так как должно быть строго 4
)
# =============================================================================
# --- ТЕМЫ ВОПРОСОВ (QUESTION TOPIC) ---
# =============================================================================

class QuestionTopicListView(HtmxListView):
    model = QuestionTopic
    template_name_prefix = 'question_topics'
    context_object_name = 'items'

    extra_context = {
        'title': 'Темы вопросов',
        'add_url': 'core:question_topic_add',
        'edit_url': 'core:question_topic_edit',
        'delete_url': 'core:question_topic_delete'
    }

    def get_queryset(self):
        # --- Этот метод УЖЕ правильный, он считает вопросы в теме ---
        qs = QuestionTopic.objects.annotate(
            question_count=Count('questions') # Считаем BankQuestion через related_name='questions'
        ).select_related(
            'subject', 'school_class__school', 'author'
        )
        # --- Конец ---

        user = self.request.user
        if not user.is_superuser:
            accessible_subjects = get_accessible_subjects(user)
            accessible_schools = get_accessible_schools(user)
            qs = qs.filter(
                subject__in=accessible_subjects,
                school_class__school__in=accessible_schools
            )
        self.selected_subject_id = self.request.GET.get('subject_id')
        self.selected_school_id = self.request.GET.get('school_id')
        self.selected_class_id = self.request.GET.get('class_id')
        if self.selected_class_id:
            qs = qs.filter(
                subject_id=self.selected_subject_id,
                school_class__school_id=self.selected_school_id,
                school_class_id=self.selected_class_id
            )
        else:
            qs = qs.none() # Темы показываем только на последнем шаге
        return qs.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Получаем GET-параметры
        self.selected_subject_id = self.request.GET.get('subject_id')
        self.selected_school_id = self.request.GET.get('school_id')
        self.selected_class_id = self.request.GET.get('class_id')

        # --- Предметы (Шаг 1) ---
        subjects_qs = Subject.objects.all().order_by('name')
        is_expert_or_teacher = False
        if not user.is_superuser:
            subjects_qs = get_accessible_subjects(user)
            if hasattr(user, 'profile') and user.profile.role in [UserProfile.Role.EXPERT, UserProfile.Role.TEACHER, UserProfile.Role.HOMEROOM_TEACHER]:
                 is_expert_or_teacher = True

        accessible_schools = get_accessible_schools(user)
        # --- 👇 ИЗМЕНЕНИЕ: Считаем ВОПРОСЫ (BankQuestion) по предмету 👇 ---
        subjects_for_context = subjects_qs.annotate(
            question_count=Count( # Меняем topic_count на question_count
                'bank_questions', # Считаем через M2M/FK связь Subject -> BankQuestion
                filter=Q(bank_questions__school_class__school__in=accessible_schools), # Учитываем доступные школы
                distinct=True # Считаем уникальные вопросы
            )
        )
        # --- КОНЕЦ ИЗМЕНЕНИЯ ---

        # Логика автовыбора предмета для Эксперта/Учителя
        if is_expert_or_teacher and subjects_for_context.count() == 1 and not self.selected_subject_id:
            first_subject = subjects_for_context.first()
            if first_subject: # Добавлена проверка на случай пустого queryset
                self.selected_subject_id = first_subject.id
                context['auto_selected_subject'] = True

        context['subjects'] = subjects_for_context

        # --- Школы (Шаг 2) ---
        schools_qs = School.objects.none()
        selected_subject = None
        if self.selected_subject_id:
            try:
                selected_subject = Subject.objects.get(pk=self.selected_subject_id)
                # --- 👇 ИЗМЕНЕНИЕ: Считаем ВОПРОСЫ (BankQuestion) по школе и предмету 👇 ---
                schools_qs = accessible_schools.annotate(
                    question_count=Count( # Меняем topic_count на question_count
                        'classes__bank_questions', # School -> SchoolClass -> BankQuestion
                        filter=Q(classes__bank_questions__subject_id=self.selected_subject_id),
                        distinct=True
                    )
                ).distinct().order_by('name') # distinct() нужен из-за M2M/FK в аннотации
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            except Subject.DoesNotExist:
                 self.selected_subject_id = None # Сбрасываем ID, если предмет не найден
        context['schools'] = schools_qs
        context['selected_subject'] = selected_subject

        # --- Классы (Шаг 3) ---
        classes_qs = SchoolClass.objects.none()
        selected_school = None
        if self.selected_subject_id and self.selected_school_id:
            try:
                # Убеждаемся, что школа доступна пользователю
                selected_school = accessible_schools.get(pk=self.selected_school_id)
                # --- 👇 ИЗМЕНЕНИЕ: Считаем ВОПРОСЫ (BankQuestion) по классу(параллели) и предмету 👇 ---
                classes_qs = SchoolClass.objects.filter(
                    school_id=self.selected_school_id,
                    parent__isnull=True, # Только параллели
                ).annotate(
                    question_count=Count( # Меняем topic_count на question_count
                        'bank_questions', # SchoolClass (параллель) -> BankQuestion
                        filter=Q(bank_questions__subject_id=self.selected_subject_id),
                        distinct=True
                    )
                ).distinct().order_by('name') # distinct() нужен из-за M2M/FK в аннотации
                # --- КОНЕЦ ИЗМЕНЕНИЯ ---
            except School.DoesNotExist:
                 self.selected_school_id = None # Сбрасываем ID, если школа не найдена/недоступна
        context['classes'] = classes_qs
        context['selected_school'] = selected_school

        # --- Выбранный класс (Шаг 4 - для таблицы тем) ---
        selected_class = None
        if self.selected_class_id:
             try:
                 # Проверяем, что класс принадлежит выбранной школе
                 selected_class = SchoolClass.objects.get(pk=self.selected_class_id, school_id=self.selected_school_id)
             except SchoolClass.DoesNotExist:
                 self.selected_class_id = None # Сбрасываем ID, если класс не найден
        context['selected_class'] = selected_class

        # Передаем ID (убедимся, что они числа или None)
        context['selected_subject_id'] = int(self.selected_subject_id) if self.selected_subject_id else None
        context['selected_school_id'] = int(self.selected_school_id) if self.selected_school_id else None
        context['selected_class_id'] = int(self.selected_class_id) if self.selected_class_id else None

        return context

    def get_template_names(self):
        # Этот метод остается без изменений
        if self.request.htmx:
            return ['question_topics/partials/_content_area.html']
        return ['question_topics/list.html']

# -------------------------------------------------------------------------
# --- ✨✨✨ ИСПРАВЛЕНИЕ 1: CREATE VIEW ✨✨✨ ---
# -------------------------------------------------------------------------
class QuestionTopicCreateView(HtmxCreateView):
    model = QuestionTopic
    form_class = QuestionTopicForm
    template_name_prefix = 'question_topics'
    list_url_name = 'core:question_topic_list'
    
    def get_context_data(self, **kwargs):
        # Добавляем title для модального окна
        context = super().get_context_data(**kwargs)
        context['title'] = 'Добавить тему'
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        # Предзаполнение формы из GET-параметров
        initial = kwargs.get('initial', {})
        if subject_id := self.request.GET.get('subject'): initial['subject'] = subject_id
        if class_id := self.request.GET.get('class'): initial['school_class'] = class_id
        kwargs['initial'] = initial
        return kwargs

    def form_valid(self, form):
        form.instance.author = self.request.user
        self.object = form.save()
        
        # --- ✨ ИСПРАВЛЕНИЕ: Ручной HTMX-ответ ---
        if self.request.htmx:
            # 1. Получаем фильтры из созданного объекта
            subject_id = self.object.subject_id
            school_id = self.object.school_class.school_id
            class_id = self.object.school_class_id
            
            # 2. Получаем новый список тем для таблицы
            items = QuestionTopic.objects.filter(
                subject_id=subject_id,
                school_class__school_id=school_id,
                school_class_id=class_id
            ).select_related(
                'subject', 'school_class__school', 'author'
            ).order_by('name')
            
            # 3. Рендерим только таблицу
            html = render_to_string(
                'question_topics/_table.html', 
                {
                    'items': items,
                    'edit_url': 'core:question_topic_edit',
                    'delete_url': 'core:question_topic_delete'
                }, 
                request=self.request
            )
            
            # 4. Отправляем HTML с триггерами
            headers = {
                'HX-Trigger': json.dumps({
                    "close-modal": True,
                    "show-message": {
                        "text": f"Тема '{self.object.name}' успешно создана.",
                        "type": "success"
                    }
                })
            }
            return HttpResponse(html, headers=headers)
        
        # Обычный ответ для не-HTMX запросов
        return super().form_valid(form)

# -------------------------------------------------------------------------
# --- ✨✨✨ ИСПРАВЛЕНИЕ 2: UPDATE VIEW ✨✨✨ ---
# -------------------------------------------------------------------------
class QuestionTopicUpdateView(HtmxUpdateView):
    model = QuestionTopic
    form_class = QuestionTopicForm
    template_name_prefix = 'question_topics'
    list_url_name = 'core:question_topic_list'

    def get_context_data(self, **kwargs):
        # Добавляем title для модального окна
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактировать тему'
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
        
    def form_valid(self, form):
        self.object = form.save()
        
        # --- ✨ ИСПРАВЛЕНИЕ: Ручной HTMX-ответ ---
        if self.request.htmx:
            # 1. Получаем фильтры
            subject_id = self.object.subject_id
            school_id = self.object.school_class.school_id
            class_id = self.object.school_class_id
            
            # 2. Получаем новый список тем
            items = QuestionTopic.objects.filter(
                subject_id=subject_id,
                school_class__school_id=school_id,
                school_class_id=class_id
            ).select_related(
                'subject', 'school_class__school', 'author'
            ).order_by('name')
            
            # 3. Рендерим таблицу
            html = render_to_string(
                'question_topics/_table.html', 
                {
                    'items': items,
                    'edit_url': 'core:question_topic_edit',
                    'delete_url': 'core:question_topic_delete'
                }, 
                request=self.request
            )
            
            # 4. Отправляем HTML с триггерами
            headers = {
                'HX-Trigger': json.dumps({
                    "close-modal": True,
                    "show-message": {
                        "text": f"Тема '{self.object.name}' успешно обновлена.",
                        "type": "success"
                    }
                })
            }
            return HttpResponse(html, headers=headers)

        return super().form_valid(form)

# -------------------------------------------------------------------------
# --- ✨✨✨ ИСПРАВЛЕНИЕ 3: DELETE VIEW ✨✨✨ ---
# -------------------------------------------------------------------------
class QuestionTopicDeleteView(HtmxDeleteView):
    model = QuestionTopic
    template_name = 'question_topics/confirm_delete.html'
    template_name_prefix = 'question_topics'
    list_url_name = 'core:question_topic_list'
    
    # --- ✨ ИСПРАВЛЕНИЕ 3.1: Добавляем title (Чинит ошибку 500) ---
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Удалить тему'
        return context

    # --- ✨ ИСПРАВЛЕНИЕ 3.2: Добавляем POST для HTMX ---
    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            
            # Получаем фильтры *до* удаления
            subject_id = self.object.subject_id
            school_id = self.object.school_class.school_id
            class_id = self.object.school_class_id
            item_name = str(self.object)
            
            # Удаляем объект
            self.object.delete()
            
            # Получаем новый список тем
            items = QuestionTopic.objects.filter(
                subject_id=subject_id,
                school_class__school_id=school_id,
                school_class_id=class_id
            ).select_related(
                'subject', 'school_class__school', 'author'
            ).order_by('name')
            
            # Рендерим таблицу
            html = render_to_string(
                'question_topics/_table.html', 
                {
                    'items': items,
                    'edit_url': 'core:question_topic_edit',
                    'delete_url': 'core:question_topic_delete'
                }, 
                request=request
            )
            
            # Отправляем HTML с триггерами
            headers = {
                'HX-Trigger': json.dumps({
                    "close-delete-modal": True, # Закрываем модальное окно удаления
                    "show-message": {
                        "text": f"Тема '{item_name}' успешно удалена.",
                        "type": "error" # Красное оповещение
                    }
                })
            }
            return HttpResponse(html, headers=headers)

        # Обычный ответ для не-HTMX запросов
        return super().post(request, *args, **kwargs)


# =============================================================================
# --- БАНК ВОПРОСОВ (BANK QUESTION) ---
# =============================================================================

class BankQuestionListView(HtmxListView):
    # ... (Этот класс остается без изменений, как мы настроили ранее) ...
    model = BankQuestion
    template_name_prefix = 'bank_questions'
    context_object_name = 'items'
    paginate_by = 20
    extra_context = {
        'title': 'Банк Вопросов',
        'add_url': 'core:bank_question_add',
        'edit_url': 'core:bank_question_edit',
        'delete_url': 'core:bank_question_delete'
    }

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if not user.is_superuser:
            accessible_subjects = get_accessible_subjects(user)
            qs = qs.filter(subject__in=accessible_subjects)

        topic_id = self.request.GET.get('topic')
        if topic_id:
            qs = qs.filter(topic_id=topic_id)

        return qs.select_related(
            'subject', 'school_class', 'topic', 'author'
        ).order_by('topic__subject__name', 'topic__name', '-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        topics_qs = QuestionTopic.objects.select_related('subject', 'school_class')
        if not user.is_superuser:
            accessible_subjects = get_accessible_subjects(user)
            accessible_schools = get_accessible_schools(user)
            topics_qs = topics_qs.filter(
                subject__in=accessible_subjects,
                school_class__school__in=accessible_schools
            )

        context['topics_for_filter'] = topics_qs.order_by('subject__name', 'name')
        return context


class BankQuestionCreateView(HtmxCreateView):
    model = BankQuestion
    form_class = BankQuestionForm
    template_name_prefix = 'bank_questions'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Добавить вопрос в Банк'
        if self.request.POST:
            context['options_formset'] = BankAnswerOptionFormSet(self.request.POST, self.request.FILES, prefix='options')
        else:
            context['options_formset'] = BankAnswerOptionFormSet(prefix='options')
            context['options_formset_initial_json'] = '[]'
        
        # Добавляем object=None для избежания ошибки в шаблоне
        context['object'] = None
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
        # Для CreateView instance должен быть None
        self.object = None
        form = BankQuestionForm(request.POST, request.FILES, instance=self.object)
        options_formset = BankAnswerOptionFormSet(request.POST, request.FILES, instance=self.object, prefix='options')

        # === УПРОЩЕННАЯ ВЕРСИЯ БЕЗ ЛОГГИНГА ===
        if form.is_valid() and options_formset.is_valid():
            return self.form_valid(form, options_formset)
        else:
            return self.form_invalid(form, options_formset)

    def form_valid(self, form, options_formset):
        """ Сохраняем вопрос и связанные варианты """
        form.instance.author = self.request.user
        self.object = form.save()
        options_formset.instance = self.object
        options_formset.save()

        success_message = f"Вопрос '{self.object.text[:50]}...' успешно создан."
        messages.success(self.request, success_message)

        if self.request.htmx:
            trigger = {
                "close-modal": True,
                "show-message": {"text": success_message, "type": "success"},
                "force-refresh": True
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy('core:bank_question_list'))

    # -------------------------------------------------------------------------
    # --- ✨✨✨ ИСПРАВЛЕНИЕ 4: CREATE VIEW FORM_INVALID ✨✨✨ ---
    # -------------------------------------------------------------------------
    def form_invalid(self, form, options_formset):
        """ Перерисовываем форму с ошибками (для HTMX), СОХРАНЯЯ ДАННЫЕ """
        
        # --- ✨ НОВОЕ: Собираем JSON из отправленных данных ---
        # Это нужно, чтобы Alpine.js воссоздал состояние формы
        submitted_options_data = []
        for form_in_fs in options_formset:
            data = {
                # .value() получает привязанное значение (то, что было в POST)
                'text': form_in_fs['text'].value() or '', 
                'is_correct': form_in_fs['is_correct'].value() or False,
                'id': form_in_fs['id'].value() or '',
                'DELETE': form_in_fs['DELETE'].value() or False,
                'option_image_url': None # При создании нет существующих изображений
            }
            submitted_options_data.append(data)
        # --- КОНЕЦ НОВОГО ---

        context = {
            'form': form,
            'options_formset': options_formset,
            # --- ✨ ИЗМЕНЕНИЕ: Используем собранный JSON ---
            'options_formset_initial_json': json.dumps(submitted_options_data),
            'title': 'Добавить вопрос в Банк',
            'object': None
        }
        
        response = render(self.request, f'{self.template_name_prefix}/partials/_form_content.html', context)
        response.status_code = 422 # 422 Unprocessable Entity
        return response


# =============================================================================
# --- БАНК ВОПРОСОВ (BANK QUESTION) ---
# =============================================================================

class BankQuestionUpdateView(HtmxUpdateView):
    model = BankQuestion
    form_class = BankQuestionForm
    template_name_prefix = 'bank_questions'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактировать вопрос Банка'

        initial_options_data = []

        if self.request.POST:
            # === ВЫЗОВ ИЗ FORM_INVALID (POST-запрос) ===
            options_formset = kwargs.get('options_formset')
            if not options_formset:
                options_formset = BankAnswerOptionFormSet(self.request.POST, self.request.FILES, instance=self.object, prefix='options')

            # Проходим по *формам* в невалидном формсете
            for i, form_in_fs in enumerate(options_formset):
                # === ИСПРАВЛЕНИЕ: Правильно получаем ID из instance если нет в POST ===
                option_id = form_in_fs['id'].value()
                if not option_id and hasattr(form_in_fs, 'instance') and form_in_fs.instance.pk:
                    option_id = form_in_fs.instance.pk

                data = {
                    'text': form_in_fs['text'].value() or '',
                    'is_correct': form_in_fs['is_correct'].value() or False,
                    'id': option_id or '',  # Используем полученный ID
                    'DELETE': form_in_fs['DELETE'].value() or False,
                    'option_image_url': None
                }

                # Безопасная проверка существующего изображения
                try:
                    if (hasattr(form_in_fs, 'instance') and 
                        form_in_fs.instance and 
                        form_in_fs.instance.pk and 
                        hasattr(form_in_fs.instance, 'option_image') and 
                        form_in_fs.instance.option_image):
                        
                        clear_field_name = f'options-{i}-option_image-clear'
                        should_clear = self.request.POST.get(clear_field_name) == 'on'
                        
                        if not should_clear:
                            try:
                                data['option_image_url'] = form_in_fs.instance.option_image.url
                            except ValueError:
                                data['option_image_url'] = None
                except (AttributeError, ValueError) as e:
                    data['option_image_url'] = None

                initial_options_data.append(data)

        else:
                # === ОБЫЧНЫЙ GET-ЗАПРОС ===
                options_formset = BankAnswerOptionFormSet(instance=self.object, prefix='options')
    
                # Проходим по формам в формсете, созданном из instance
                for form_in_fs in options_formset:
                    
                    # --- ✨✨✨ ГЛАВНОЕ ИСПРАВЛЕНИЕ: Создаем словарь вручную ---
                    # Вместо .initial.copy(), чтобы избежать ImageFieldFile
                    initial_data = {
                        'text': form_in_fs.initial.get('text', ''),
                        'is_correct': form_in_fs.initial.get('is_correct', False),
                        'id': '', # Заполним ниже
                        'DELETE': False,
                        'option_image_url': None # Заполним ниже
                    }
                    # --- ✨✨✨ КОНЕЦ ГЛАВНОГО ИСПРАВЛЕНИЯ ---
    
                    # --- Получаем ID из instance ---
                    if form_in_fs.instance and form_in_fs.instance.pk:
                        initial_data['id'] = form_in_fs.instance.pk
                    
                    # --- Добавляем URL изображения (если есть) ---
                    try:
                        if (form_in_fs.instance and 
                            form_in_fs.instance.pk and 
                            form_in_fs.instance.option_image):
                            initial_data['option_image_url'] = form_in_fs.instance.option_image.url
                    except (AttributeError, ValueError):
                        initial_data['option_image_url'] = None # На случай, если файл удален
                    
                    # --- Добавляем готовый JSON-безопасный словарь в список ---
                    initial_options_data.append(initial_data)
                    # --- ✨✨✨ КОНЕЦ ГЛАВНОГО ИСПРАВЛЕНИЯ ---

        context['options_formset'] = options_formset
        context['options_formset_initial_json'] = json.dumps(initial_options_data)
        
        if 'form' in kwargs:
            context['form'] = kwargs['form']
            
        return context

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        form = BankQuestionForm(request.POST, request.FILES, instance=self.object)
        options_formset = BankAnswerOptionFormSet(request.POST, request.FILES, instance=self.object, prefix='options')

        # === ИСПРАВЛЕНИЕ: Используем импортированный logging ===
        logger = logging.getLogger(__name__)
        logger.info(f"Form valid: {form.is_valid()}")
        logger.info(f"Formset valid: {options_formset.is_valid()}")
        
        if not options_formset.is_valid():
            logger.error(f"Formset errors: {options_formset.errors}")
            logger.error(f"Formset non-form errors: {options_formset.non_form_errors()}")

        if form.is_valid() and options_formset.is_valid():
            return self.form_valid(form, options_formset)
        else:
            return self.form_invalid(form, options_formset)

    def form_valid(self, form, options_formset):
        self.object = form.save()
        options_formset.save()

        success_message = f"Вопрос '{self.object.text[:50]}...' успешно обновлен."
        
        if self.request.htmx:
            trigger = {
                "close-modal": True,
                "show-message": {"text": success_message, "type": "success"},
                "force-refresh": True
            }
            headers = {'HX-Trigger': json.dumps(trigger)}
            return HttpResponse(status=204, headers=headers)

        return redirect(reverse_lazy('core:bank_question_list'))

    def form_invalid(self, form, options_formset):
        """ Перерисовываем форму с ошибками (для HTMX) """
        logger = logging.getLogger(__name__)
        logger.error(f"Form errors: {form.errors}")
        logger.error(f"Formset errors: {options_formset.errors}")
        logger.error(f"Formset non-form errors: {options_formset.non_form_errors()}")
        
        context = self.get_context_data(form=form, options_formset=options_formset)
        response = render(self.request, f'{self.template_name_prefix}/partials/_form_content.html', context)
        response.status_code = 422 
        return response 
# --- Этот класс остается БЕЗ ИЗМЕНЕНИЙ ---
class BankQuestionDeleteView(HtmxDeleteView):
    model = BankQuestion
    template_name = 'bank_questions/confirm_delete.html'
    template_name_prefix = 'bank_questions'
    list_url_name = 'core:bank_question_list'
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
        # Этот view отвечает за модальное окно
        return ['question_counts/form_modal_bulk.html']

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
@login_required
def bank_question_preview_view(request, pk):
    """ Отображает содержимое вопроса и его ответов в модальном окне """
    # Получаем вопрос с предзагрузкой связанных объектов
    question = get_object_or_404(
        BankQuestion.objects.select_related(
            'topic', 'subject', 'school_class', 'author'
        ).prefetch_related('options'), # Загружаем варианты ответов
        pk=pk
    )

    # Проверка прав доступа (можно добавить более строгую проверку, если нужно)
    user = request.user
    if not user.is_superuser:
        accessible_subjects = get_accessible_subjects(user)
        if question.subject not in accessible_subjects:
             # Можно вернуть ошибку 403 или просто пустой ответ
             return HttpResponse("Нет доступа", status=403)

    context = {
        'question': question,
        'options': question.options.all() # Передаем варианты в контекст
    }
    # Возвращаем только HTML-фрагмент для модального окна
    return render(request, 'bank_questions/preview_modal.html', context)

@login_required
@require_POST
def bank_question_quick_edit(request, pk):
    question = get_object_or_404(BankQuestion, pk=pk)
    
    # Проверка прав: разрешаем Админу ИЛИ Эксперту
    # (Раньше было "is_staff AND expert", что неправильно. Нужно OR)
    is_admin = request.user.is_staff or request.user.is_superuser
    is_expert = hasattr(request.user, 'profile') and request.user.profile.role == 'EXPERT'
    
    if not (is_admin or is_expert):
        return HttpResponseForbidden()

    new_text = request.POST.get('text')
    if new_text:
        question.text = new_text.strip()
        question.save()
        return HttpResponse(status=200)
    
    return HttpResponseBadRequest()

@login_required
@require_POST
def bank_option_quick_edit(request, pk):
    option = get_object_or_404(BankAnswerOption, pk=pk)
    
    # Проверка прав: разрешаем Админу ИЛИ Эксперту
    is_admin = request.user.is_staff or request.user.is_superuser
    is_expert = hasattr(request.user, 'profile') and request.user.profile.role == 'EXPERT'
    
    if not (is_admin or is_expert):
        return HttpResponseForbidden()

    new_text = request.POST.get('text')
    if new_text:
        option.text = new_text.strip()
        option.save()
        return HttpResponse(status=200)
    
    return HttpResponseBadRequest()

@login_required
@require_POST
def update_question_image(request, pk):
    """Сохраняет обрезанное/измененное изображение вопроса"""
    question = get_object_or_404(BankQuestion, pk=pk)
    
    # Проверка прав (только эксперты и админы)
    is_expert = hasattr(request.user, 'profile') and request.user.profile.role == 'EXPERT'
    if not (request.user.is_staff or request.user.is_superuser or is_expert):
        return JsonResponse({'status': 'error', 'message': 'Нет доступа'}, status=403)

    if 'image' in request.FILES:
        image_file = request.FILES['image']
        # Сохраняем новое изображение (оно заменит старое)
        question.question_image.save(image_file.name, image_file, save=True)
        return JsonResponse({'status': 'success', 'url': question.question_image.url})
    
    return JsonResponse({'status': 'error', 'message': 'Файл не найден'}, status=400)

@login_required
@require_POST
def save_question_option_order(request, pk):
    """Сохраняет новый порядок вариантов ответа для вопроса."""
    
    logger = logging.getLogger(__name__)
    logger.info(f"Сохранение порядка вариантов для вопроса {pk}")
    
    try:
        data = json.loads(request.body)
        option_ids = data.get('order')
        
        logger.info(f"Получены ID вариантов: {option_ids}")

        if not isinstance(option_ids, list):
            logger.error("Неверный формат данных: order не является списком")
            return JsonResponse({'status': 'error', 'message': 'Неверный формат данных'}, status=400)
        
        # Обновляем поле 'order'
        for index, option_id in enumerate(option_ids):
            updated = BankAnswerOption.objects.filter(
                id=option_id,
                question_id=pk
            ).update(order=index)
            logger.info(f"Вариант {option_id} -> порядок {index}, обновлено: {updated}")
        
        logger.info(f"Порядок вариантов для вопроса {pk} успешно сохранен")
        return JsonResponse({'status': 'success', 'message': 'Порядок вариантов сохранен'})
    
    except Exception as e:
        logger.error(f"Ошибка при сохранении порядка вариантов: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@login_required
@require_POST
def bank_option_quick_edit(request, pk):
    """Быстрое редактирование текста варианта ответа из буклета (HTMX)"""
    option = get_object_or_404(BankAnswerOption, pk=pk)
    
    # Проверка прав (только эксперты/админы)
    if not request.user.is_staff and not request.user.profile.role == 'EXPERT':
        return HttpResponseForbidden()

    new_text = request.POST.get('text')
    if new_text:
        option.text = new_text.strip()
        option.save()
        return HttpResponse(status=200)
    
    return HttpResponseBadRequest()

@login_required
@require_POST
def save_question_image_width(request, pk):
    """Сохраняет ширину изображения (AJAX)"""
    question = get_object_or_404(BankQuestion, pk=pk)
    
    # Разрешаем только админам и экспертам
    if not (request.user.is_staff or (hasattr(request.user, 'profile') and request.user.profile.role == 'EXPERT')):
         return HttpResponseForbidden()

    new_width = request.POST.get('width')
    if new_width:
        question.image_width = new_width
        question.save()
        return HttpResponse(status=200)
    
    return HttpResponseBadRequest()

# 1. НОВЫЙ VIEW: БИБЛИОТЕКА ТЕМ (КАРТОЧКИ)
class QuestionLibraryView(HtmxListView):
    """Отображает ТЕМЫ в виде карточек (Плитка)"""
    model = QuestionTopic
    template_name = 'bank_questions/library.html'
    context_object_name = 'topics'
    
    # --- 👇 ДОБАВЬТЕ ЭТОТ МЕТОД 👇 ---
    def get_template_names(self):
        # Мы переопределяем этот метод, чтобы базовый класс не искал "None/list.html"
        return [self.template_name]
    # --- 👆 КОНЕЦ ДОБАВЛЕНИЯ 👆 ---
    
    def get_queryset(self):
        qs = QuestionTopic.objects.annotate(
            q_count=Count('questions')
        ).select_related('subject', 'school_class').order_by('subject__name', 'name')
        
        user = self.request.user
        if not user.is_superuser:
            qs = qs.filter(
                subject__in=get_accessible_subjects(user),
                school_class__school__in=get_accessible_schools(user)
            )
        
        if subject_id := self.request.GET.get('subject'):
            qs = qs.filter(subject_id=subject_id)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Библиотека вопросов'
        context['subjects'] = get_accessible_subjects(self.request.user)
        return context

# 2. НОВЫЙ VIEW: ИМПОРТ (MODAL)
class BankQuestionImportView(HtmxFormView):
    form_class = ImportQuestionForm
    template_name_prefix = 'bank_questions'
    
    def get_template_names(self):
        return ['bank_questions/import_modal.html']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        topic_id = self.request.GET.get('topic_id')
        if topic_id:
            topic = get_object_or_404(QuestionTopic, pk=topic_id)
            context['topic'] = topic
            context['title'] = f"Импорт в тему: {topic.name}"
        return context

    def form_valid(self, form):
        topic_id = self.request.GET.get('topic_id')
        topic = get_object_or_404(QuestionTopic, pk=topic_id)
        
        file = form.cleaned_data['file']
        file_type = form.cleaned_data['file_type']
        
        # Запускаем сервис импорта
        count, errors = process_import(file, file_type, topic, self.request.user)
        
        if count > 0:
            msg = f"Успешно загружено {count} вопросов!"
            msg_type = "success"
            if errors:
                msg += f" (но было {len(errors)} ошибок)"
                msg_type = "warning"
        else:
            msg = "Не удалось загрузить вопросы. Проверьте формат файла."
            if errors:
                msg += f" Ошибка: {errors[0]}"
            msg_type = "error"

        # Отправляем уведомление и закрываем окно
        trigger = {
            "close-modal": True,
            "show-message": {"text": msg, "type": msg_type},
            "force-refresh": True # Обновляем страницу, чтобы увидеть вопросы
        }
        return HttpResponse(status=204, headers={'HX-Trigger': json.dumps(trigger)})