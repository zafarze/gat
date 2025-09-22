# D:\New_GAT\core\admin.py (ПОЛНЫЙ И ИСПРАВЛЕННЫЙ КОД)

from django.contrib import admin
from .models import (
    AcademicYear, School, Subject, Quarter, SchoolClass,
    ClassSubject, GatTest, Student, StudentResult
)

class ClassSubjectInline(admin.TabularInline):
    model = ClassSubject
    extra = 1

@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'school')
    list_filter = ('school',)
    search_fields = ('name', 'school__name')
    inlines = [ClassSubjectInline]
    ordering = ('name',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'last_name', 'first_name', 'school_class')
    list_filter = ('school_class__school', 'school_class')
    search_fields = ('last_name', 'first_name', 'student_id')
    ordering = ('school_class', 'last_name', 'first_name')
    # Ускоряем загрузку страницы, подгружая связанные объекты одним запросом
    list_select_related = ('school_class', 'school_class__school')

# --- Остальные модели ---
# (здесь код не менялся, но приведен для полноты)
@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date')
    search_fields = ('name',)

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    list_display = ('name', 'address')
    search_fields = ('name',)

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    # --- ИЗМЕНЕНИЯ ---
    list_display = ('name', 'abbreviation', 'school') # Добавили школу в список
    list_filter = ('school',) # Добавили фильтр по школам
    search_fields = ('name', 'abbreviation', 'school__name') # Добавили поиск по названию школы
    ordering = ('school', 'name') # Добавили сортировку

@admin.register(Quarter)
class QuarterAdmin(admin.ModelAdmin):
    list_display = ('name', 'year', 'start_date', 'end_date')
    list_filter = ('year',)
    search_fields = ('name',)
    ordering = ('-year__name', 'start_date')

@admin.register(GatTest)
class GatTestAdmin(admin.ModelAdmin):
    list_display = ('name', 'school_class', 'quarter', 'test_date')
    list_filter = ('school_class__school', 'quarter__year', 'quarter')
    search_fields = ('name', 'school_class__name')
    autocomplete_fields = ['school_class', 'quarter']

@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    list_display = ('student', 'gat_test')
    list_filter = ('gat_test__school_class__school', 'gat_test')
    search_fields = ('student__last_name', 'student__student_id', 'gat_test__name')