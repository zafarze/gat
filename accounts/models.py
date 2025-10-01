# D:\New_GAT\accounts\models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from core.models import School, Subject, Student

class RoleChoices(models.TextChoices):
    ADMIN = 'ADMIN', 'Генеральный Директор'
    SCHOOL_DIRECTOR = 'SCHOOL_DIRECTOR', 'Директор Школы'
    TEACHER = 'TEACHER', 'Учитель'
    STUDENT = 'STUDENT', 'Ученик'
    EXPERT = 'EXPERT', 'Эксперт по предмету'

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    photo = models.ImageField(upload_to='users/', null=True, blank=True, verbose_name="Фотография")
    
    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.TEACHER,
        verbose_name="Роль"
    )

    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Школа",
        help_text="Обязательно для Директора и Учителя"
    )
    
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Предмет экспертизы",
        help_text="Обязательно для Эксперта"
    )

    student = models.OneToOneField(
        Student,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Карточка Ученика",
        help_text="Обязательно для роли Ученик"
    )

    def __str__(self):
        return f'Профиль пользователя {self.user.username}'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    # Добавлена проверка hasattr для избежания ошибок при создании суперпользователя
    if hasattr(instance, 'profile'):
        instance.profile.save()