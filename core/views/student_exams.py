# D:\New_GAT\core\views\student_exams.py (ПОЛНАЯ ИСПРАВЛЕННАЯ ВЕРСИЯ)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from ..models import StudentResult, Question, Subject

@login_required
def exam_list_view(request):
    """Отображает страницу со списком всех пройденных учеником тестов."""
    if not hasattr(request.user, 'profile') or request.user.profile.role != 'STUDENT':
        return redirect('dashboard')

    student = request.user.profile.student
    student_results = StudentResult.objects.filter(student=student).select_related('gat_test').order_by('-gat_test__test_date')
    
    context = {
        'title': 'Мои экзамены',
        'results': student_results,
    }
    return render(request, 'student_dashboard/exam_list.html', context)

@login_required
def exam_review_view(request, result_id):
    """Отображает детальный разбор одного выбранного теста."""
    result = get_object_or_404(StudentResult, id=result_id)
    
    # Проверка безопасности: ученик может видеть только свои результаты
    if not request.user.profile.student == result.student:
        messages.error(request, "У вас нет доступа к этому результату.")
        return redirect('core:student_dashboard')

    # Группируем вопросы по предметам для красивого отображения
    questions_by_subject = {}
    test_subjects = result.gat_test.subjects.order_by('name')
    
    for subject in test_subjects:
        questions = Question.objects.filter(
            gat_test=result.gat_test, 
            topic__subject=subject
        ).prefetch_related('options').order_by('question_number')
        
        # ✨ ИЗМЕНЕНИЕ 1: Теперь мы ожидаем, что в `scores` хранится словарь (dict), а не список (list).
        # Например: {"1": True, "2": False, "3": True}
        student_answers_dict = result.scores_by_subject.get(str(subject.id), {})
        
        review_data = []
        for question in questions:
            # ✨ ИЗМЕНЕНИЕ 2: Ищем ответ по номеру вопроса, а не по индексу в списке.
            # Это делает логику надёжной и независимой от порядка.
            # .get() используется для безопасности, если ответа на какой-то вопрос нет.
            was_correct = student_answers_dict.get(str(question.question_number))
            
            review_data.append({
                'question': question,
                'student_was_correct': was_correct,
            })
        
        if review_data:
            questions_by_subject[subject.name] = review_data

    context = {
        'title': f'Разбор теста: {result.gat_test.name}',
        'result': result,
        'questions_by_subject': questions_by_subject,
    }
    return render(request, 'student_dashboard/exam_review.html', context)