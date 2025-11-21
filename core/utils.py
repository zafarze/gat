# D:\GAT\core\utils.py (ОБНОВЛЕННАЯ ВЕРСИЯ ДЛЯ ЦЕНТРА ВОПРОСОВ)

def calculate_grade_from_percentage(percentage):
    """
    Единая функция для конвертации процента в 10-балльную оценку.
    Используется по всему проекту.
    """
    if not isinstance(percentage, (int, float)):
        return 1 # Возвращаем минимальную оценку, если данные некорректны

    if percentage >= 91: return 10
    elif percentage >= 81: return 9
    elif percentage >= 71: return 8
    elif percentage >= 61: return 7
    elif percentage >= 51: return 6
    elif percentage >= 41: return 5
    elif percentage >= 31: return 4
    elif percentage >= 21: return 3
    elif percentage >= 11: return 2
    else: return 1

# НОВЫЕ ФУНКЦИИ ДЛЯ ЦЕНТРА ВОПРОСОВ

def validate_question_data(question_text, options):
    """
    Проверяет корректность данных вопроса и вариантов ответов.
    """
    errors = []
    
    if not question_text or len(question_text.strip()) < 5:
        errors.append("Текст вопроса должен содержать не менее 5 символов")
    
    if not options or len(options) < 2:
        errors.append("Должно быть не менее 2 вариантов ответа")
    
    correct_options = [opt for opt in options if opt.get('is_correct', False)]
    if len(correct_options) != 1:
        errors.append("Должен быть ровно один правильный вариант ответа")
    
    return errors

def calculate_difficulty_statistics(questions):
    """
    Рассчитывает статистику сложности вопросов.
    """
    total = questions.count()
    if total == 0:
        return {
            'easy': 0,
            'medium': 0,
            'hard': 0,
            'easy_percent': 0,
            'medium_percent': 0,
            'hard_percent': 0
        }
    
    easy = questions.filter(difficulty='EASY').count()
    medium = questions.filter(difficulty='MEDIUM').count()
    hard = questions.filter(difficulty='HARD').count()
    
    return {
        'easy': easy,
        'medium': medium,
        'hard': hard,
        'easy_percent': round((easy / total) * 100, 1),
        'medium_percent': round((medium / total) * 100, 1),
        'hard_percent': round((hard / total) * 100, 1)
    }

def generate_question_bank_report(topic_id=None, subject_id=None, class_id=None):
    """
    Генерирует отчет по банку вопросов с фильтрацией.
    """
    from .models import BankQuestion, QuestionTopic
    
    questions = BankQuestion.objects.all()
    
    if topic_id:
        questions = questions.filter(topic_id=topic_id)
    if subject_id:
        questions = questions.filter(subject_id=subject_id)
    if class_id:
        questions = questions.filter(school_class_id=class_id)
    
    stats = calculate_difficulty_statistics(questions)
    
    topics_with_counts = QuestionTopic.objects.annotate(
        question_count=models.Count('questions')
    ).filter(questions__in=questions).distinct()
    
    return {
        'total_questions': questions.count(),
        'difficulty_stats': stats,
        'topics_with_counts': topics_with_counts,
        'subjects_covered': questions.values('subject__name').annotate(
            count=models.Count('id')
        ).order_by('-count')
    }

def export_questions_to_excel(questions_queryset, file_path):
    """
    Экспортирует вопросы в Excel файл.
    """
    import pandas as pd
    from django.utils import timezone
    
    data = []
    for question in questions_queryset.select_related('topic', 'subject', 'school_class'):
        correct_option = question.options.filter(is_correct=True).first()
        
        data.append({
            'ID': question.id,
            'Текст вопроса': question.text,
            'Тема': question.topic.name,
            'Предмет': question.subject.name,
            'Класс': question.school_class.name,
            'Сложность': question.get_difficulty_display(),
            'Правильный ответ': correct_option.text if correct_option else 'Не указан',
            'Автор': question.author.username if question.author else 'Не указан',
            'Дата создания': timezone.localtime(question.created_at).strftime('%Y-%m-%d %H:%M'),
            'Теги': question.tags or ''
        })
    
    df = pd.DataFrame(data)
    df.to_excel(file_path, index=False, engine='openpyxl')
    return file_path