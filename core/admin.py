# D:\GAT\core\admin.py (ОБНОВЛЕННАЯ ВЕРСИЯ)

from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import (
    AcademicYear, Quarter, School, SchoolClass, Subject,
    GatTest, Student, StudentResult, TeacherNote, QuestionCount,
    QuestionTopic, BankQuestion, BankAnswerOption, StudentAnswer,
    DifficultyRule, Notification, University, Faculty
)

# ==========================================================
# --- INLINE МОДЕЛИ ---
# ==========================================================

class BankAnswerOptionInline(admin.TabularInline):
    """Inline для вариантов ответов к вопросам из банка."""
    model = BankAnswerOption
    extra = 4
    min_num = 2
    max_num = 5
    fields = ('text', 'is_correct', 'created_at')
    readonly_fields = ('created_at',)

class BankQuestionInline(admin.TabularInline):
    """Inline для вопросов в теме."""
    model = BankQuestion
    extra = 0
    fields = ('text', 'difficulty', 'question_type', 'created_at')
    readonly_fields = ('created_at',)
    show_change_link = True

# ==========================================================
# --- АДМИН-ПАНЕЛИ ДЛЯ НОВЫХ МОДЕЛЕЙ ЦЕНТРА ВОПРОСОВ ---
# ==========================================================

@admin.register(QuestionTopic)
class QuestionTopicAdmin(admin.ModelAdmin):
    """Админка для Тем Вопросов."""
    list_display = ('name', 'subject', 'school_class', 'question_count', 'author', 'created_at')
    list_filter = ('subject', 'school_class__school', 'school_class')
    search_fields = ('name', 'subject__name', 'school_class__name')
    autocomplete_fields = ['subject', 'school_class', 'author']
    list_select_related = ('subject', 'school_class', 'author')
    inlines = [BankQuestionInline]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_question_count=Count('questions'))
        return queryset

    def question_count(self, obj):
        return obj._question_count
    question_count.short_description = 'Кол-во вопросов'
    question_count.admin_order_field = '_question_count'

@admin.register(BankQuestion)
class BankQuestionAdmin(admin.ModelAdmin):
    """Админка для Вопросов из Банка."""
    list_display = ('short_text', 'topic', 'subject', 'school_class', 'difficulty', 'option_count', 'correct_option', 'author', 'created_at')
    list_filter = ('subject', 'school_class', 'difficulty', 'topic')
    search_fields = ('text', 'topic__name', 'subject__name')
    autocomplete_fields = ['topic', 'subject', 'school_class', 'author']
    list_select_related = ('topic', 'subject', 'school_class', 'author')
    inlines = [BankAnswerOptionInline]
    readonly_fields = ('created_at', 'updated_at')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_option_count=Count('options'))
        return queryset

    def short_text(self, obj):
        return obj.text[:80] + '...' if len(obj.text) > 80 else obj.text
    short_text.short_description = 'Текст вопроса'

    def option_count(self, obj):
        return obj._option_count
    option_count.short_description = 'Вариантов'
    option_count.admin_order_field = '_option_count'

    def correct_option(self, obj):
        correct_options = obj.options.filter(is_correct=True)
        if correct_options.exists():
            return correct_options.first().text[:50] + '...' if len(correct_options.first().text) > 50 else correct_options.first().text
        return '—'
    correct_option.short_description = 'Правильный ответ'

@admin.register(BankAnswerOption)
class BankAnswerOptionAdmin(admin.ModelAdmin):
    """Админка для Вариантов Ответов из Банка."""
    list_display = ('short_text', 'question', 'is_correct', 'created_at')
    list_filter = ('is_correct', 'question__subject', 'question__school_class')
    search_fields = ('text', 'question__text')
    autocomplete_fields = ['question']
    list_select_related = ('question', 'question__subject', 'question__school_class')

    def short_text(self, obj):
        return obj.text[:60] + '...' if len(obj.text) > 60 else obj.text
    short_text.short_description = 'Текст ответа'

# ==========================================================
# --- АДМИН-ПАНЕЛИ ДЛЯ НАСТРОЕК И ПРАВИЛ ---
# ==========================================================

@admin.register(DifficultyRule)
class DifficultyRuleAdmin(admin.ModelAdmin):
    """Админка для Правил Сложности (Easy/Medium/Hard)."""
    list_display = ('subject', 'school_class', 'display_ratios')
    list_filter = ('school_class', 'subject')
    autocomplete_fields = ['school_class', 'subject']
    
    def display_ratios(self, obj):
        return f"🟢 {obj.easy_percent}% | 🟡 {obj.medium_percent}% | 🔴 {obj.hard_percent}%"
    display_ratios.short_description = "Easy / Medium / Hard"

