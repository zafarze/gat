# D:\GAT\core\templatetags\custom_filters.py

from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Позволяет получать значение из словаря по ключу-переменной в шаблоне.
    Использование: {{ my_dictionary|get_item:my_variable }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    # Для списков, чтобы получать элемент по индексу
    try:
        return dictionary[key]
    except (TypeError, IndexError, KeyError):
        return None

@register.filter(name='get_subject_name')
def get_subject_name(subject_id, subjects_dict):
    """
    Получает название предмета по ID из словаря предметов.
    Использование: {{ subject_id|get_subject_name:subjects_dict }}
    """
    return subjects_dict.get(str(subject_id), f"Предмет {subject_id}")

@register.filter(name='format_difficulty')
def format_difficulty(difficulty_code):
    """
    Форматирует код сложности в читаемый текст.
    Использование: {{ question.difficulty|format_difficulty }}
    """
    difficulty_map = {
        'EASY': 'Легкий',
        'MEDIUM': 'Средний',
        'HARD': 'Сложный'
    }
    return difficulty_map.get(difficulty_code, difficulty_code)

@register.filter(name='check_correct_answer')
def check_correct_answer(question, student_answer):
    """
    Проверяет, правильный ли ответ дал студент на вопрос.
    Использование: {{ question|check_correct_answer:student_answer }}
    """
    if not student_answer:
        return False
    
    # Получаем правильный вариант ответа
    correct_option = question.options.filter(is_correct=True).first()
    if not correct_option:
        return False
    
    # Сравниваем порядок выбранного варианта
    return student_answer.chosen_option_order == correct_option.id

@register.filter(name='get_correct_option_text')
def get_correct_option_text(question):
    """
    Возвращает текст правильного ответа на вопрос.
    Использование: {{ question|get_correct_option_text }}
    """
    correct_option = question.options.filter(is_correct=True).first()
    return correct_option.text if correct_option else "Не указан"

@register.filter(name='split_topics')
def split_topics(topics_queryset, count=5):
    """
    Разделяет queryset тем на группы для отображения в несколько колонок.
    Использование: {{ topics|split_topics:3 }}
    """
    topics_list = list(topics_queryset)
    return [topics_list[i:i + count] for i in range(0, len(topics_list), count)]

@register.filter(name='to_json')
def to_json(value):
    """
    Конвертирует значение в JSON строку.
    Использование: {{ data|to_json }}
    """
    return mark_safe(json.dumps(value))

@register.filter(name='percentage')
def percentage(value, total):
    """
    Вычисляет процентное значение.
    Использование: {{ correct_count|percentage:total_count }}%
    """
    if total == 0:
        return 0
    return round((value / total) * 100, 1)

@register.filter(name='get_student_score')
def get_student_score(scores_by_subject, subject_id):
    """
    Получает балл студента по конкретному предмету из JSON поля.
    Использование: {{ result.scores_by_subject|get_student_score:subject.id }}
    """
    if isinstance(scores_by_subject, dict):
        subject_data = scores_by_subject.get(str(subject_id), {})
        if isinstance(subject_data, dict):
            # Подсчитываем правильные ответы
            correct_answers = sum(1 for is_correct in subject_data.values() if is_correct)
            return correct_answers
    return 0

@register.filter(name='subject_has_questions')
def subject_has_questions(subject, school_class):
    """
    Проверяет, есть ли вопросы для данного предмета и класса.
    Использование: {{ subject|subject_has_questions:school_class }}
    """
    return subject.bank_questions.filter(school_class=school_class).exists()

@register.simple_tag
def calculate_progress_color(percentage):
    """
    Возвращает цвет для индикатора прогресса на основе процента.
    Использование: {% calculate_progress_color percentage as color %}
    """
    if percentage >= 80:
        return "success"
    elif percentage >= 60:
        return "warning"
    else:
        return "danger"