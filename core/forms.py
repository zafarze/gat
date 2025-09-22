# D:\New_GAT\core\forms.py (ПОЛНЫЙ И ИСПРАВЛЕННЫЙ КОД)

from django import forms
from django.db.models import Count
from .models import AcademicYear, GatTest, Quarter, School, SchoolClass, Subject, ClassSubject
from .models import School, Subject
# Общий CSS класс для полей ввода
input_class = 'mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500'

from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from .models import UserProfile


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            # Добавляем format='%Y-%m-%d'
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
            'year': forms.Select(attrs={'class': input_class}),
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
        # Используем только поле 'name'
        fields = ['school', 'name']
        widgets = {
            'school': forms.Select(attrs={'class': input_class}),
            'name': forms.TextInput(attrs={'class': input_class}),
        }
        labels = {
            'school': 'Школа',
            'name': 'Название класса (например, 5А)',
        }

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        # --- ИЗМЕНЕНИЕ ---
        fields = ['school', 'name', 'abbreviation', 'gat_info'] # Добавляем поле gat_info
        widgets = {
            'school': forms.Select(attrs={'class': input_class}),
            'name': forms.TextInput(attrs={'class': input_class}),
            'abbreviation': forms.TextInput(attrs={'class': input_class}),
            # --- ДОБАВЬТЕ ЭТО ---
            'gat_info': forms.TextInput(attrs={'class': input_class}),
        }
        labels = {
            'school': 'Школа',
            'name': 'Название предмета',
            'abbreviation': 'Сокращение (для Excel)',
            # --- ДОБАВЬТЕ ЭТО ---
            'gat_info': 'GAT (Информационно)',
        }

class GatTestForm(forms.ModelForm):
    class Meta:
        model = GatTest
        fields = ['name', 'test_number', 'school_class', 'quarter', 'test_date', 'subjects']
        widgets = {
            'name': forms.TextInput(attrs={'class': input_class}),
            'test_number': forms.NumberInput(attrs={'class': input_class}),
            'school_class': forms.Select(attrs={'class': input_class}),
            'quarter': forms.Select(attrs={'class': input_class}),
            'test_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': input_class, 'type': 'date'}),
            'subjects': forms.CheckboxSelectMultiple(),
        }

class ClassSubjectForm(forms.ModelForm):
    class Meta:
        model = ClassSubject
        fields = ['school_class', 'subject', 'number_of_questions']
        widgets = {
            'school_class': forms.Select(attrs={'class': input_class}),
            'subject': forms.Select(attrs={'class': input_class}),
            'number_of_questions': forms.NumberInput(attrs={'class': input_class}),
        }
        labels = { 'school_class': 'Класс', 'subject': 'Предмет', 'number_of_questions': 'Количество вопросов' }

class UploadFileForm(forms.Form):
    gat_test = forms.ModelChoiceField(queryset=GatTest.objects.all().order_by('-test_date'), label="Выберите GAT-тест для загрузки результатов")
    file = forms.FileField(label="Выберите Excel-файл (.xlsx)")

    def __init__(self, *args, **kwargs):
        super(UploadFileForm, self).__init__(*args, **kwargs)
        self.fields['gat_test'].widget.attrs.update({'class': input_class})
        self.fields['file'].widget.attrs.update({'class': 'mt-1 block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 focus:outline-none'})
        
class GatTestCompareForm(forms.Form):
    test1 = forms.ModelChoiceField(
        queryset=GatTest.objects.all().order_by('-test_date'),
        label="Выберите первый тест для сравнения",
        widget=forms.Select(attrs={'class': input_class})
    )
    test2 = forms.ModelChoiceField(
        queryset=GatTest.objects.all().order_by('-test_date'),
        label="Выберите второй тест для сравнения",
        widget=forms.Select(attrs={'class': input_class})
    )

    # Проверка, что не выбраны одинаковые тесты
    def clean(self):
        cleaned_data = super().clean()
        test1 = cleaned_data.get("test1")
        test2 = cleaned_data.get("test2")

        if test1 and test2 and test1 == test2:
            raise forms.ValidationError("Нельзя сравнивать тест с самим собой. Выберите два разных теста.")

        return cleaned_data

class DeepAnalysisForm(forms.Form):
    # --- НОВОЕ ПОЛЕ ---
    quarter = forms.ModelChoiceField(
        queryset=Quarter.objects.annotate(test_count=Count('gattests')).filter(test_count__gt=0).order_by('-year__start_date', '-start_date'),
        widget=forms.Select(attrs={'class': input_class}),
        label="Выберите четверть",
        required=True
    )
    schools = forms.ModelMultipleChoiceField(
        queryset=School.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': input_class, 'size': '6'}),
        label="Выберите школы для сравнения",
        required=True
    )
    # --- НОВОЕ ПОЛЕ ---
    school_classes = forms.ModelMultipleChoiceField(
        queryset=SchoolClass.objects.none(), # Изначально пустое, будет заполняться через JS
        widget=forms.SelectMultiple(attrs={'class': input_class, 'size': '6'}),
        label="Классы (необязательно)",
        required=False
    )
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.none(), # Изначально пустое, будет заполняться через JS
        widget=forms.SelectMultiple(attrs={'class': input_class, 'size': '6'}),
        label="Выберите предметы для сравнения",
        required=True
    )
    test_number = forms.ChoiceField(
        choices=[(1, 'GAT-1'), (2, 'GAT-2')],
        widget=forms.Select(attrs={'class': input_class}),
        label="Выберите тест",
        required=True
    )

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
        self.fields['old_password'].widget.attrs.update({'class': input_class, 'placeholder': 'Текущий пароль'})
        self.fields['new_password1'].widget.attrs.update({'class': input_class, 'placeholder': 'Новый пароль'})
        self.fields['new_password2'].widget.attrs.update({'class': input_class, 'placeholder': 'Подтвердите новый пароль'})

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