@admin.register(QuestionCount)
class QuestionCountAdmin(admin.ModelAdmin):
    """Админка для Количества Вопросов."""
    list_display = ('school_class', 'subject', 'number_of_questions')
    list_filter = ('school_class__school', 'subject')
    search_fields = ('school_class__name', 'subject__name')
    autocomplete_fields = ['school_class', 'subject']

# ==========================================================
# --- АДМИН-ПАНЕЛИ СУЩЕСТВУЮЩИХ МОДЕЛЕЙ ---
# ==========================================================

@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    """Админка для Учебных Годов."""
    list_display = ('name', 'start_date', 'end_date')
    search_fields = ('name',)

@admin.register(Quarter)
class QuarterAdmin(admin.ModelAdmin):
    """Админка для Четвертей."""
    list_display = ('name', 'year', 'start_date', 'end_date')
    list_filter = ('year',)
    search_fields = ('name',)
    autocomplete_fields = ['year']

@admin.register(School)
class SchoolAdmin(admin.ModelAdmin):
    """Админка для Школ."""
    list_display = ('name', 'school_id', 'city', 'class_count', 'topic_count')
    search_fields = ('name', 'city', 'school_id')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _class_count=Count('classes', distinct=True),
            _topic_count=Count('classes__topics', distinct=True)
        )
        return queryset

    def class_count(self, obj):
        return obj._class_count
    class_count.short_description = 'Кол-во классов'
    class_count.admin_order_field = '_class_count'

    def topic_count(self, obj):
        return obj._topic_count
    topic_count.short_description = 'Кол-во тем'
    topic_count.admin_order_field = '_topic_count'

