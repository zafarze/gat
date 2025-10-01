# D:\New_GAT\core\models.py (ОКОНЧАТЕЛЬНАЯ ВЕРСИЯ БЕЗ ДУБЛИРОВАНИЯ)

from django.db import models
from django.contrib.auth.models import User

class AcademicYear(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return self.name

class School(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class Subject(models.Model):
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='subjects')
    name = models.CharField(max_length=100)
    abbreviation = models.CharField(max_length=50, null=True, blank=True)
    gat_info = models.CharField(max_length=100, blank=True, help_text="Для какого GAT предназначен этот предмет (просто информация)")

    class Meta:
        unique_together = ('school', 'name')
        ordering = ['school', 'name']

    def __str__(self):
        return f"{self.name} ({self.school.name})"

class Quarter(models.Model):
    name = models.CharField(max_length=100)
    year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='quarters')
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-year__start_date', 'start_date']

    def __str__(self):
        return f"{self.name} ({self.year.name})"

class SchoolClass(models.Model):
    name = models.CharField(max_length=10, help_text="Полное название класса, например: 5А или 10")
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='classes')
    subjects = models.ManyToManyField('Subject', through='ClassSubject', related_name='school_classes')
    
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subclasses')
    
    homeroom_teacher = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='homeroom_class',
        verbose_name="Классный руководитель",
        limit_choices_to={'profile__role': 'TEACHER'}
    )

    class Meta:
        unique_together = ('school', 'name')
        ordering = ['school__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.school.name})"

class ClassSubject(models.Model):
    school_class = models.ForeignKey('SchoolClass', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    number_of_questions = models.PositiveIntegerField()

    class Meta:
        unique_together = ('school_class', 'subject')

    def __str__(self):
        return f"{self.school_class} - {self.subject}"

class GatTest(models.Model):
    name = models.CharField(max_length=255)
    test_number = models.PositiveIntegerField()
    test_date = models.DateField()
    quarter = models.ForeignKey('Quarter', on_delete=models.CASCADE, related_name='gattests')
    school_class = models.ForeignKey('SchoolClass', on_delete=models.CASCADE, related_name='gattests')
    subjects = models.ManyToManyField('Subject', related_name='gat_tests')

    class Meta:
        ordering = ['-test_date']

    def __str__(self):
        return self.name

class Student(models.Model):
    student_id = models.CharField(max_length=50, unique=True)
    
    # --- ИЗМЕНЕНИЕ: Заменяем старые поля имени ---
    # last_name = models.CharField(max_length=100)
    # first_name = models.CharField(max_length=100)
    
    # Новые поля для мультиязычности
    last_name_ru = models.CharField('Фамилия (рус.)', max_length=100)
    first_name_ru = models.CharField('Имя (рус.)', max_length=100)
    
    last_name_tj = models.CharField('Насаб (точ.)', max_length=100, blank=True)
    first_name_tj = models.CharField('Ном (точ.)', max_length=100, blank=True)
    
    last_name_en = models.CharField('Last Name (eng.)', max_length=100, blank=True)
    first_name_en = models.CharField('First Name (eng.)', max_length=100, blank=True)
    
    school_class = models.ForeignKey('SchoolClass', on_delete=models.CASCADE, related_name='students')

    class Meta:
        # Сортируем по русской версии фамилии
        ordering = ['school_class', 'last_name_ru', 'first_name_ru']

    def __str__(self):
        # Отображаем русскую версию имени по умолчанию
        return f"{self.last_name_ru} {self.first_name_ru} ({self.student_id})"

class StudentResult(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='results')
    gat_test = models.ForeignKey('GatTest', on_delete=models.CASCADE, related_name='student_results')
    scores = models.JSONField()

    class Meta:
        unique_together = ('student', 'gat_test')
        ordering = ['gat_test', 'student']

    def __str__(self):
        return f"Результат для {self.student} по тесту {self.gat_test}"

class TeacherNote(models.Model):
    """Заметка от преподавателя или администратора по конкретному студенту."""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='notes', verbose_name="Студент")
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_notes', verbose_name="Автор")
    note = models.TextField(verbose_name="Текст заметки")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Заметка для {self.student} от {self.author.username}'