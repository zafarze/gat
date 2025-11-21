# D:\GAT\core\views\students_crud.py (НОВЫЙ ФАЙЛ)

import json
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, UpdateView
from django.contrib.auth.decorators import login_required

from accounts.models import UserProfile
from ..forms import StudentForm, StudentUploadForm
from ..models import School, SchoolClass, Student
from ..services import process_student_upload
from .permissions import get_accessible_schools

# =============================================================================
# --- МИКСИН ДЛЯ ПРОВЕРКИ ПРАВ ДОСТУПА ---
# =============================================================================

class StudentAccessMixin:
    """
    Миксин для проверки прав Суперпользователя или Директора
    на управление учениками конкретной школы.
    """
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        target_school = None

        if self.request.method == 'POST':
            # Для CreateView
            if 'school_class' in request.POST:
                try:
                    school_class = SchoolClass.objects.select_related('school').get(pk=request.POST['school_class'])
                    target_school = school_class.school
                except SchoolClass.DoesNotExist:
                    pass
        
        # Для UpdateView и DeleteView
        if 'pk' in kwargs:
            try:
                student = Student.objects.select_related('school_class__school').get(pk=kwargs['pk'])
                target_school = student.school_class.school
            except Student.DoesNotExist:
                pass
        
        # Для CreateView (GET-запрос)
        if 'class_id' in request.GET:
             try:
                school_class = SchoolClass.objects.select_related('school').get(pk=request.GET['class_id'])
                target_school = school_class.school
             except SchoolClass.DoesNotExist:
                 pass

        is_allowed = False
        if user.is_superuser:
            is_allowed = True
        elif target_school and hasattr(user, 'profile') and user.profile.role == UserProfile.Role.DIRECTOR:
            if target_school in get_accessible_schools(user):
                is_allowed = True
        elif not target_school and user.is_superuser:
            # Разрешаем, если школа не определена (например, форма загрузки)
             is_allowed = True

        if not is_allowed:
            raise PermissionDenied("У вас нет прав для выполнения этого действия с учениками данной школы.")

        return super().dispatch(request, *args, **kwargs)

# =============================================================================
# --- CRUD ОПЕРАЦИИ (С ПРАВАМИ ДИРЕКТОРА) ---
# =============================================================================

class StudentCreateView(LoginRequiredMixin, StudentAccessMixin, CreateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'
    
    def get_success_url(self):
        return reverse_lazy('core:student_list', kwargs={'class_id': self.object.school_class.id})

    def get_initial(self):
        if class_id := self.request.GET.get('class_id'):
            return {'school_class': class_id}
        return super().get_initial()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Добавить ученика'
        class_id = self.request.GET.get('class_id')
        context['class_id'] = class_id
        if class_id:
            context['cancel_url'] = reverse_lazy('core:student_list', kwargs={'class_id': class_id})
        else:
            context['cancel_url'] = reverse_lazy('core:student_school_list')
        return context

    def form_valid(self, form):
        messages.success(self.request, "Ученик успешно добавлен.")
        return super().form_valid(form)

class StudentUpdateView(LoginRequiredMixin, StudentAccessMixin, UpdateView):
    model = Student
    form_class = StudentForm
    template_name = 'students/student_form.html'
    
    def get_success_url(self):
        return reverse_lazy('core:student_list', kwargs={'class_id': self.object.school_class.id})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Редактировать ученика'
        context['class_id'] = self.object.school_class.id
        context['cancel_url'] = self.get_success_url()
        return context

    def form_valid(self, form):
        messages.success(self.request, "Данные ученика успешно обновлены.")
        return super().form_valid(form)

class StudentDeleteView(LoginRequiredMixin, StudentAccessMixin, DeleteView):
    model = Student
    template_name = 'students/student_confirm_delete.html'

    def get_success_url(self):
        if self.object:
            return reverse_lazy('core:student_list', kwargs={'class_id': self.object.school_class_id})
        return reverse_lazy('core:student_school_list')

    def form_valid(self, form):
        student_name = str(self.object)
        success_url = self.get_success_url()
        self.object.delete()

        if self.request.htmx:
            trigger = {
                "close-delete-modal": True, 
                "show-message": {"text": f"Ученик {student_name} удален.", "type": "error"},
                "force-refresh": True # Говорим списку обновиться
            }
            return HttpResponse(status=204, headers={'HX-Trigger': json.dumps(trigger)})

        messages.success(self.request, f"Ученик {student_name} был успешно удален.")
        return redirect(success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['cancel_url'] = self.get_success_url()
        return context

@login_required
def student_delete_multiple_view(request):
    """Массовое удаление выбранных учеников."""
    user = request.user

    if request.method == 'POST':
        student_ids_to_delete = request.POST.getlist('student_ids')
        class_id = request.POST.get('class_id')

        target_school = None
        if class_id:
            try:
                target_class = SchoolClass.objects.select_related('school').get(pk=class_id)
                target_school = target_class.school
            except SchoolClass.DoesNotExist:
                messages.error(request, "Указанный класс не найден.")
                return redirect('core:student_school_list')

        is_allowed = False
        if user.is_superuser:
            is_allowed = True
        elif target_school and hasattr(user, 'profile') and user.profile.role == UserProfile.Role.DIRECTOR:
            if target_school in get_accessible_schools(user):
                is_allowed = True

        if not is_allowed:
            messages.error(request, "У вас нет прав для удаления учеников из этого класса.")
            return redirect('core:student_school_list')

        if not student_ids_to_delete:
            messages.warning(request, "Вы не выбрали ни одного ученика для удаления.")
        else:
            students_query = Student.objects.filter(pk__in=student_ids_to_delete, school_class__school=target_school)
            deleted_count, _ = students_query.delete()
            messages.success(request, f"Успешно удалено учеников: {deleted_count}.")

        if class_id:
            return redirect('core:student_list', class_id=class_id)

    return redirect('core:student_school_list')

# =============================================================================
# --- МАССОВАЯ ЗАГРУЗКА УЧЕНИКОВ ---
# =============================================================================

@login_required
def student_upload_view(request):
    """Обрабатывает загрузку учеников из Excel файла."""
    if not request.user.is_superuser:
        messages.error(request, "У вас нет прав для выполнения этого действия.")
        return redirect('core:student_school_list')

    if request.method == 'POST':
        form = StudentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES['file']
            try:
                report = process_student_upload(file)
                row_errors = report.get('errors', [])
                if row_errors:
                    for error_message in row_errors:
                        messages.warning(request, error_message)
                created_count = report.get('created', 0)
                updated_count = report.get('updated', 0)
                total_processed = created_count + updated_count
                if total_processed > 0:
                    messages.success(
                        request,
                        f"Операция завершена. Всего обработано: {total_processed} (Создано: {created_count}, Обновлено: {updated_count})."
                    )
                elif not row_errors:
                    messages.info(
                        request,
                        "Файл обработан, но не найдено новых учеников для добавления или обновления."
                    )
            except Exception as e:
                messages.error(request, f"Произошла критическая ошибка при обработке файла: {e}")
                return redirect('core:student_upload')
            
            return redirect('core:student_school_list')
        else:
            messages.error(request, "Ошибка в форме. Пожалуйста, прикрепите корректный файл.")

    form = StudentUploadForm()
    context = {
        'title': 'Загрузить учеников из Excel',
        'form': form
    }
    return render(request, 'students/student_upload_form.html', context)