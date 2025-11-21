# D:\GAT\core\views\crud_management.py (НОВЫЙ ФАЙЛ)

from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.urls import reverse_lazy
from django.template.loader import render_to_string
from accounts.models import UserProfile

# АБСОЛЮТНЫЕ ИМПОРТЫ
from core.models import (
    AcademicYear, Quarter, School, SchoolClass, Subject
)
from core.forms import (
    AcademicYearForm, QuarterForm, SchoolForm, SchoolClassForm,
    SubjectForm
)
from core.views.permissions import get_accessible_schools
from .crud_base import HtmxListView, HtmxCreateView, HtmxUpdateView, HtmxDeleteView

# =============================================================================
# --- УПРАВЛЕНИЕ (MANAGEMENT) ---
# =============================================================================
@login_required
def management_dashboard_view(request):
    return render(request, 'management.html')

# =============================================================================
# --- УЧЕБНЫЕ ГОДЫ (ACADEMIC YEAR) ---
# =============================================================================
class AcademicYearListView(HtmxListView):
    model = AcademicYear
    template_name_prefix = 'years'
    extra_context = {
        'title': 'Учебные годы', 
        'add_url': 'core:year_add',
        'edit_url': 'core:year_edit',
        'delete_url': 'core:year_delete'
    }

class AcademicYearCreateView(HtmxCreateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

class AcademicYearUpdateView(HtmxUpdateView):
    model = AcademicYear
    form_class = AcademicYearForm
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

class AcademicYearDeleteView(HtmxDeleteView):
    model = AcademicYear
    template_name = 'years/confirm_delete.html'
    template_name_prefix = 'years'
    list_url_name = 'core:year_list'

# =============================================================================
# --- ЧЕТВЕРТИ (QUARTER) ---
# =============================================================================
class QuarterListView(HtmxListView):
    model = Quarter
    template_name_prefix = 'quarters'
    extra_context = {
        'title': 'Четверти',
        'add_url': 'core:quarter_add',
        'edit_url': 'core:quarter_edit',
        'delete_url': 'core:quarter_delete'
    }

    def get_queryset(self):
        # Это базовый справочник, фильтрация по правам не нужна.
        return Quarter.objects.select_related('year').order_by('-year__start_date', 'start_date')

class QuarterCreateView(HtmxCreateView):
    model = Quarter
    form_class = QuarterForm
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

class QuarterUpdateView(HtmxUpdateView):
    model = Quarter
    form_class = QuarterForm
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

class QuarterDeleteView(HtmxDeleteView):
    model = Quarter
    template_name = 'quarters/confirm_delete.html'
    template_name_prefix = 'quarters'
    list_url_name = 'core:quarter_list'

# =============================================================================
# --- ШКОЛЫ (SCHOOL) ---
# =============================================================================
class SchoolListView(HtmxListView):
    model = School
    template_name_prefix = 'schools'
    extra_context = {
        'title': 'Школы',
        'add_url': 'core:school_add',
        'edit_url': 'core:school_edit',
        'delete_url': 'core:school_delete',
        'table_template': 'schools/_table.html'
    }

    def get_queryset(self):
        user = self.request.user
        profile = getattr(user, 'profile', None)

        if user.is_superuser:
            queryset = School.objects.all()
        elif profile and profile.role == UserProfile.Role.DIRECTOR:
            queryset = profile.schools.all()
        else:
            queryset = get_accessible_schools(user)

        sort_by = self.request.GET.get('sort', 'school_id')
        direction = self.request.GET.get('direction', 'asc')

        allowed_sort_fields = ['school_id', 'name', 'city']
        if sort_by not in allowed_sort_fields:
            sort_by = 'school_id'

        if direction == 'desc':
            sort_by = f'-{sort_by}'

        return queryset.order_by(sort_by)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_sort'] = self.request.GET.get('sort', 'school_id')
        context['current_direction'] = self.request.GET.get('direction', 'asc')
        return context

class SchoolCreateView(HtmxCreateView):
    model = School
    form_class = SchoolForm
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

class SchoolUpdateView(HtmxUpdateView):
    model = School
    form_class = SchoolForm
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

class SchoolDeleteView(HtmxDeleteView):
    model = School
    template_name = 'schools/confirm_delete.html'
    template_name_prefix = 'schools'
    list_url_name = 'core:school_list'

# =============================================================================
# --- КЛАССЫ (SCHOOL CLASS) ---
# =============================================================================

class SchoolClassListView(HtmxListView):
    model = School
    template_name_prefix = 'classes'
    extra_context = {
        'title': 'Классы',
        'add_url': 'core:class_add',
        'edit_url': 'core:class_edit',
        'delete_url': 'core:class_delete'
    }

    def get_queryset(self):
        schools_qs = get_accessible_schools(self.request.user)
        return schools_qs.prefetch_related(
            Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
        ).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'items' in context:
            context['schools'] = context.pop('items')
        return context

class SchoolClassCreateView(HtmxCreateView):
    model = SchoolClass
    form_class = SchoolClassForm
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if school_id := self.request.GET.get('school'):
            kwargs['school'] = get_object_or_404(School, pk=school_id)
            kwargs['initial'] = {'school': school_id}
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['school_id_for_htmx'] = self.request.GET.get('school')
        return context

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно создан.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            # Обновляем карточку школы
            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=self.object.school.pk)
            
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SchoolClassUpdateView(HtmxUpdateView):
    model = SchoolClass
    form_class = SchoolClassForm
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        if self.object:
            kwargs['school'] = self.object.school
        return kwargs

    def form_valid(self, form):
        self.object = form.save()
        success_message = f'"{self.object}" успешно обновлен.'
        messages.success(self.request, success_message)
        
        if self.request.htmx:
            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=self.object.school.pk)
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-modal": True, "show-message": {"text": success_message, "type": "success"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)

        return redirect(reverse_lazy(self.list_url_name))