@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    """Админка для Классов."""
    list_display = ('name', 'school', 'parent', 'student_count', 'topic_count', 'bank_question_count')
    list_filter = ('school',)
    search_fields = ('name', 'school__name')
    list_select_related = ('school', 'parent')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _student_count=Count('students', distinct=True),
            _topic_count=Count('topics', distinct=True),
            _bank_question_count=Count('bank_questions', distinct=True)
        )
        return queryset

    def student_count(self, obj):
        return obj._student_count
    student_count.short_description = 'Кол-во учеников'
    student_count.admin_order_field = '_student_count'

    def topic_count(self, obj):
        return obj._topic_count
    topic_count.short_description = 'Кол-во тем'
    topic_count.admin_order_field = '_topic_count'

    def bank_question_count(self, obj):
        return obj._bank_question_count
    bank_question_count.short_description = 'Кол-во вопросов'
    bank_question_count.admin_order_field = '_bank_question_count'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Админка для Предметов."""
    list_display = ('name', 'abbreviation', 'topic_count', 'bank_question_count')
    search_fields = ('name', 'abbreviation')

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _topic_count=Count('topics', distinct=True),
            _bank_question_count=Count('bank_questions', distinct=True)
        )
        return queryset

    def topic_count(self, obj):
        return obj._topic_count
    topic_count.short_description = 'Кол-во тем'
    topic_count.admin_order_field = '_topic_count'

    def bank_question_count(self, obj):
        return obj._bank_question_count
    bank_question_count.short_description = 'Кол-во вопросов'
    bank_question_count.admin_order_field = '_bank_question_count'

@admin.register(GatTest)
class GatTestAdmin(admin.ModelAdmin):
    """Админка для GAT Тестов."""
    # ✨ ОБНОВЛЕНО: Добавлено is_published_for_students
    list_display = ('name', 'school', 'school_class', 'test_date', 'quarter', 'day', 'question_count', 'shuffle_status', 'is_published_for_students')
    list_filter = ('school', 'school_class', 'quarter', 'test_date', 'day', 'is_published_for_students')
    search_fields = ('name', 'school__name', 'school_class__name')
    autocomplete_fields = ['school', 'school_class', 'quarter']
    date_hierarchy = 'test_date'
    ordering = ('-test_date',)
    filter_horizontal = ['questions']  # Для удобного выбора вопросов
    readonly_fields = ('created_at', 'updated_at')
    
    # ✨ ОБНОВЛЕНО: Позволяет менять статус публикации прямо из списка
    list_editable = ('is_published_for_students',)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_question_count=Count('questions'))
        return queryset

    def question_count(self, obj):
        return obj._question_count
    question_count.short_description = 'Вопросов'
    question_count.admin_order_field = '_question_count'

    def shuffle_status(self, obj):
        status = []
        if obj.shuffle_questions:
            status.append('📋 Вопросы')
        if obj.shuffle_options:
            status.append('🔀 Варианты')
        return format_html('<br>'.join(status)) if status else '—'
    shuffle_status.short_description = 'Перемешивание'

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    """Админка для Учеников."""
    list_display = ('full_name_ru', 'student_id', 'school_class', 'status')
    list_filter = ('status', 'school_class__school',)
    search_fields = ('last_name_ru', 'first_name_ru', 'student_id')
    ordering = ('school_class', 'last_name_ru', 'first_name_ru')
    list_select_related = ('school_class', 'school_class__school')
    autocomplete_fields = ['school_class']

@admin.register(StudentResult)
class StudentResultAdmin(admin.ModelAdmin):
    """Админка для Результатов Учеников."""
    list_display = ('student', 'gat_test', 'display_scores', 'total_score', 'booklet_variant')
    list_filter = ('gat_test__school', 'gat_test__quarter', 'gat_test')
    search_fields = ('student__last_name_ru', 'student__student_id', 'gat_test__name')
    list_select_related = ('student', 'gat_test', 'gat_test__school')
    autocomplete_fields = ['student', 'gat_test']
    readonly_fields = ('created_at', 'updated_at')

    @admin.display(description='Результаты (предметы)')
    def display_scores(self, obj):
        if not isinstance(obj.scores_by_subject, dict) or not obj.scores_by_subject:
            return "Нет данных"
        
        try:
            # Получаем предметы из связанных вопросов теста
            subject_ids = set()
            for question in obj.gat_test.questions.all():
                subject_ids.add(question.subject_id)
            
            subject_map = {
                str(s.id): s.name 
                for s in Subject.objects.filter(id__in=subject_ids)
            }
            
            subject_names = [
                subject_map.get(sub_id, f"ID {sub_id}?") 
                for sub_id in obj.scores_by_subject.keys()
            ]
            
            return ", ".join(subject_names)

        except Exception:
            return ", ".join(obj.scores_by_subject.keys())

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    """Админка для Ответов Учеников."""
    list_display = ('student_name', 'gat_test', 'question_short', 'is_correct', 'chosen_option_order', 'created_at')
    list_filter = ('is_correct', 'result__gat_test__school', 'result__gat_test')
    search_fields = ('result__student__last_name_ru', 'question__text')
    list_select_related = ('result__student', 'result__gat_test', 'question')
    readonly_fields = ('created_at', 'updated_at')

    def student_name(self, obj):
        return obj.result.student.full_name_ru
    student_name.short_description = 'Ученик'
    student_name.admin_order_field = 'result__student__last_name_ru'

    def gat_test(self, obj):
        return obj.result.gat_test.name
    gat_test.short_description = 'GAT Тест'
    gat_test.admin_order_field = 'result__gat_test__name'

    def question_short(self, obj):
        return obj.question.text[:60] + '...' if len(obj.question.text) > 60 else obj.question.text
    question_short.short_description = 'Вопрос'

@admin.register(TeacherNote)
class TeacherNoteAdmin(admin.ModelAdmin):
    """Админка для Заметок Учителей."""
    list_display = ('student', 'author', 'created_at', 'short_note')
    list_filter = ('author', 'student__school_class__school')
    search_fields = ('student__last_name_ru', 'author__username', 'note')
    autocomplete_fields = ['student', 'author']
    readonly_fields = ('created_at',)

    def short_note(self, obj):
        return obj.note[:50] + '...' if len(obj.note) > 50 else obj.note
    short_note.short_description = 'Заметка (коротко)'

# ==========================================================
# --- ДОПОЛНИТЕЛЬНЫЕ МОДЕЛИ ---
# ==========================================================

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'message', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('user__username', 'message')
    autocomplete_fields = ['user']

@admin.register(University)
class UniversityAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'website')
    search_fields = ('name', 'city')

@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('name', 'university', 'required_subjects_count')
    list_filter = ('university',)
    search_fields = ('name', 'university__name')
    autocomplete_fields = ['university']
    filter_horizontal = ['required_subjects']

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(_subjects_count=Count('required_subjects'))
        return queryset

    def required_subjects_count(self, obj):
        return obj._subjects_count
    required_subjects_count.short_description = 'Требуемых предметов'
    required_subjects_count.admin_order_field = '_subjects_count'