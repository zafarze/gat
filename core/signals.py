# D:\GAT\core\signals.py

from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from .models import BankQuestion, StudentResult

# Пример будущих сигналов:
# @receiver(post_save, sender=BankQuestion)
# def update_question_count(sender, instance, created, **kwargs):
#     """Обновляет счетчик вопросов при создании нового вопроса"""
#     if created:
#         # Логика обновления счетчиков
#         pass

# @receiver(pre_delete, sender=StudentResult)
# def cleanup_student_answers(sender, instance, **kwargs):
#     """Очищает ответы ученика при удалении результата"""
#     instance.answers.all().delete()