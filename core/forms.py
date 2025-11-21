# D:\New_GAT\core\forms.py (ОБНОВЛЕННАЯ ВЕРСИЯ ДЛЯ ЦЕНТРА ВОПРОСОВ)

from django import forms
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from django.urls import reverse
from accounts.models import UserProfile
from core.models import Subject

from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    GatTest, TeacherNote, Student, QuestionCount,
    QuestionTopic, BankQuestion, BankAnswerOption
)
from .models import StudentResult, GatTest
from .views.permissions import get_accessible_schools, get_accessible_subjects

# --- ОБЩИЕ СТИЛИ ДЛЯ ФОРМ ---
input_class = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
select_class = 'mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md'
select_multiple_class = f'{select_class} h-32'
checkbox_class = 'h-4 w-4 text-indigo-600 focus:ring-indigo-500 border-gray-300 rounded'

class BaseForm(forms.ModelForm):
    """
    Базовая форма с автоматическим применением CSS классов
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if hasattr(field, 'widget') and hasattr(field.widget, 'attrs'):
                if isinstance(field.widget, (forms.TextInput, forms.Textarea, forms.DateInput, forms.EmailInput, forms.NumberInput)):
                    field.widget.attrs.update({'class': input_class})
                elif isinstance(field.widget, forms.Select) and not field.widget.allow_multiple_selected:
                    field.widget.attrs.update({'class': select_class})
                elif isinstance(field.widget, forms.SelectMultiple):
                     # Для SelectMultiple используем стандартный класс, так как стили могут быть кастомными
                    pass
                elif isinstance(field.widget, forms.CheckboxInput):
                    field.widget.attrs.update({'class': checkbox_class})
                elif isinstance(field.widget, forms.CheckboxSelectMultiple):
                    # Для CheckboxSelectMultiple стилизация происходит в шаблоне
                    pass

class BaseStyledForm(forms.Form):
    """
    Базовая форма с автоматическим применением CSS классов,
    но для обычных форм (не ModelForm).
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.TextInput, forms.Textarea, forms.DateInput, forms.EmailInput, forms.NumberInput)):
                widget.attrs.update({'class': input_class})
            elif isinstance(widget, forms.Select):
                widget.attrs.update({'class': select_class})

# ==========================================================
# --- ФОРМЫ ДЛЯ РАЗДЕЛОВ УПРАВЛЕНИЯ (CRUD) ---
# ==========================================================

class AcademicYearForm(BaseForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }
        labels = {
            'name': 'Название учебного года',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания'
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and start_date >= end_date:
            raise forms.ValidationError("Дата начала должна быть раньше даты окончания")
        return cleaned_data


class QuarterForm(BaseForm):
    class Meta:
        model = Quarter
        fields = ['name', 'year', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'
            ),
            'end_date': forms.DateInput(
                attrs={'type': 'date'},
                format='%Y-%m-%d'
            ),
        }
        labels = {
            'name': 'Название четверти',
            'year': 'Учебный год',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания'
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        year = cleaned_data.get('year')
        if start_date and end_date:
            if start_date >= end_date:
                raise forms.ValidationError("Дата начала четверти должна быть раньше даты окончания")
            if year:
                if not (year.start_date <= start_date and end_date <= year.end_date):
                    raise forms.ValidationError(
                        f"Даты четверти должны находиться в пределах учебного года ({year.start_date} - {year.end_date})"
                    )
        return cleaned_data


class SchoolForm(BaseForm):
    class Meta:
        model = School
        fields = ['school_id', 'name', 'city', 'address']
        labels = {
            'school_id': 'ID Школы',
            'name': 'Название школы',
            'city': 'Город',
            'address': 'Адрес'
        }


class SchoolClassForm(BaseForm):
    class Meta:
        model = SchoolClass
        fields = ['school', 'name', 'parent', 'homeroom_teacher']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'Например: 5А или 10'}),
        }
        labels = {
            'school': 'Школа',
            'name': 'Название класса/параллели',
            'parent': 'Является подклассом для (параллель)',
            'homeroom_teacher': 'Классный руководитель'
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        instance = kwargs.get('instance')
        if not school and instance:
            school = instance.school

        super().__init__(*args, **kwargs)
        
        parents_qs = SchoolClass.objects.filter(parent__isnull=True)
        
        if school:
            parents_qs = parents_qs.filter(school=school)
            
            self.fields['homeroom_teacher'].queryset = User.objects.filter(
                profile__school=school
            ).order_by('last_name', 'first_name')
        else:
            self.fields['homeroom_teacher'].queryset = User.objects.none()

        self.fields['parent'].queryset = parents_qs.order_by('name')
        self.fields['parent'].empty_label = "Нет (это параллель)"
        self.fields['homeroom_teacher'].empty_label = "Не назначен"


class SubjectForm(BaseForm):
    class Meta:
        model = Subject
        fields = ['name', 'abbreviation']
        labels = {
            'name': 'Название предмета',
            'abbreviation': 'Сокращение'
        }


# =============================================================================
# --- НОВЫЕ ФОРМЫ ДЛЯ ЦЕНТРА ВОПРОСОВ ---
# =============================================================================

class QuestionTopicForm(BaseForm):
    class Meta:
        model = QuestionTopic
        fields = ['name', 'subject', 'school_class']
        labels = {
            'name': 'Название темы',
            'subject': 'Предмет',
            'school_class': 'Класс (Параллель)'
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and not self.request.user.is_superuser:
            # Фильтруем предметы по доступным для пользователя
            accessible_subjects = get_accessible_subjects(self.request.user)
            self.fields['subject'].queryset = accessible_subjects.order_by('name')
            
            # Фильтруем классы по доступным школам
            accessible_schools = get_accessible_schools(self.request.user)
            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                school__in=accessible_schools,
                parent__isnull=True
            ).order_by('school__name', 'name')
        else:
            self.fields['subject'].queryset = Subject.objects.all().order_by('name')
            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                parent__isnull=True
            ).order_by('school__name', 'name')


