# D:\GAT\core\templatetags\custom_filters.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    # ... (твой существующий код для get_item) ...
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    if isinstance(dictionary, (list, tuple)):
        try:
            key = int(key)
            if 0 <= key < len(dictionary):
                return dictionary[key]
        except (ValueError, TypeError):
            pass
    return None

# --- 👇 ДОБАВЬ ЭТОТ КОД НИЖЕ 👇 ---

@register.filter(name='format_difficulty')
def format_difficulty(value):
    """ Преобразует код сложности в читаемый текст """
    if value == 'EASY':
        return 'Легкий'
    elif value == 'MEDIUM':
        return 'Средний'
    elif value == 'HARD':
        return 'Сложный'
    return value 