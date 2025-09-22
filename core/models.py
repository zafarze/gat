# core/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
class AcademicYear(models.Model):
    name = models.CharField(max_length=100, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-start_date'] # Сортируем по дате начала, новые сверху

    def __str__(self):
        return self.name

class School(models.Model):
    name = models.CharField(max_length=200, unique=True)
    address = models.CharField(max_length=300)

    class Meta:
        ordering = ['name'] # Сортируем по названию

    def __str__(self):
        return self.name

class Subject(models.Model):
    # --- НОВОЕ ПОЛЕ ---
    # Связываем предмет со школой. Если школа удаляется, удаляются и ее предметы.
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='subjects')
    
    name = models.CharField(max_length=100) # Убираем unique=True отсюда
    abbreviation = models.CharField(max_length=50, null=True, blank=True) # Убираем unique=True
    gat_info = models.CharField(max_length=100, blank=True, help_text="Для какого GAT предназначен этот предмет (просто информация)")

    class Meta:
        # --- ИЗМЕНЕНИЕ ---
        # Название предмета и аббревиатура должны быть уникальными В ПРЕДЕЛАХ ОДНОЙ ШКОЛЫ.
        unique_together = ('school', 'name')
        ordering = ['school', 'name']

    def __str__(self):
        # Отображаем предмет вместе со школой для ясности
        return f"{self.name} ({self.school.name})"

class Quarter(models.Model):
    name = models.CharField(max_length=100)
    year = models.ForeignKey('AcademicYear', on_delete=models.CASCADE, related_name='quarters')
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        ordering = ['-year__start_date', 'start_date'] # Сначала по году, потом по дате начала

    def __str__(self):
        return f"{self.name} ({self.year.name})"

class SchoolClass(models.Model):
    name = models.CharField(max_length=10, help_text="Полное название класса, например: 5А или 10")
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='classes')
    subjects = models.ManyToManyField('Subject', through='ClassSubject', related_name='school_classes')
    
    # --- ВОТ ЭТО ПОЛЕ НУЖНО ДОБАВИТЬ ---
    parent = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='subclasses'
    )

    class Meta:
        unique_together = ('school', 'name')
        ordering = ['school__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.school.name})"
    
    # --- НОВОЕ ПОЛЕ ---
    # Для классов-букв (10А, 10Б) это поле будет указывать на родительский, "базовый" класс (10)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subclasses')

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
        unique_together = ('school_class', 'subject') # Класс может иметь предмет только один раз

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
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    school_class = models.ForeignKey('SchoolClass', on_delete=models.CASCADE, related_name='students')

    class Meta:
        ordering = ['school_class', 'last_name', 'first_name']

    def __str__(self):
        return f"{self.last_name} {self.first_name} ({self.student_id})"

class StudentResult(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='results')
    gat_test = models.ForeignKey('GatTest', on_delete=models.CASCADE, related_name='student_results')
    scores = models.JSONField()

    class Meta:
        unique_together = ('student', 'gat_test')
        ordering = ['gat_test', 'student']

    def __str__(self):
        return f"Результат для {self.student} по тесту {self.gat_test}"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    photo = models.ImageField(upload_to='profile_photos/', null=True, blank=True, default='profile_photos/default.png')

    def __str__(self):
        return f'Профиль для {self.user.username}'

# Сигнал: автоматически создаем профиль, когда создается новый пользователь
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)