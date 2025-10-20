# D:\New_GAT\core\context_processors.py

from .models import AcademicYear

def archive_years_processor(request):
    """
    Этот процессор добавляет список всех учебных лет и ID выбранного года
    в контекст каждого шаблона.
    """
    selected_year_id = request.GET.get('year')
    
    # Пытаемся получить объект выбранного года, чтобы отобразить его имя
    selected_year = None
    if selected_year_id:
        try:
            selected_year = AcademicYear.objects.get(pk=selected_year_id)
        except AcademicYear.DoesNotExist:
            pass

    return {
        'all_archive_years': AcademicYear.objects.all().order_by('-name'),
        'selected_archive_year': selected_year
    }