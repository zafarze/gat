# D:\New_GAT\core\urls.py (ПОЛНАЯ И ОБНОВЛЁННАЯ ВЕРСИЯ)

from django.urls import path
from . import views

urlpatterns = [
    ## --- ОСНОВНЫЕ СТРАНИЦЫ И АУТЕНТИФИКАЦИЯ ---
    path('', views.login_view, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('dashboard/management/', views.management_view, name='management'),

    ## --- CRUD (УПРАВЛЕНИЕ ДАННЫМИ) ---
    # Учебные Годы
    path('dashboard/years/', views.AcademicYearListView.as_view(), name='year_list'),
    path('dashboard/years/add/', views.AcademicYearCreateView.as_view(), name='year_add'),
    path('dashboard/years/<int:pk>/edit/', views.AcademicYearUpdateView.as_view(), name='year_edit'),
    path('dashboard/years/<int:pk>/delete/', views.AcademicYearDeleteView.as_view(), name='year_delete'),

    # Четверти
    path('dashboard/quarters/', views.QuarterListView.as_view(), name='quarter_list'),
    path('dashboard/quarters/add/', views.QuarterCreateView.as_view(), name='quarter_add'),
    path('dashboard/quarters/<int:pk>/edit/', views.QuarterUpdateView.as_view(), name='quarter_edit'),
    path('dashboard/quarters/<int:pk>/delete/', views.QuarterDeleteView.as_view(), name='quarter_delete'),

    # Школы
    path('dashboard/schools/', views.SchoolListView.as_view(), name='school_list'),
    path('dashboard/schools/add/', views.SchoolCreateView.as_view(), name='school_add'),
    path('dashboard/schools/<int:pk>/edit/', views.SchoolUpdateView.as_view(), name='school_edit'),
    path('dashboard/schools/<int:pk>/delete/', views.SchoolDeleteView.as_view(), name='school_delete'),

    # Классы
    path('dashboard/classes/', views.SchoolClassListView.as_view(), name='class_list'),
    path('dashboard/classes/add/', views.SchoolClassCreateView.as_view(), name='class_add'),
    path('dashboard/classes/<int:pk>/edit/', views.SchoolClassUpdateView.as_view(), name='class_edit'),
    path('dashboard/classes/<int:pk>/delete/', views.SchoolClassDeleteView.as_view(), name='class_delete'),

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Предметы (теперь используют функцию, а не класс)
    path('dashboard/subjects/', views.subject_list_view, name='subject_list'),
    path('dashboard/subjects/add/', views.SubjectCreateView.as_view(), name='subject_add'),
    path('dashboard/subjects/<int:pk>/edit/', views.SubjectUpdateView.as_view(), name='subject_edit'),
    path('dashboard/subjects/<int:pk>/delete/', views.SubjectDeleteView.as_view(), name='subject_delete'),

    # Учебный план (Предметы в классе)
    path('dashboard/class-subjects/', views.ClassSubjectListView.as_view(), name='class_subject_list'),
    path('dashboard/class-subjects/add/', views.ClassSubjectCreateView.as_view(), name='class_subject_add'),
    path('dashboard/class-subjects/<int:pk>/edit/', views.ClassSubjectUpdateView.as_view(), name='class_subject_edit'),
    path('dashboard/class-subjects/<int:pk>/delete/', views.ClassSubjectDeleteView.as_view(), name='class_subject_delete'),

    # GAT Тесты
    path('dashboard/gat-tests/', views.gat_test_list_view, name='gat_test_list'),
    path('dashboard/gat-tests/add/', views.GatTestCreateView.as_view(), name='gat_test_add'),
    path('dashboard/gat-tests/<int:pk>/edit/', views.GatTestUpdateView.as_view(), name='gat_test_edit'),
    path('dashboard/gat-tests/<int:pk>/delete/', views.GatTestDeleteView.as_view(), name='gat_test_delete'),
    path('dashboard/gat-tests/<int:pk>/delete-results/', views.gat_test_delete_results_view, name='gat_test_delete_results'),

    ## --- РЕЗУЛЬТАТЫ, ОТЧЕТЫ И АРХИВ ---
    # Загрузка результатов
    path('dashboard/results/upload/', views.upload_results_view, name='upload_results'),

    # Детальный рейтинг (GAT-1 или GAT-2) и экспорт
    path('dashboard/results/gat/<int:test_number>/', views.detailed_results_list_view, name='detailed_results_list'),
    path('dashboard/results/gat/<int:test_number>/export/excel/', views.export_detailed_results_excel, name='export_detailed_results_excel'),
    path('dashboard/results/gat/<int:test_number>/export/pdf/', views.export_detailed_results_pdf, name='export_detailed_results_pdf'),

    # Детальный результат одного студента
    path('dashboard/results/<int:pk>/', views.student_result_detail_view, name='student_result_detail'),
    path('dashboard/results/<int:pk>/delete/', views.student_result_delete_view, name='student_result_delete'),

    # Сравнение двух тестов
    path('dashboard/results/compare/<int:test1_id>/vs/<int:test2_id>/', views.compare_class_tests_view, name='compare_class_tests'),

    # Новая иерархическая навигация по результатам
    path('dashboard/results/archive/', views.archive_years_view, name='results_archive'),
    path('dashboard/results/archive/<int:year_id>/', views.archive_quarters_view, name='archive_quarters'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/', views.archive_schools_view, name='archive_schools'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/school/<int:school_id>/', views.archive_classes_view, name='archive_classes'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/class/<int:class_id>/total/', views.class_results_view, name='class_results'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/class/<int:class_id>/tests/', views.gat_test_archive_view, name='archive_tests_list'),

    ## --- API (ДЛЯ JAVASCRIPT) ---
    path('api/load-quarters/', views.load_quarters, name='api_load_quarters'),
    path('api/load-classes/', views.load_classes, name='api_load_classes'),
    path('api/get-previous-subjects/', views.get_previous_subjects_view, name='api_get_previous_subjects'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/class/<int:class_id>/', views.class_results_dashboard_view, name='class_results_dashboard'),
    path('dashboard/statistics/', views.statistics_view, name='statistics'),
    path('dashboard/analysis/', views.analysis_view, name='analysis'),
    path('dashboard/deep-analysis/', views.deep_analysis_view, name='deep_analysis'),
    path('dashboard/student/<int:student_id>/', views.student_progress_view, name='student_progress'),
    path('api/load-subjects-and-classes/', views.load_subjects_and_classes_for_schools, name='api_load_subjects_and_classes'),
    path('api/header-search/', views.header_search_api, name='api_header_search'),
    path('dashboard/profile/', views.profile_view, name='profile'),
]