class SchoolClassDeleteView(HtmxDeleteView):
    model = SchoolClass
    template_name = 'classes/confirm_delete.html'
    template_name_prefix = 'classes'
    list_url_name = 'core:class_list'

    def post(self, request, *args, **kwargs):
        if self.request.htmx:
            self.object = self.get_object()
            school = self.object.school
            item_name = str(self.object)
            self.object.delete()
            success_message = f'"{item_name}" успешно удален.'
            messages.error(self.request, success_message)

            school = School.objects.prefetch_related(
                Prefetch('classes', queryset=SchoolClass.objects.order_by('name'))
            ).get(pk=school.pk)
            context = { 'school': school, 'add_url': 'core:class_add', 'user': self.request.user }
            trigger = {"close-delete-modal": True, "show-message": {"text": success_message, "type": "error"}}
            headers = {'HX-Trigger': json.dumps(trigger)}
            html = render_to_string('classes/_school_card.html', context, request=self.request)
            return HttpResponse(html, headers=headers)
        
        return super().post(request, *args, **kwargs)

# =============================================================================
# --- ПРЕДМЕТЫ (SUBJECT) ---
# =============================================================================
class SubjectListView(HtmxListView):
    model = Subject
    template_name_prefix = 'subjects'
    extra_context = {
        'title': 'Предметы',
        'add_url': 'core:subject_add',
        'edit_url': 'core:subject_edit',
        'delete_url': 'core:subject_delete'
    }

    def get_queryset(self):
        # Предметы - это глобальный справочник, доступный администраторам и директорам
        if self.request.user.is_staff or self.request.user.is_superuser or \
           (hasattr(self.request.user, 'profile') and self.request.user.profile.role == UserProfile.Role.DIRECTOR):
             return Subject.objects.all().order_by('name')
        
        # Другие роли (Эксперты, Учителя) видят только свои
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile.subjects.all().order_by('name')
            
        return Subject.objects.none()


class SubjectCreateView(HtmxCreateView):
    model = Subject
    form_class = SubjectForm
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'
    
    # form_valid() использует базовую реализацию с 'force-refresh',
    # которая идеально подходит для этого простого списка.

class SubjectUpdateView(HtmxUpdateView):
    model = Subject
    form_class = SubjectForm
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'
    
    # form_valid() использует базовую реализацию с 'force-refresh'.

class SubjectDeleteView(HtmxDeleteView):
    model = Subject
    template_name = 'subjects/confirm_delete.html'
    template_name_prefix = 'subjects'
    list_url_name = 'core:subject_list'
    
    # post() использует базовую реализацию с 'force-refresh'.