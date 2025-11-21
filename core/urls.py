# D:\GAT\core\urls.py (ИСПРАВЛЕННАЯ ВЕРСИЯ)

from django.urls import path
from core.views import booklets

# --- Импорты из 'accounts' ---
from accounts import views as account_views

# --- Импорты из приложения 'core' ---
from core.views import (
    api,
    dashboard,
    deep_analysis,
    grading,
    monitoring,
    permissions,
    statistics,
    student_dashboard,
    student_exams,
    reports_analysis,
    reports_archive,
    reports_comparison,
    reports_detailed,
    reports_upload,
    students_views,
    students_accounts,
    students_crud,
    crud_management,
    crud_question_bank,
    crud_tests,
    gat_test_booklet_preview,
    export_booklet_docx,
    download_booklet_pdf,
)

app_name = 'core'

urlpatterns = [
    # =============================================================================
    # --- АУТЕНТИФИКАЦИЯ И ГЛАВНЫЕ СТРАНИЦЫ ---
    # =============================================================================
    path('', account_views.user_login, name='home'),
    path('login/', account_views.user_login, name='login'),
    path('logout/', account_views.user_logout, name='logout'),
    path('dashboard/', dashboard.dashboard_view, name='dashboard'),
    
    
    # Главная страница банка теперь Библиотека
    path('dashboard/bank/library/', crud_question_bank.QuestionLibraryView.as_view(), name='question_library'),
    
    # Импорт
    path('dashboard/bank/import/', crud_question_bank.BankQuestionImportView.as_view(), name='bank_question_import'),

    # =============================================================================
    # --- ПРОФИЛЬ И УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ---
    # =============================================================================
    path('dashboard/profile/', account_views.profile, name='profile'),
    path('dashboard/users/', account_views.UserListView.as_view(), name='user_list'),
    path('dashboard/users/add/', account_views.UserCreateView.as_view(), name='user_add'),
    path('dashboard/users/<int:pk>/edit/', account_views.UserUpdateView.as_view(), name='user_edit'),
    path('dashboard/users/<int:pk>/delete/', account_views.UserDeleteView.as_view(), name='user_delete'),
    path('dashboard/users/<int:pk>/toggle-active/', account_views.toggle_user_active, name='user_toggle_active'),
    path('dashboard/permissions/', permissions.manage_permissions_view, name='manage_permissions'),
    path('api/bank-questions/<int:pk>/save-width/', crud_question_bank.save_question_image_width, name='bank_question_save_width'),

    # =============================================================================
    # --- ПАНЕЛЬ УПРАВЛЕНИЯ (CRUD ОПЕРАЦИИ) ---
    # =============================================================================
    path('dashboard/management/', crud_management.management_dashboard_view, name='management'),
    path('management/data-cleanup/', students_views.data_cleanup_view, name='data_cleanup'),

    # Учебные годы
    path('dashboard/years/', crud_management.AcademicYearListView.as_view(), name='year_list'),
    path('dashboard/years/add/', crud_management.AcademicYearCreateView.as_view(), name='year_add'),
    path('dashboard/years/<int:pk>/edit/', crud_management.AcademicYearUpdateView.as_view(), name='year_edit'),
    path('dashboard/years/<int:pk>/delete/', crud_management.AcademicYearDeleteView.as_view(), name='year_delete'),

    # Четверти
    path('dashboard/quarters/', crud_management.QuarterListView.as_view(), name='quarter_list'),
    path('dashboard/quarters/add/', crud_management.QuarterCreateView.as_view(), name='quarter_add'),
    path('dashboard/quarters/<int:pk>/edit/', crud_management.QuarterUpdateView.as_view(), name='quarter_edit'),
    path('dashboard/quarters/<int:pk>/delete/', crud_management.QuarterDeleteView.as_view(), name='quarter_delete'),

    # Школы
    path('dashboard/schools/', crud_management.SchoolListView.as_view(), name='school_list'),
    path('dashboard/schools/add/', crud_management.SchoolCreateView.as_view(), name='school_add'),
    path('dashboard/schools/<int:pk>/edit/', crud_management.SchoolUpdateView.as_view(), name='school_edit'),
    path('dashboard/schools/<int:pk>/delete/', crud_management.SchoolDeleteView.as_view(), name='school_delete'),

    # Классы
    path('dashboard/classes/', crud_management.SchoolClassListView.as_view(), name='class_list'),
    path('dashboard/classes/add/', crud_management.SchoolClassCreateView.as_view(), name='class_add'),
    path('dashboard/classes/<int:pk>/edit/', crud_management.SchoolClassUpdateView.as_view(), name='class_edit'),
    path('dashboard/classes/<int:pk>/delete/', crud_management.SchoolClassDeleteView.as_view(), name='class_delete'),

    # Предметы
    path('dashboard/subjects/', crud_management.SubjectListView.as_view(), name='subject_list'),
    path('dashboard/subjects/add/', crud_management.SubjectCreateView.as_view(), name='subject_add'),
    path('dashboard/subjects/<int:pk>/edit/', crud_management.SubjectUpdateView.as_view(), name='subject_edit'),
    path('dashboard/subjects/<int:pk>/delete/', crud_management.SubjectDeleteView.as_view(), name='subject_delete'),

    # =============================================================================
    # --- ЦЕНТР ВОПРОСОВ (BANK QUESTION & TOPICS) ---
    # =============================================================================
    
    # Темы вопросов
    path('dashboard/question-topics/', crud_question_bank.QuestionTopicListView.as_view(), name='question_topic_list'),
    path('dashboard/question-topics/add/', crud_question_bank.QuestionTopicCreateView.as_view(), name='question_topic_add'),
    path('dashboard/question-topics/<int:pk>/edit/', crud_question_bank.QuestionTopicUpdateView.as_view(), name='question_topic_edit'),
    path('dashboard/question-topics/<int:pk>/delete/', crud_question_bank.QuestionTopicDeleteView.as_view(), name='question_topic_delete'),

    # Вопросы из банка (CRUD)
    path('dashboard/bank-questions/', crud_question_bank.BankQuestionListView.as_view(), name='bank_question_list'),
    path('dashboard/bank-questions/add/', crud_question_bank.BankQuestionCreateView.as_view(), name='bank_question_add'),
    path('dashboard/bank-questions/<int:pk>/edit/', crud_question_bank.BankQuestionUpdateView.as_view(), name='bank_question_edit'),
    path('dashboard/bank-questions/<int:pk>/delete/', crud_question_bank.BankQuestionDeleteView.as_view(), name='bank_question_delete'),
    
    # API и действия с вопросами (AJAX/HTMX)
    path('dashboard/bank-questions/<int:pk>/preview/', crud_question_bank.bank_question_preview_view, name='bank_question_preview'),
    path('api/bank-questions/<int:pk>/save-option-order/', crud_question_bank.save_question_option_order, name='bank_question_save_option_order'),
    path('api/bank-questions/<int:pk>/update-image/', crud_question_bank.update_question_image, name='bank_question_update_image'),
    path('api/bank-questions/<int:pk>/quick-edit/', crud_question_bank.bank_question_quick_edit, name='bank_question_quick_edit'),

    # Количество вопросов (QuestionCount)
    path('dashboard/question-counts/', crud_question_bank.QuestionCountListView.as_view(), name='question_count_list'),
    path('dashboard/question-counts/add/', crud_question_bank.QuestionCountCreateView.as_view(), name='question_count_add'),
    path('dashboard/question-counts/bulk-add/', crud_question_bank.QuestionCountBulkCreateView.as_view(), name='question_count_bulk_add'),
    path('dashboard/question-counts/<int:pk>/edit/', crud_question_bank.QuestionCountUpdateView.as_view(), name='question_count_edit'),
    path('dashboard/question-counts/<int:pk>/delete/', crud_question_bank.QuestionCountDeleteView.as_view(), name='question_count_delete'),

    # =============================================================================
    # --- GAT ТЕСТЫ (ЭКЗАМЕНЫ) ---
    # =============================================================================
    path('dashboard/gat-tests/', crud_tests.gat_test_list_view, name='gat_test_list'),
    path('dashboard/gat-tests/add/', crud_tests.GatTestCreateView.as_view(), name='gat_test_add'),
    path('dashboard/gat-tests/<int:pk>/edit/', crud_tests.GatTestUpdateView.as_view(), name='gat_test_edit'),
    path('dashboard/gat-tests/<int:pk>/delete/', crud_tests.GatTestDeleteView.as_view(), name='gat_test_delete'),
    path('dashboard/gat-tests/<int:pk>/delete-results/', crud_tests.gat_test_delete_results_view, name='gat_test_delete_results'),
    
    # Управление вопросами в тесте
    path('dashboard/gat-tests/<int:test_pk>/add-question/<int:question_pk>/', crud_tests.add_question_to_test, name='gat_test_add_question'),
    path('dashboard/gat-tests/<int:test_pk>/remove-question/<int:question_pk>/', crud_tests.remove_question_from_test, name='gat_test_remove_question'),
    
    # Буклет и печать
    path('dashboard/gat-tests/<int:test_pk>/preview/', student_exams.gat_test_booklet_preview, name='gat_test_booklet_preview'),
    path('api/gat-tests/<int:test_pk>/save-order/', student_exams.save_booklet_order, name='gat_test_save_order'),

    # =============================================================================
    # --- УЧЕНИКИ ---
    # =============================================================================
    path('dashboard/students/', students_views.student_school_list_view, name='student_school_list'),
    path('dashboard/students/class/<int:class_id>/', students_views.student_list_view, name='student_list'),
    path('dashboard/students/add/', students_crud.StudentCreateView.as_view(), name='student_add'),
    path('dashboard/students/<int:pk>/edit/', students_crud.StudentUpdateView.as_view(), name='student_edit'),
    path('dashboard/students/delete-multiple/', students_crud.student_delete_multiple_view, name='student_delete_multiple'),
    path('dashboard/students/<int:pk>/delete/', students_crud.StudentDeleteView.as_view(), name='student_delete'),
    path('dashboard/students/upload/', students_crud.student_upload_view, name='student_upload'),
    path('dashboard/students/<int:student_id>/progress/', students_views.student_progress_view, name='student_progress'),
    path('dashboard/students/<int:student_id>/create-account/', students_accounts.create_student_user_account, name='student_create_account'),
    path('dashboard/students/user/<int:user_id>/reset-password/', students_accounts.student_reset_password, name='student_reset_password'),
    path('dashboard/students/user/<int:user_id>/delete-account/', students_accounts.delete_student_user_account, name='student_delete_account'),
    path('dashboard/students/class/<int:class_id>/create-and-export-accounts/', students_accounts.class_create_export_accounts, name='class_create_export_accounts'),
    path('dashboard/student/<int:student_pk>/notes/add/', crud_tests.TeacherNoteCreateView.as_view(), name='note_add'),
    path('dashboard/notes/<int:pk>/delete/', crud_tests.TeacherNoteDeleteView.as_view(), name='note_delete'),
    path('dashboard/students/school/<int:school_id>/parallels/', students_views.student_parallel_list_view, name='student_parallel_list'),
    path('dashboard/students/parallel/<int:parent_id>/classes/', students_views.student_class_list_view, name='student_class_list'),
    path('dashboard/students/parallel/<int:parallel_id>/all/', students_views.student_list_combined_view, name='student_list_combined'),
    path('dashboard/students/parallel/<int:parallel_id>/create-and-export-accounts/', students_accounts.parallel_create_export_accounts, name='parallel_create_export_accounts'),

    # =============================================================================
    # --- ОТЧЕТЫ, АНАЛИТИКА И ЭКСПОРТ ---
    # =============================================================================
    path('dashboard/results/upload/', reports_upload.upload_results_view, name='upload_results'),
    path('dashboard/results/gat/<int:test_number>/', reports_detailed.detailed_results_list_view, name='detailed_results_list'),
    path('dashboard/results/<int:pk>/', reports_detailed.student_result_detail_view, name='student_result_detail'),
    path('dashboard/results/<int:pk>/delete/', reports_detailed.student_result_delete_view, name='student_result_delete'),
    path('dashboard/monitoring/', monitoring.monitoring_view, name='monitoring'),
    path('dashboard/grading/', grading.grading_view, name='grading'),
    path('dashboard/statistics/', statistics.statistics_view, name='statistics'),
    path('dashboard/analysis/', reports_analysis.analysis_view, name='analysis'),
    path('dashboard/deep-analysis/', deep_analysis.deep_analysis_view, name='deep_analysis'),
    path('dashboard/results/archive/', reports_archive.archive_years_view, name='results_archive'),
    path('dashboard/results/archive/<int:year_id>/', reports_archive.archive_quarters_view, name='archive_quarters'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/', reports_archive.archive_schools_view, name='archive_schools'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/school/<int:school_id>/', reports_archive.archive_classes_view, name='archive_classes'),
    path('dashboard/results/archive/quarter/<int:quarter_id>/class/<int:class_id>/', reports_comparison.class_results_dashboard_view, name='class_results_dashboard'),
    path('dashboard/results/compare/<int:test1_id>/vs/<int:test2_id>/', reports_comparison.compare_class_tests_view, name='compare_class_tests'),
    path('archive/quarter/<int:quarter_id>/parent/<int:parent_class_id>/combined_report/', reports_comparison.combined_class_report_view, name='combined_class_report'),
    path('dashboard/results/archive/quarter/<int:quarter_pk>/school/<int:school_pk>/class/<int:class_pk>/', reports_archive.archive_subclasses_view, name='archive_subclasses'),
    
    # Экспорт
    path('dashboard/results/gat/<int:test_number>/export/excel/', reports_detailed.export_detailed_results_excel, name='export_detailed_results_excel'),
    path('dashboard/results/gat/<int:test_number>/export/pdf/', reports_detailed.export_detailed_results_pdf, name='export_detailed_results_pdf'),
    path('dashboard/monitoring/export/pdf/', monitoring.export_monitoring_pdf, name='export_monitoring_pdf'),
    path('dashboard/monitoring/export/excel/', monitoring.export_monitoring_excel, name='export_monitoring_excel'),
    path('dashboard/grading/export/excel/', grading.export_grading_excel, name='export_grading_excel'),
    path('dashboard/grading/export/pdf/', grading.export_grading_pdf, name='export_grading_pdf'),

    # =============================================================================
    # --- ОБЩИЙ API (ДЛЯ HTMX И JAVASCRIPT) ---
    # =============================================================================
    path('api/header-search/', api.header_search_api, name='api_header_search'),
    path('api/load-quarters/', api.load_quarters, name='api_load_quarters'),
    path('api/load-schools/', api.api_load_schools, name='api_load_schools'),
    path('api/load-classes/', api.load_classes, name='api_load_classes'),
    path('api/load-subjects/', api.load_subjects, name='api_load_subjects'),
    path('api/load-classes-as-chips/', api.api_load_classes_as_chips, name='api_load_classes_as_chips'),
    path('api/load-subjects-for-filters/', api.load_subjects_for_filters, name='api_load_subjects_for_filters'),
    path('api/notifications/', api.get_notifications_api, name='api_get_notifications'),
    path('api/notifications/mark-as-read/', api.mark_notifications_as_read, name='api_mark_notifications_as_read'),
    path('api/permissions/toggle-school/', api.toggle_school_access_api, name='api_toggle_school_access'),
    path('api/permissions/toggle-subject/', api.toggle_subject_access_api, name='api_toggle_subject_access'),
    path('htmx/load-class-and-subjects/', api.load_class_and_subjects_for_gat, name='load_class_and_subjects_for_gat'),
    path('htmx/load-fields-for-qc/', api.load_fields_for_qc, name='load_fields_for_qc'),
    path('htmx/load-subjects-for-user-form/', api.api_load_subjects_for_user_form, name='api_load_subjects_for_user_form'),
    path('api/load-topics/', api.load_topics, name='api_load_topics'),
    path('api/load-questions-by-topic/', api.load_questions_by_topic, name='api_load_questions_by_topic'),
    path('api/bank-options/<int:pk>/quick-edit/', crud_question_bank.bank_option_quick_edit, name='bank_option_quick_edit'),

    # =============================================================================
    # --- КАБИНЕТ УЧЕНИКА ---
    # =============================================================================
    path('student/dashboard/', student_dashboard.student_dashboard_view, name='student_dashboard'),
    path('student/exams/', student_exams.exam_list_view, name='exam_list'),
    path('student/exams/<int:result_id>/review/', student_exams.exam_review_view, name='exam_review'),
    
    # =============================================================================
    # --- БУКЛЕТЫ И ПУБЛИКАЦИЯ (НОВЫЙ МОДУЛЬ) ---
    # =============================================================================
    path('dashboard/booklets/', booklets.booklet_catalog_view, name='booklet_catalog'),
    path('api/gat-tests/<int:pk>/toggle-publish/', booklets.toggle_publish_status, name='toggle_publish_status'),
    path('gat-tests/<int:test_pk>/export-word/', export_booklet_docx, name='gat_test_export_word'),
    path('gat-tests/<int:test_pk>/download-pdf/', download_booklet_pdf, name='gat_test_download_pdf'),
]