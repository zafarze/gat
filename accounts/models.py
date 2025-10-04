# D:\New_GAT\accounts\models.py (ФИНАЛЬНАЯ, ОБЪЕДИНЕННАЯ ВЕРСИЯ)

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Импортируем модели из вашего приложения 'core'
# Убедитесь, что этот импорт правильный для вашей структуры проекта
from core.models import School, Subject, Student

class UserProfile(models.Model):
    """
    Расширенная модель пользователя, которая хранит дополнительную информацию,
    такую как роль, фотография, основная школа и доступы к другим школам.
    """

    # --- СВЯЗЬ С ОСНОВНОЙ МОДЕЛЬЮ USER ---
    # OneToOneField гарантирует, что у каждого пользователя Django будет только один профиль.
    # related_name='profile' позволяет легко получать доступ: request.user.profile
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile',
        verbose_name="Пользователь"
    )
    
    # --- РОЛИ ПОЛЬЗОВАТЕЛЕЙ В СИСТЕМЕ ---
    # Используем TextChoices для более удобного определения ролей, как в вашем файле
    class RoleChoices(models.TextChoices):
        ADMIN = 'ADMIN', 'Администратор'
        SCHOOL_DIRECTOR = 'SCHOOL_DIRECTOR', 'Директор Школы'
        TEACHER = 'TEACHER', 'Учитель'
        STUDENT = 'STUDENT', 'Ученик'
        EXPERT = 'EXPERT', 'Эксперт по предмету'

    role = models.CharField(
        max_length=20,
        choices=RoleChoices.choices,
        default=RoleChoices.TEACHER,
        verbose_name="Роль"
    )
    
    # --- ФОТОГРАФИЯ ПРОФИЛЯ ---
    photo = models.ImageField(
        upload_to='profile_photos/', # Рекомендуется отдельная папка для фото профилей
        null=True,
        blank=True,
        verbose_name="Фотография профиля"
    )

    # --- ОСНОВНАЯ ПРИВЯЗКА ДЛЯ РАЗНЫХ РОЛЕЙ ---
    # Основная школа пользователя (для Директора, Учителя)
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Основная школа",
        help_text="Обязательно для Директора и Учителя"
    )
    
    # Предмет, который курирует Эксперт
    subject = models.ForeignKey(
        Subject,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Предмет экспертизы",
        help_text="Обязательно для Эксперта"
    )

    # Связь с записью ученика (для роли Ученик)
    student = models.OneToOneField(
        Student,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name="Карточка Ученика",
        help_text="Обязательно для роли Ученик"
    )

    # --- НОВОЕ ПОЛЕ ДЛЯ РАСШИРЕННЫХ ПРАВ ДОСТУПА ---
    # Это поле позволяет дать одному директору доступ к нескольким школам.
    # Администратор сможет управлять этими связями на новой странице.
    additional_schools = models.ManyToManyField(
        School,
        related_name='accessible_by',
        blank=True,
        verbose_name="Дополнительный доступ к школам",
        help_text="Выберите школы, к которым у директора будет дополнительный доступ"
    )

    def __str__(self):
        # Возвращает полное имя пользователя для удобного отображения в админ-панели.
        return self.user.get_full_name() or self.user.username
        
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"

# --- СИГНАЛЫ ДЛЯ АВТОМАТИЧЕСКОГО СОЗДАНИЯ ПРОФИЛЯ ---
# Этот код гарантирует, что как только новый пользователь Django будет создан
# (например, через админ-панель или форму регистрации), для него
# автоматически создастся связанный объект UserProfile.

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    Создает профиль для нового пользователя или сохраняет существующий.
    """
    if created:
        UserProfile.objects.create(user=instance)
    # Проверка hasattr нужна, чтобы избежать ошибок при создании суперпользователя через консоль
    if hasattr(instance, 'profile'):
        instance.profile.save()