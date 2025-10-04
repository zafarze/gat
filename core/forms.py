# D:\New_GAT\core\forms.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)

from django import forms
from django.db.models import Count
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from crispy_forms.helper import FormHelper  # <-- ДОБАВЛЕНО
from crispy_forms.layout import Layout      # <-- ДОБАВЛЕНО
from accounts.models import UserProfile
from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject, 
    ClassSubject, GatTest, TeacherNote
)
from .views.permissions import get_accessible_schools
from .models import Student

# --- ОБЩИЕ СТИЛИ ДЛЯ ФОРМ ---
input_class = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
select_class = 'mt-1 block w-full pl-3 pr-10 py-2 text-base border-gray-300 focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm rounded-md'
select_multiple_class = f'{select_class} h-32' # Стиль для полей с множественным выбором

# --- ФОРМЫ ДЛЯ CRUD-ОПЕРАЦИЙ ---

class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
        }
        labels = { 'name': 'Название года', 'start_date': 'Дата начала', 'end_date': 'Дата окончания' }

class QuarterForm(forms.ModelForm):
    class Meta:
        model = Quarter
        fields = ['name', 'year', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            'year': forms.Select(attrs={'class': select_class}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
            'end_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
        }
        labels = { 'name': 'Название четверти', 'year': 'Учебный год', 'start_date': 'Дата начала', 'end_date': 'Дата окончания' }

class SchoolForm(forms.ModelForm):
    class Meta:
        model = School
        fields = ['name', 'address']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            'address': forms.TextInput(attrs={'class': input_class}),
        }
        labels = { 'name': 'Название школы', 'address': 'Адрес' }

class SchoolClassForm(forms.ModelForm):
    class Meta:
        model = SchoolClass
        fields = ['school', 'name', 'parent']
        widgets = {
            'school': forms.Select(attrs={'class': select_class}),
            'name': forms.TextInput(attrs={'class': input_class, 'placeholder': 'Например: 5А, 10Б'}),
            'parent': forms.Select(attrs={'class': select_class}),
        }
        labels = { 'school': 'Школа', 'name': 'Название класса', 'parent': 'Параллель (необязательно)' }

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['school', 'name', 'abbreviation', 'gat_info']
        widgets = {
            'school': forms.Select(attrs={'class': select_class}),
            'name': forms.TextInput(attrs={'class': input_class}),
            'abbreviation': forms.TextInput(attrs={'class': input_class, 'placeholder': 'Например: Мат, Рус'}),
            'gat_info': forms.TextInput(attrs={'class': input_class, 'placeholder': 'Например: GAT-1'}),
        }
        labels = { 'school': 'Школа', 'name': 'Название предмета', 'abbreviation': 'Сокращение (для Excel)', 'gat_info': 'GAT (Информационно)'}

class GatTestForm(forms.ModelForm):
    class Meta:
        model = GatTest
        fields = ['name', 'test_number', 'school_class', 'quarter', 'test_date', 'subjects']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            'test_number': forms.NumberInput(attrs={'class': input_class}),
            'school_class': forms.Select(attrs={'class': select_class}),
            'quarter': forms.Select(attrs={'class': select_class}),
            'test_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
            'subjects': forms.CheckboxSelectMultiple(),
        }

class ClassSubjectForm(forms.ModelForm):
    class Meta:
        model = ClassSubject
        fields = ['school_class', 'subject', 'number_of_questions']
        widgets = {
            'school_class': forms.Select(attrs={'class': select_class}),
            'subject': forms.Select(attrs={'class': select_class}),
            'number_of_questions': forms.NumberInput(attrs={'class': input_class}),
        }
        labels = { 'school_class': 'Класс', 'subject': 'Предмет', 'number_of_questions': 'Количество вопросов' }

# --- СПЕЦИАЛИЗИРОВАННЫЕ ФОРМЫ ---