class BankQuestionForm(BaseForm):
    class Meta:
        model = BankQuestion
        fields = [
            'topic',
            'text',
            'question_image',
            'difficulty',
            #'tags'
        ]
        widgets = {
            'text': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите текст вопроса...'}),
            'tags': forms.TextInput(attrs={'placeholder': 'через запятую, например: алгебра, уравнения, 10 класс'}),
            'question_image': forms.ClearableFileInput(attrs={'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'}),
        }
        labels = {
            'topic': 'Тема',
            'text': 'Текст вопроса',
            'question_image': 'Изображение к вопросу',
            'difficulty': 'Сложность',
            'tags': 'Теги для поиска'
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        if self.request and not self.request.user.is_superuser:
            # Фильтруем темы по доступным предметам и классам
            accessible_subjects = get_accessible_subjects(self.request.user)
            accessible_schools = get_accessible_schools(self.request.user)

            self.fields['topic'].queryset = QuestionTopic.objects.filter(
                subject__in=accessible_subjects,
                school_class__school__in=accessible_schools
            ).order_by('subject__name', 'school_class__name', 'name')
        else:
            self.fields['topic'].queryset = QuestionTopic.objects.all().order_by(
                'subject__name', 'school_class__name', 'name'
            )

    # --- ✨ ГЛАВНОЕ ИСПРАВЛЕНИЕ ЗДЕСЬ ✨ ---
    def clean(self):
        """
        Автоматически устанавливаем Предмет и Класс на основе выбранной Темы,
        чтобы пройти валидацию модели.
        """
        cleaned_data = super().clean()
        topic = cleaned_data.get('topic')

        if topic:
            # Принудительно берем предмет и класс из выбранной темы
            # Это предотвращает ошибку "Предмет вопроса должен совпадать..."
            self.instance.subject = topic.subject
            self.instance.school_class = topic.school_class
            
            # Также обновляем cleaned_data на случай, если они нужны где-то еще
            cleaned_data['subject'] = topic.subject
            cleaned_data['school_class'] = topic.school_class

        return cleaned_data


class BankAnswerOptionForm(BaseForm):
    class Meta:
        model = BankAnswerOption
        # --- 👇 ДОБАВЬ 'option_image' В СПИСОК 👇 ---
        fields = ['text', 'option_image', 'is_correct']
        # --- КОНЕЦ ДОБАВЛЕНИЯ ---
        widgets = {
            'text': forms.TextInput(attrs={'placeholder': 'Введите вариант ответа...'}),
             # --- 👇 ДОБАВЬ ВИДЖЕТ ДЛЯ ИЗОБРАЖЕНИЯ 👇 ---
            'option_image': forms.ClearableFileInput(attrs={'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'}),
            # --- КОНЕЦ ДОБАВЛЕНИЯ ---
        }
        labels = {
            'text': 'Текст ответа',
            # --- 👇 ДОБАВЬ LABEL 👇 ---
            'option_image': 'Изображение',
            # --- КОНЕЦ ДОБАВЛЕНИЯ ---
            'is_correct': 'Правильный ответ'
        }


class GatTestForm(BaseForm):
    class Meta:
        model = GatTest
        fields = ['name', 'test_number', 'day', 'quarter', 'test_date', 'school', 'school_class', 'shuffle_questions', 'shuffle_options']
        widgets = {
            'test_date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }
        labels = {
            'name': 'Название теста',
            'test_number': 'Номер GAT',
            'day': 'День GAT',
            'quarter': 'Четверть',
            'test_date': 'Дата проведения',
            'school': 'Школа',
            'school_class': 'Класс (Параллель)',
            'shuffle_questions': 'Перемешивать вопросы',
            'shuffle_options': 'Перемешивать варианты ответов'
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        school = kwargs.pop('school', None)
        
        super().__init__(*args, **kwargs)
        
        self.fields['school'].required = True
        self.fields['school_class'].required = True

        if self.request and not self.request.user.is_superuser:
            accessible_schools = get_accessible_schools(self.request.user)
            self.fields['school'].queryset = accessible_schools.order_by('name')
        else:
            self.fields['school'].queryset = School.objects.all().order_by('name')

        final_school = school
        if not final_school:
            if self.data:
                try:
                    school_id = int(self.data.get('school'))
                    final_school = School.objects.get(pk=school_id)
                except (ValueError, TypeError, School.DoesNotExist):
                    pass
            elif self.instance and self.instance.pk:
                final_school = self.instance.school

        if final_school:
            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                school=final_school, parent__isnull=True
            ).order_by('name')
            self.initial['school'] = final_school
        else:
            self.fields['school_class'].queryset = SchoolClass.objects.none()


class QuestionCountForm(BaseForm):
    school = forms.ModelChoiceField(
        queryset=School.objects.all().order_by('name'),
        label="Школа",
        required=False
    )

    class Meta:
        model = QuestionCount
        fields = ['school_class', 'subject', 'number_of_questions']
        labels = {
            'school_class': 'Класс (Параллель)',
            'subject': 'Предмет',
            'number_of_questions': 'Количество вопросов'
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        final_school = school
        if not final_school:
            if self.data:
                try:
                    school_id = int(self.data.get('school'))
                    final_school = School.objects.get(pk=school_id)
                except (ValueError, TypeError, School.DoesNotExist):
                    pass
            elif self.instance and self.instance.pk:
                final_school = self.instance.school_class.school

        if final_school:
            self.fields['school_class'].queryset = SchoolClass.objects.filter(
                school=final_school, parent__isnull=True
            ).order_by('name')
            self.fields['subject'].queryset = Subject.objects.all().order_by('name')
            self.initial['school'] = final_school
        else:
            self.fields['school_class'].queryset = SchoolClass.objects.none()
            self.fields['subject'].queryset = Subject.objects.all().order_by('name')


class StudentForm(BaseForm):
    class Meta:
        model = Student
        fields = ['student_id', 'school_class', 'status', 'first_name_ru', 'last_name_ru', 'first_name_tj', 'last_name_tj', 'first_name_en', 'last_name_en']
        labels = {
            'student_id': 'ID студента',
            'school_class': 'Класс',
            'status': 'Статус',
            'first_name_ru': 'Имя (рус)',
            'last_name_ru': 'Фамилия (рус)',
            'first_name_tj': 'Имя (тадж)',
            'last_name_tj': 'Фамилия (тадж)',
            'first_name_en': 'Имя (англ)',
            'last_name_en': 'Фамилия (англ)'
        }

# ==========================================================
# --- СПЕЦИАЛИЗИРОВАННЫЕ ФОРМЫ ---
# ==========================================================

class QuestionCountBulkSchoolForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.all(),
        label="Учебный год",
        empty_label="Выберите год...",
        required=True
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Школы",
        required=True
    )
    school_class = forms.ModelChoiceField(
        queryset=SchoolClass.objects.none(),
        label="Класс",
        empty_label="Выберите класс...",
        required=True
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        label="Предмет",
        empty_label="Выберите предмет...",
        required=True
    )
    number_of_questions = forms.IntegerField(
        label="Количество вопросов",
        min_value=0,
        required=True
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        accessible_schools = get_accessible_schools(user)

        if 'academic_year' in self.data:
            try:
                year_id = int(self.data.get('academic_year'))
                self.fields['schools'].queryset = accessible_schools.filter(
                    gat_tests__quarter__year_id=year_id
                ).distinct()
            except (ValueError, TypeError):
                pass
        
        if 'schools' in self.data:
            school_ids = self.data.getlist('schools')
            
            if school_ids:
                common_classes_qs = SchoolClass.objects.filter(
                    school_id__in=school_ids, parent__isnull=True
                ).values('name').annotate(
                    school_count=models.Count('school_id', distinct=True)
                ).filter(school_count=len(school_ids))
                
                common_class_names = [item['name'] for item in common_classes_qs]
                
                self.fields['school_class'].queryset = SchoolClass.objects.filter(
                    school_id=school_ids[0], name__in=common_class_names, parent__isnull=True
                ).order_by('name')

                self.fields['subject'].queryset = Subject.objects.all().order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        schools = cleaned_data.get('schools')
        school_class = cleaned_data.get('school_class')
        subject = cleaned_data.get('subject')

        if not schools or not school_class or not subject:
            return cleaned_data

        for school in schools:
            if not SchoolClass.objects.filter(school=school, name=school_class.name, parent__isnull=True).exists():
                self.add_error('school_class', f'Класс-параллель "{school_class.name}" не найден в школе "{school.name}".')
                
        return cleaned_data


class UploadFileForm(forms.Form):
    gat_test = forms.ModelChoiceField(queryset=GatTest.objects.all().order_by('-test_date'), label="Выберите GAT-тест")
    file = forms.FileField(label="Выберите Excel-файл (.xlsx)", widget=forms.FileInput(attrs={'accept': '.xlsx'}))
    
    def __init__(self, *args, **kwargs):
        test_date = kwargs.pop('test_date', None)
        super().__init__(*args, **kwargs)

        if test_date:
            self.fields['gat_test'].queryset = GatTest.objects.filter(
                test_date=test_date
            ).order_by('name')
        
        self.fields['gat_test'].widget.attrs.update({'class': select_class})
        self.fields['file'].widget.attrs.update({'class': 'mt-1 block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'})


class StudentUploadForm(forms.Form):
    file = forms.FileField(label="Выберите Excel-файл (.xlsx)", widget=forms.FileInput(attrs={'accept': '.xlsx'}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['file'].widget.attrs.update({'class': 'mt-1 block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'})


class TeacherNoteForm(BaseForm):
    class Meta:
        model = TeacherNote
        fields = ['note']
        widgets = {'note': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Введите вашу заметку...'})}
        labels = {'note': 'Ваша заметка о студенте'}

# ==========================================================
# --- ФОРМЫ ФИЛЬТРОВ ---
# ==========================================================

class BaseFilterForm(forms.Form):
    """
    Улучшенная базовая форма для фильтров.
    Теперь она сама применяет права доступа при инициализации.
    """
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.apply_user_permissions()

    def apply_user_permissions(self):
        """
        Фильтрует queryset'ы полей 'schools' и 'subjects' на основе прав пользователя.
        """
        if not self.user:
            return

        accessible_schools = get_accessible_schools(self.user)
        accessible_subjects = get_accessible_subjects(self.user)
        
        if 'schools' in self.fields:
            self.fields['schools'].queryset = accessible_schools.order_by('name')
        
        if 'subjects' in self.fields:
            self.fields['subjects'].queryset = accessible_subjects.order_by('name')


class DeepAnalysisForm(BaseFilterForm):
    quarters = forms.ModelMultipleChoiceField(
        queryset=Quarter.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Четверти",
        required=True
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Школы",
        required=True
    )
    school_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Классы",
        required=True
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Предметы",
        required=True
    )
    test_numbers = forms.MultipleChoiceField(
        choices=[(1, 'GAT-1'), (2, 'GAT-2'), (3, 'GAT-3'), (4, 'GAT-4')],
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Тесты",
        required=True
    )
    days = forms.MultipleChoiceField(
        choices=[(1, 'День 1'), (2, 'День 2')],
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Дни",
        required=False
    )

    def apply_user_permissions(self):
        super().apply_user_permissions()
        
        accessible_schools = self.fields['schools'].queryset
        quarter_ids = GatTest.objects.filter(school__in=accessible_schools).values_list('quarter_id', flat=True).distinct()
        self.fields['quarters'].queryset = Quarter.objects.filter(id__in=quarter_ids).order_by('-year__start_date', '-start_date')

        if self.data and 'schools' in self.data:
            try:
                school_ids = [int(x) for x in self.data.getlist('schools')]
                self.fields['school_classes'].queryset = SchoolClass.objects.filter(
                    school_id__in=school_ids,
                    school__in=accessible_schools
                ).select_related('school').order_by('name')
            except (ValueError, TypeError):
                pass


class MonitoringFilterForm(BaseFilterForm):
    quarters = forms.ModelMultipleChoiceField(
        queryset=Quarter.objects.none(), required=False, label="Четверть",
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class})
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.none(), required=False, label="Школы",
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class})
    )
    school_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(), required=False, label="Классы",
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class})
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(), required=False, label="Предметы",
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class})
    )
    test_numbers = forms.MultipleChoiceField(
        choices=[(1, 'GAT-1'), (2, 'GAT-2'), (3, 'GAT-3'), (4, 'GAT-4')],
        required=False, label="Тесты", widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class})
    )
    days = forms.MultipleChoiceField(
        choices=[(1, 'День 1'), (2, 'День 2')], 
        widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
        label="Дни", required=False
    )

    def apply_user_permissions(self):
        super().apply_user_permissions()
        
        accessible_schools = self.fields['schools'].queryset
        
        quarter_ids = GatTest.objects.filter(school__in=accessible_schools).values_list('quarter_id', flat=True).distinct()
        self.fields['quarters'].queryset = Quarter.objects.filter(id__in=quarter_ids).order_by('-year__start_date', '-start_date')
        
        if self.data and self.data.getlist('schools'):
            try:
                school_ids = [int(x) for x in self.data.getlist('schools')]
                self.fields['school_classes'].queryset = SchoolClass.objects.filter(
                    school_id__in=school_ids,
                    school__in=accessible_schools
                ).select_related('school').order_by('name')
            except (ValueError, TypeError): pass


