# D:\GAT\core\views\reports_upload.py

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
# --- Импорты для поиска пользователей ---
from django.contrib.auth.models import User
from django.db.models import Q
from accounts.models import UserProfile

from core.forms import UploadFileForm
from core import services
from core.models import Notification, SchoolClass

@login_required
def upload_results_view(request):
    """Загрузка результатов тестов с умной рассылкой уведомлений"""
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        test_date = None
        
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
            test_date = services.extract_test_date_from_excel(uploaded_file)
            form = UploadFileForm(request.POST, request.FILES, test_date=test_date)

        if form.is_valid():
            gat_test = form.cleaned_data['gat_test']
            excel_file = request.FILES['file']

            try:
                success, report_data = services.process_student_results_upload(gat_test, excel_file)
                print(f"--- GAT UPLOAD REPORT: {report_data}")

                if success:
                    total = report_data.get('total_unique_students', 0)
                    errors = report_data.get('errors', [])
                    
                    success_msg = f"Файл успешно обработан. Загружено результатов для {total} учеников."
                    messages.success(request, success_msg)
                    
                    for error in errors:
                        messages.error(request, error)

                    # =====================================================
                    # --- 🔔 ЛОГИКА УМНОЙ РАССЫЛКИ УВЕДОМЛЕНИЙ ---
                    # =====================================================
                    
                    result_link = reverse(
                        'core:detailed_results_list',
                        kwargs={'test_number': gat_test.test_number}
                    ) + f"?test_id={gat_test.id}"
                    
                    school_name = gat_test.school.name
                    class_name = gat_test.school_class.name
                    notification_msg = f"📊 Результаты GAT-{gat_test.test_number} ({school_name}, {class_name}) загружены. Обработано: {total}."

                    # 1. Собираем список получателей (используем set, чтобы избежать дублей)
                    recipients = set()
                    
                    # -> Тот, кто загрузил (всегда получает)
                    recipients.add(request.user)

                    # -> ГРУППА 1: Глобальные наблюдатели (Суперадмины и Эксперты)
                    # Они видят всё, поэтому получают уведомления от всех школ
                    global_watchers = User.objects.filter(
                        Q(is_superuser=True) | 
                        Q(profile__role=UserProfile.Role.EXPERT)
                    )
                    for user in global_watchers:
                        recipients.add(user)

                    # -> ГРУППА 2: Сотрудники ЭТОЙ школы (Директора и Учителя)
                    # Директор школы А получит это, только если gat_test.school == А
                    target_school = gat_test.school
                    
                    school_staff = User.objects.filter(
                        # Директора, у которых эта школа в списке доступных
                        Q(profile__role=UserProfile.Role.DIRECTOR, profile__schools=target_school) |
                        # Учителя, привязанные к этой школе
                        Q(profile__role=UserProfile.Role.TEACHER, profile__school=target_school)
                    )
                    for staff in school_staff:
                        recipients.add(staff)

                    # -> ГРУППА 3: Классные руководители затронутых классов
                    target_class = gat_test.school_class
                    
                    # Если тест для параллели (например, "5"), находим классруков 5А, 5Б, 5В...
                    if target_class.parent is None:
                        homeroom_teachers = User.objects.filter(
                            profile__role=UserProfile.Role.HOMEROOM_TEACHER,
                            profile__homeroom_class__parent=target_class
                        )
                    else:
                        # Если тест для конкретного класса (редко, но возможно)
                        homeroom_teachers = User.objects.filter(
                            profile__role=UserProfile.Role.HOMEROOM_TEACHER,
                            profile__homeroom_class=target_class
                        )
                    
                    for teacher in homeroom_teachers:
                        recipients.add(teacher)

                    # 2. Создаем уведомления
                    notifications_to_create = []
                    for recipient in recipients:
                        notifications_to_create.append(Notification(
                            user=recipient,
                            message=notification_msg,
                            link=result_link
                        ))
                    
                    # Массовое создание (быстрее, чем в цикле)
                    Notification.objects.bulk_create(notifications_to_create)
                    
                    # =====================================================

                    return redirect(result_link)
                else:
                    messages.error(request, f"Ошибка обработки файла: {report_data}")

            except Exception as e:
                messages.error(request, f"Произошла критическая ошибка при обработке файла: {str(e)}")
        else:
            messages.error(request, "Форма содержит ошибки. Проверьте введенные данные.")
    else:
        form = UploadFileForm()

    context = {
        'form': form,
        'title': 'Загрузка результатов GAT тестов'
    }
    return render(request, 'results/upload_form.html', context)