class UploadFileForm(forms.Form):
    gat_test = forms.ModelChoiceField(queryset=GatTest.objects.all().order_by('-test_date'), label="Выберите GAT-тест для загрузки")
    file = forms.FileField(label="Выберите Excel-файл (.xlsx)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gat_test'].widget.attrs.update({'class': select_class})
        self.fields['file'].widget.attrs.update({'class': 'mt-1 block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'})

class DeepAnalysisForm(forms.Form):
    quarters = forms.ModelMultipleChoiceField(queryset=Quarter.objects.none(), widget=forms.CheckboxSelectMultiple, label="Четверти", required=True)
    schools = forms.ModelMultipleChoiceField(queryset=School.objects.none(), widget=forms.CheckboxSelectMultiple, label="Школы", required=True)
    school_classes = forms.ModelMultipleChoiceField(queryset=SchoolClass.objects.none(), widget=forms.CheckboxSelectMultiple, label="Классы (необязательно)", required=False)
    subjects = forms.ModelMultipleChoiceField(queryset=Subject.objects.none(), widget=forms.CheckboxSelectMultiple, label="Предметы", required=True)
    test_numbers = forms.MultipleChoiceField(choices=[('1', 'GAT-1'), ('2', 'GAT-2')], widget=forms.CheckboxSelectMultiple, label="Тесты", required=True)

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user:
            # Используем "умную" функцию для получения списка доступных школ
            accessible_schools_qs = get_accessible_schools(user)
            self.fields['schools'].queryset = accessible_schools_qs
            
            # Фильтруем и четверти, чтобы показывать только те, где были тесты в доступных школах
            self.fields['quarters'].queryset = Quarter.objects.filter(gattests__school_class__school__in=accessible_schools_qs).distinct().order_by('-year__start_date', '-start_date')

        # Эта логика сработает, когда форма будет инициализирована с GET-параметрами
        if self.data:
            try:
                year_id = int(self.data.get('academic_year'))
                if year_id:
                    self.fields['quarter'].queryset = Quarter.objects.filter(year_id=year_id).order_by('start_date')
            except (ValueError, TypeError):
                pass

            try:
                school_ids = self.data.getlist('schools')
                if school_ids:
                    self.fields['school_classes'].queryset = SchoolClass.objects.filter(school_id__in=school_ids).order_by('name')
                    self.fields['subjects'].queryset = Subject.objects.filter(school_id__in=school_ids).order_by('name')
            except (ValueError, TypeError):
                pass


class MonitoringFilterForm(forms.Form):
    academic_year = forms.ModelChoiceField(
        queryset=AcademicYear.objects.order_by('-start_date'), 
        required=False, 
        label="Учебный год", 
        empty_label="Выберите год..."
    )
    quarter = forms.ModelChoiceField(
        queryset=Quarter.objects.none(), 
        required=False, 
        label="Четверть"
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.none(), # Заполняется динамически
        required=False, 
        label="Школы", 
        widget=forms.SelectMultiple
    )
    school_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(), # Заполняется динамически
        required=False, 
        label="Классы", 
        widget=forms.SelectMultiple
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(), # Заполняется динамически
        required=False, 
        label="Предметы", 
        widget=forms.SelectMultiple
    )
    gat_tests = forms.MultipleChoiceField(
        choices=[(1, 'GAT-1'), (2, 'GAT-2')], 
        required=False, 
        label="Тесты", 
        widget=forms.CheckboxSelectMultiple
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Применяем фильтрацию по правам доступа
        if user:
            accessible_schools_qs = get_accessible_schools(user)
            self.fields['schools'].queryset = accessible_schools_qs

            # Фильтруем и годы, чтобы не показывать пустые
            year_ids_with_results = GatTest.objects.filter(
                school_class__school__in=accessible_schools_qs
            ).values_list('quarter__year_id', flat=True).distinct()
            self.fields['academic_year'].queryset = AcademicYear.objects.filter(id__in=year_ids_with_results).order_by('-start_date')


        # Динамическая подгрузка для связанных полей (если данные уже отправлены)
        if 'academic_year' in self.data:
            try:
                year_id = int(self.data.get('academic_year'))
                self.fields['quarter'].queryset = Quarter.objects.filter(year_id=year_id).order_by('start_date')
            except (ValueError, TypeError):
                pass

        if 'schools' in self.data:
            try:
                school_ids = self.data.getlist('schools')
                self.fields['school_classes'].queryset = SchoolClass.objects.filter(school_id__in=school_ids).order_by('name')
                self.fields['subjects'].queryset = Subject.objects.filter(school_id__in=school_ids).order_by('name')
            except (ValueError, TypeError):
                pass
# --- ФОРМЫ ПРОФИЛЯ И ПОЛЬЗОВАТЕЛЕЙ ---

class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=False, label="Имя", widget=forms.TextInput(attrs={'class': input_class}))
    last_name = forms.CharField(max_length=100, required=False, label="Фамилия", widget=forms.TextInput(attrs={'class': input_class}))
    
    class Meta:
        model = UserProfile
        fields = ['photo']
        labels = {'photo': 'Фотография профиля'}

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': input_class})
        self.fields['new_password1'].widget.attrs.update({'class': input_class})
        self.fields['new_password2'].widget.attrs.update({'class': input_class})

class EmailChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['email']
        widgets = {'email': forms.EmailInput(attrs={'class': input_class})}
        labels = {'email': 'Новый Email'}

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Этот email уже используется.")
        return email

class TeacherNoteForm(forms.ModelForm):
    class Meta:
        model = TeacherNote
        fields = ['note']
        widgets = { 'note': forms.Textarea(attrs={'class': input_class, 'rows': 4}) }
        labels = { 'note': 'Ваша заметка о студенте' }
        
class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'student_id', 'school_class', 
            'first_name_ru', 'last_name_ru',
            'first_name_tj', 'last_name_tj',
            'first_name_en', 'last_name_en',
        ]
        widgets = {
            'student_id': forms.TextInput(attrs={'class': input_class}),
            'school_class': forms.Select(attrs={'class': select_class}),
            'first_name_ru': forms.TextInput(attrs={'class': input_class}),
            'last_name_ru': forms.TextInput(attrs={'class': input_class}),
            'first_name_tj': forms.TextInput(attrs={'class': input_class}),
            'last_name_tj': forms.TextInput(attrs={'class': input_class}),
            'first_name_en': forms.TextInput(attrs={'class': input_class}),
            'last_name_en': forms.TextInput(attrs={'class': input_class}),
        }

class StudentUploadForm(forms.Form):
    file = forms.FileField(label="Выберите Excel-файл (.xlsx)")


class StatisticsFilterForm(forms.Form):
    quarters = forms.ModelMultipleChoiceField(
        queryset=Quarter.objects.annotate(test_count=Count('gattests')).filter(test_count__gt=0).order_by('-year__start_date', '-start_date'),
        widget=forms.CheckboxSelectMultiple,
        label="Четверти",
        required=False
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.none(),  # Изначально queryset пустой, мы его заполним ниже
        widget=forms.CheckboxSelectMultiple,
        label="Школы",
        required=False
    )
    school_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        label="Классы",
        required=False # <-- ИЗМЕНЕНО: Сделал необязательным для удобства
    )
    test_numbers = forms.MultipleChoiceField(
        choices=[('1', 'GAT-1'), ('2', 'GOT-2')],
        widget=forms.CheckboxSelectMultiple,
        label="Тесты",
        required=False
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Эта простая проверка сработает и для админа, и для директора
        if user:
            # ---> ВОТ ИСПРАВЛЕНИЕ <---
            # Просто используем нашу функцию, чтобы получить правильный список школ
            self.fields['schools'].queryset = get_accessible_schools(user)