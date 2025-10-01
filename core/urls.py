# D:\New_GAT\core\urls.py (Финальная, исправленная версия)

from django.urls import path
# Явно импортируем каждый модуль представлений для ясности и надежности
from .views import (
    auth,
    dashboard,
    profile,
    crud,
    students,
    reports,
    monitoring,
    deep_analysis,
    api,
    grading
)

urlpatterns = [
    # --- ОСНОВНЫЕ СТРАНИЦЫ И АУТЕНТИФИКАЦИЯ ---
    path('', auth.login_view, name='index'),
    path('login/', auth.login_view, name='login'),
    path('logout/', auth.logout_view, name='logout'),
    path('dashboard/', dashboard.dashboard_view, name='dashboard'),
    path('dashboard/management/', dashboard.management_view, name='management'),
    path('dashboard/monitoring/', monitoring.monitoring_view, name='monitoring'),

    # --- ПРОФИЛЬ И УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---
    path('dashboard/profile/', profile.profile_view, name='profile'),
    path('dashboard/users/', profile.user_list_view, name='user_list'),
    path('dashboard/users/add/', profile.user_create_view, name='user_add'),
    path('dashboard/users/<int:pk>/edit/', profile.user_update_view, name='user_edit'),
    path('dashboard/users/<int:pk>/delete/', profile.UserDeleteView.as_view(), name='user_delete'),
    path('dashboard/users/<int:pk>/toggle-active/', profile.user_toggle_active_view, name='user_toggle_active'),

    # --- ЗАМЕТКИ УЧИТЕЛЕЙ (теперь указывают на crud) ---
    path('dashboard/student/<int:student_pk>/notes/add/', crud.TeacherNoteCreateView.as_view(), name='note_add'),
    path('dashboard/notes/<int:pk>/delete/', crud.TeacherNoteDeleteView.as_view(), name='note_delete'),

    # --- УПРАВЛЕНИЕ ДАННЫМИ (CRUD) ---
    # Учебные Годы
    path('dashboard/years/', crud.AcademicYearListView.as_view(), name='year_list'),
    path('dashboard/years/add/', crud.AcademicYearCreateView.as_view(), name='year_add'),
    path('dashboard/years/<int:pk>/edit/', crud.AcademicYearUpdateView.as_view(), name='year_edit'),
    path('dashboard/years/<int:pk>/delete/', crud.AcademicYearDeleteView.as_view(), name='year_delete'),

    # Четверти
    path('dashboard/quarters/', crud.QuarterListView.as_view(), name='quarter_list'),
    path('dashboard/quarters/add/', crud.QuarterCreateView.as_view(), name='quarter_add'),
    path('dashboard/quarters/<int:pk>/edit/', crud.QuarterUpdateView.as_view(), name='quarter_edit'),
    path('dashboard/quarters/<int:pk>/delete/', crud.QuarterDeleteView.as_view(), name='quarter_delete'),

    # Школы
    path('dashboard/schools/', crud.SchoolListView.as_view(), name='school_list'),
    path('dashboard/schools/add/', crud.SchoolCreateView.as_view(), name='school_add'),
    path('dashboard/schools/<int:pk>/edit/', crud.SchoolUpdateView.as_view(), name='school_edit'),
    path('dashboard/schools/<int:pk>/delete/', crud.SchoolDeleteView.as_view(), name='school_delete'),

    # Классы
    path('dashboard/classes/', crud.SchoolClassListView.as_view(), name='class_list'),
    path('dashboard/classes/add/', crud.SchoolClassCreateView.as_view(), name='class_add'),
    path('dashboard/classes/<int:pk>/edit/', crud.SchoolClassUpdateView.as_view(), name='class_edit'),
    path('dashboard/classes/<int:pk>/delete/', crud.SchoolClassDeleteView.as_view(), name='class_delete'),

    # Предметы
    path('dashboard/subjects/', crud.subject_list_view, name='subject_list'),
    path('dashboard/subjects/add/', crud.SubjectCreateView.as_view(), name='subject_add'),
    path('dashboard/subjects/<int:pk>/edit/', crud.SubjectUpdateView.as_view(), name='subject_edit'),
    path('dashboard/subjects/<int:pk>/delete/', crud.SubjectDeleteView.as_view(), name='subject_delete'),

    # Учебный план (Предметы в классе)
    path('dashboard/class-subjects/', crud.ClassSubjectListView.as_view(), name='class_subject_list'),
    path('dashboard/class-subjects/add/', crud.ClassSubjectCreateView.as_view(), name='class_subject_add'),
    path('dashboard/class-subjects/<int:pk>/edit/', crud.ClassSubjectUpdateView.as_view(), name='class_subject_edit'),
    path('dashboard/class-subjects/<int:pk>/delete/', crud.ClassSubjectDeleteView.as_view(), name='class_subject_delete'),

    # GAT Тесты
    path('dashboard/gat-tests/', crud.gat_test_list_view, name='gat_test_list'),
    path('dashboard/gat-tests/add/', crud.GatTestCreateView.as_view(), name='gat_test_add'),
    path('dashboard/gat-tests/<int:pk>/edit/', crud.GatTestUpdateView.as_view(), name='gat_test_edit'),
    path('dashboard/gat-tests/<int:pk>/delete/', crud.GatTestDeleteView.as_view(), name='gat_test_delete'),
    path('dashboard/gat-tests/<int:pk>/delete-results/', crud.gat_test_delete_results_view, name='gat_test_delete_results'),

    # Ученики
    path('dashboard/students/', students.StudentListView.as_view(), name='student_list'),
    path('dashboard/students/add/', students.StudentCreateView.as_view(), name='student_add'),
    path('dashboard/students/<int:pk>/edit/', students.StudentUpdateView.as_view(), name='student_edit'),
    path('dashboard/students/<int:pk>/delete/', students.StudentDeleteView.as_view(), name='student_delete'),
    path('dashboard/students/upload/', students.student_upload_view, name='student_upload'),
    path('dashboard/student/<int:student_id>/', students.student_progress_view, name='student_progress'),

    # --- РЕЗУЛЬТАТЫ, ОТЧЕТЫ И АНАЛИТИКА ---
    path('dashboard/results/upload/', reports.upload_results_view, name='upload_results'),
    path('dashboard/results/gat/<int:test_number>/', reports.detailed_results_list_view, name='detailed_results_list'),
    path('dashboard/results/<int:pk>/', reports.student_result_detail_view, name='student_result_detail'),
    path('dashboard/results/<int:pk>/delete/', reports.student_result_delete_view, name='student_result_delete'),
    path('dashboard/statistics/', reports.statistics_view, name='statistics'),
    path('dashboard/analysis/', reports.analysis_view, name='analysis'),
    path('dashboard/deep-analysis/', deep_analysis.deep_analysis_view, name='deep_analysis'),

    # Архив и сравнение
    path('dashboard/results/archive/', reports.archive_years_view, name='results_archive'),
    path('dashboard/results/archive/<int:year_id>/', reports.archive_quarters_view, name='archive_quarters'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/', reports.archive_schools_view, name='archive_schools'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/school/<int:school_id>/', reports.archive_classes_view, name='archive_classes'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/class/<int:class_id>/', reports.class_results_dashboard_view, name='class_results_dashboard'),
    path('dashboard/results/compare/<int:test1_id>/vs/<int:test2_id>/', reports.compare_class_tests_view, name='compare_class_tests'),

    # Экспорт
    path('dashboard/results/gat/<int:test_number>/export/excel/', reports.export_detailed_results_excel, name='export_detailed_results_excel'),
    path('dashboard/results/gat/<int:test_number>/export/pdf/', reports.export_detailed_results_pdf, name='export_detailed_results_pdf'),
    path('dashboard/monitoring/export/pdf/', monitoring.export_monitoring_pdf, name='export_monitoring_pdf'),
    path('dashboard/monitoring/export/excel/', monitoring.export_monitoring_excel, name='export_monitoring_excel'),
    path('dashboard/grading/', grading.grading_view, name='grading'),
    path('dashboard/grading/export/excel/', grading.export_grading_excel, name='export_grading_excel'),
    path('dashboard/grading/export/pdf/', grading.export_grading_pdf, name='export_grading_pdf'),

    # --- API (ДЛЯ JAVASCRIPT) ---
    path('api/header-search/', api.header_search_api, name='api_header_search'),
    path('api/get-previous-subjects/', api.get_previous_subjects_view, name='api_get_previous_subjects'),
    path('api/load-subjects-and-classes/', api.load_subjects_and_classes_for_schools, name='api_load_subjects_and_classes'),
    path('api/load-quarters/', api.load_quarters, name='api_load_quarters'),
    path('api/load-classes/', api.load_classes, name='api_load_classes'),
    path('api/load-subjects/', api.load_subjects, name='api_load_subjects'),
]