class StatisticsFilterForm(BaseFilterForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = AcademicYear.objects.filter(start_date__lte=timezone.now().date(), end_date__gte=timezone.now().date()).first()
        quarters_queryset = Quarter.objects.filter(year=current_year) if current_year else Quarter.objects.none()
        self.fields['quarters'] = forms.ModelMultipleChoiceField(
            queryset=quarters_queryset.order_by('start_date'),
            widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}), label="Четверти", required=True
        )
        schools_queryset = get_accessible_schools(self.user) if self.user else School.objects.none()
        self.fields['schools'] = forms.ModelMultipleChoiceField(
            queryset=schools_queryset, widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
            label="Школы", required=True
        )
        self.fields['school_classes'] = forms.ModelMultipleChoiceField(
            queryset=SchoolClass.objects.none(), widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
            label="Классы", required=False
        )
        self.fields['test_numbers'] = forms.MultipleChoiceField(
            choices=[(1, 'GAT-1'), (2, 'GAT-2'), (3, 'GAT-3'), (4, 'GAT-4')],
            widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}), label="Тесты", required=True
        )
        self.fields['days'] = forms.MultipleChoiceField(
            choices=[(1, 'День 1'), (2, 'День 2')], widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
            label="Дни", required=False
        )
        subjects_queryset = get_accessible_subjects(self.user) if self.user else Subject.objects.none()
        self.fields['subjects'] = forms.ModelMultipleChoiceField(
            queryset=subjects_queryset, widget=forms.CheckboxSelectMultiple(attrs={'class': checkbox_class}),
            label="Предметы", required=False
        )
        if self.data and self.data.getlist('schools'):
            try:
                school_ids = [int(x) for x in self.data.getlist('schools')]
                self.fields['school_classes'].queryset = SchoolClass.objects.filter(
                    school_id__in=school_ids,
                    school__in=schools_queryset
                ).select_related('school', 'parent').order_by('name')
            except (ValueError, TypeError): pass

