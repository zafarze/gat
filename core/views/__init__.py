# D:\New_GAT\core\views\__init__.py (ОБНОВЛЕННЫЙ ФАЙЛ)

# --- Импорты из api.py ---
from .api import (
    load_quarters,
    load_classes,
    load_subjects,
    api_load_classes_as_chips,
    load_subjects_for_filters,
    get_notifications_api,
    mark_notifications_as_read,
    header_search_api,
    toggle_school_access_api,
    toggle_subject_access_api,
    load_class_and_subjects_for_gat,
    load_fields_for_qc,
    api_load_schools,
    api_load_subjects_for_user_form,
    load_topics,
    load_questions_by_topic
)

# --- Импорты из crud_management.py ---
from .crud_management import (
    management_dashboard_view,
    AcademicYearListView, AcademicYearCreateView, AcademicYearUpdateView, AcademicYearDeleteView,
    QuarterListView, QuarterCreateView, QuarterUpdateView, QuarterDeleteView,
    SchoolListView, SchoolCreateView, SchoolUpdateView, SchoolDeleteView,
    SchoolClassListView, SchoolClassCreateView, SchoolClassUpdateView, SchoolClassDeleteView,
    SubjectListView, SubjectCreateView, SubjectUpdateView, SubjectDeleteView
)

# --- Импорты из crud_question_bank.py ---
from .crud_question_bank import (
    QuestionTopicListView, QuestionTopicCreateView, QuestionTopicUpdateView, QuestionTopicDeleteView,
    BankQuestionListView, BankQuestionCreateView, BankQuestionUpdateView, BankQuestionDeleteView,
    QuestionCountListView, QuestionCountCreateView, QuestionCountUpdateView, QuestionCountDeleteView,
    QuestionCountBulkCreateView
)

# --- Импорты из crud_tests.py ---
from .crud_tests import (
    gat_test_list_view,
    GatTestCreateView, GatTestUpdateView, GatTestDeleteView,
    gat_test_delete_results_view,
    TeacherNoteCreateView, TeacherNoteDeleteView
)

# --- Импорты из dashboard.py ---
from .dashboard import (
    dashboard_view,
)

# --- Импорты из deep_analysis.py ---
from .deep_analysis import (
    deep_analysis_view,
)

# --- Импорты из grading.py ---
from .grading import (
    grading_view,
    export_grading_pdf,
    export_grading_excel,
)

# --- Импорты из monitoring.py ---
from .monitoring import (
    monitoring_view,
    export_monitoring_pdf,
    export_monitoring_excel,
)

# --- Импорты из permissions.py ---
from .permissions import (
    manage_permissions_view,
    get_accessible_schools,
    get_accessible_subjects,
    get_accessible_classes,
    get_accessible_students
)

# --- Импорты из reports_analysis.py ---
from .reports_analysis import (
    analysis_view,
)

# --- Импорты из reports_archive.py ---
from .reports_archive import (
    archive_years_view,
    archive_quarters_view,
    archive_schools_view,
    archive_classes_view,
    archive_subclasses_view
)

# --- Импорты из reports_comparison.py ---
from .reports_comparison import (
    class_results_dashboard_view,
    compare_class_tests_view,
    combined_class_report_view
)

# --- Импорты из reports_detailed.py ---
from .reports_detailed import (
    detailed_results_list_view,
    student_result_detail_view,
    student_result_delete_view,
    export_detailed_results_excel,
    export_detailed_results_pdf
)

# --- Импорты из reports_upload.py ---
from .reports_upload import (
    upload_results_view,
)

# --- Импорты из statistics.py ---
from .statistics import (
    statistics_view,
)

# --- Импорты из student_dashboard.py ---
from .student_dashboard import (
    student_dashboard_view,
)

# --- Импорты из student_exams.py ---
from .student_exams import (
    exam_list_view,
    exam_review_view,
    gat_test_booklet_preview,
    save_booklet_order,
    export_booklet_docx,
    download_booklet_pdf,
)

# --- Импорты из students_views.py ---
from .students_views import (
    student_school_list_view,
    student_parallel_list_view,
    student_class_list_view,
    student_list_view,
    student_list_combined_view,
    student_progress_view,
    data_cleanup_view
)

# --- Импорты из students_accounts.py ---
from .students_accounts import (
    create_student_user_account,
    student_reset_password,
    delete_student_user_account,
    class_create_export_accounts,
    parallel_create_export_accounts
)

# --- Импорты из students_crud.py ---
from .students_crud import (
    StudentCreateView,
    StudentUpdateView,
    StudentDeleteView,
    student_delete_multiple_view,
    student_upload_view
)

# --- Импорты из utils_reports.py ---
from .utils_reports import (
    get_report_context,
)