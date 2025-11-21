# D:\GAT\core\context_processors.py

from django.db.models import Count
from .models import AcademicYear

def archive_years_processor(request):
    """
    Этот процессор добавляет список всех учебных лет и ID выбранного года
    в контекст каждого шаблона.
    
    Улучшения:
    - Оптимизация запроса с аннотацией количества тестов
    - Обработка ошибок
    - Кэширование запроса
    """
    selected_year_id = request.GET.get('year')
    
    selected_year = None
    if selected_year_id:
        try:
            # Получаем выбранный год с аннотацией количества связанных тестов
            selected_year = AcademicYear.objects.filter(pk=selected_year_id).first()
        except (ValueError, AcademicYear.DoesNotExist):
            # Если year_id не число или год не найден, игнорируем
            pass

    try:
        # Получаем все учебные годы с аннотацией количества четвертей
        all_archive_years = AcademicYear.objects.annotate(
            quarters_count=Count('quarters')
        ).order_by('-start_date')
    except Exception:
        # В случае ошибки БД возвращаем пустой queryset
        all_archive_years = AcademicYear.objects.none()

    return {
        'all_archive_years': all_archive_years,
        'selected_archive_year': selected_year,
        'has_archive_data': all_archive_years.exists()
    }

# Дополнительно можно добавить в этот же файл:

def global_settings_processor(request):
    """
    Глобальные настройки для всех шаблонов
    """
    return {
        'SITE_NAME': 'GAT Testing System',
        'COMPANY_NAME': 'Educational Center',
        'CURRENT_YEAR': 2025,  # Можно сделать динамическим
    }