# ==========================================================
# --- ФОРМЫ ПРОФИЛЯ И ПОЛЬЗОВАТЕЛЕЙ ---
# ==========================================================

class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False, label="Имя", widget=forms.TextInput(attrs={'class': input_class}))
    last_name = forms.CharField(max_length=100, required=False, label="Фамилия", widget=forms.TextInput(attrs={'class': input_class}))

    class Meta:
        model = UserProfile
        fields = ['photo']
        labels = {'photo': 'Фотография профиля'}
        widgets = {'photo': forms.FileInput(attrs={'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'})}


class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': input_class})


class EmailChangeForm(forms.ModelForm):
    email_confirmation = forms.EmailField(label="Подтверждение email", widget=forms.EmailInput(attrs={'class': input_class}))

    class Meta:
        model = User
        fields = ['email']
        widgets = {'email': forms.EmailInput(attrs={'class': input_class})}
        labels = {'email': 'Новый Email'}

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        email_confirmation = cleaned_data.get('email_confirmation')
        if email and email_confirmation and email != email_confirmation:
            raise forms.ValidationError("Email адреса не совпадают")
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Этот email уже используется.")
        return email
    
class ImportQuestionForm(forms.Form):
    file_type = forms.ChoiceField(
        choices=[('excel', 'Excel (.xlsx)'), ('word', 'Word (.docx)')],
        label="Тип файла",
        widget=forms.Select(attrs={'class': select_class})
    )
    file = forms.FileField(
        label="Выберите файл",
        widget=forms.FileInput(attrs={'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100'})
    )